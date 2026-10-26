from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from english7.api.errors import ApplicationError
from english7.db.models import (
    Activity,
    AudioTrack,
    ContentRevision,
    QuestionSource,
    ReviewStatus,
    Section,
    SourceDocument,
    SourceFragment,
    Textbook,
    Unit,
)
from english7.modules.admin.audit_service import AdminAuditService
from english7.modules.flashcards.models import Flashcard


class AdminContentService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        audit_service: AdminAuditService,
    ) -> None:
        self._session_factory = session_factory
        self._audit = audit_service

    @staticmethod
    def _unit_snapshot(unit: Unit) -> dict[str, Any]:
        return {
            "textbook_id": str(unit.textbook_id),
            "number": unit.number,
            "title": unit.title,
            "is_published": unit.is_published,
        }

    @staticmethod
    def _fragment_snapshot(fragment: SourceFragment) -> dict[str, Any]:
        return {
            "source_document_id": str(fragment.source_document_id),
            "activity_id": str(fragment.activity_id) if fragment.activity_id else None,
            "pdf_page": fragment.pdf_page,
            "printed_page": fragment.printed_page,
            "normalized_text": fragment.normalized_text,
            "review_status": str(fragment.review_status),
            "is_published": fragment.is_published,
        }

    @staticmethod
    def _section_snapshot(section: Section) -> dict[str, Any]:
        return {
            "unit_id": str(section.unit_id),
            "title": section.title,
            "section_type": section.section_type,
            "position": section.position,
        }

    @staticmethod
    def _activity_snapshot(activity: Activity) -> dict[str, Any]:
        return {
            "section_id": str(activity.section_id),
            "number": activity.number,
            "activity_type": activity.activity_type,
            "instruction": activity.instruction,
        }

    @staticmethod
    def _current_version(session: Session, entity_type: str, entity_id: UUID) -> int:
        return session.scalar(
            select(func.max(ContentRevision.version)).where(
                ContentRevision.entity_type == entity_type,
                ContentRevision.entity_id == entity_id,
            )
        ) or 0

    def _add_revision(
        self,
        session: Session,
        *,
        entity_type: str,
        entity_id: UUID,
        snapshot: dict[str, Any],
        actor_id: UUID,
        status: str,
    ) -> int:
        version = self._current_version(session, entity_type, entity_id) + 1
        session.add(
            ContentRevision(
                entity_type=entity_type,
                entity_id=entity_id,
                version=version,
                status=status,
                snapshot=snapshot,
                actor_id=actor_id,
                published_at=(
                    datetime.now(timezone.utc) if status == "published" else None
                ),
            )
        )
        return version

    def _ensure_version(
        self,
        session: Session,
        entity_type: str,
        entity_id: UUID,
        expected_version: int,
    ) -> None:
        actual = self._current_version(session, entity_type, entity_id)
        if actual != expected_version:
            raise ApplicationError(
                "content_version_conflict",
                "Content changed on another device; reload before saving",
                409,
                {"expected": expected_version, "actual": actual},
            )

    def list_units(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            units = list(session.scalars(select(Unit).order_by(Unit.number, Unit.id)))
            return [self._unit_view(session, unit) for unit in units]

    def _unit_view(self, session: Session, unit: Unit) -> dict[str, Any]:
        version = self._current_version(session, "unit", unit.id)
        status = "published" if unit.is_published else "draft"
        latest_status = session.scalar(
            select(ContentRevision.status)
            .where(
                ContentRevision.entity_type == "unit",
                ContentRevision.entity_id == unit.id,
            )
            .order_by(ContentRevision.version.desc())
            .limit(1)
        )
        return {
            "id": unit.id,
            "textbook_id": unit.textbook_id,
            "number": unit.number,
            "title": unit.title,
            "is_published": unit.is_published,
            "version": version,
            "status": latest_status or status,
        }

    def create_unit(
        self,
        *,
        textbook_id: UUID,
        number: int,
        title: str,
        actor_id: UUID,
        **audit_context: Any,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            if session.get(Textbook, textbook_id) is None:
                raise ApplicationError("textbook_not_found", "Textbook was not found", 404)
            duplicate = session.scalar(
                select(Unit.id).where(Unit.textbook_id == textbook_id, Unit.number == number)
            )
            if duplicate is not None:
                raise ApplicationError("unit_number_conflict", "Unit number already exists", 409)
            unit = Unit(textbook_id=textbook_id, number=number, title=title.strip(), is_published=False)
            session.add(unit)
            session.flush()
            version = self._add_revision(
                session,
                entity_type="unit",
                entity_id=unit.id,
                snapshot=self._unit_snapshot(unit),
                actor_id=actor_id,
                status="draft",
            )
            session.commit()
            result = self._unit_view(session, unit)
            result["version"] = version
        self._record(actor_id, "unit.created", unit.id, after=result, **audit_context)
        return result

    def update_unit(
        self,
        unit_id: UUID,
        changes: dict[str, Any],
        *,
        expected_version: int,
        actor_id: UUID,
        **audit_context: Any,
    ) -> dict[str, Any]:
        allowed = {"number", "title"}
        if set(changes) - allowed:
            raise ApplicationError("content_fields_invalid", "Unit contains unsupported fields", 422)
        with self._session_factory() as session:
            unit = session.get(Unit, unit_id)
            if unit is None:
                raise ApplicationError("unit_not_found", "Unit was not found", 404)
            self._ensure_version(session, "unit", unit_id, expected_version)
            before = self._unit_snapshot(unit)
            for field, value in changes.items():
                setattr(unit, field, value.strip() if field == "title" else value)
            unit.is_published = False
            version = self._add_revision(
                session,
                entity_type="unit",
                entity_id=unit.id,
                snapshot=self._unit_snapshot(unit),
                actor_id=actor_id,
                status="draft",
            )
            session.commit()
            result = self._unit_view(session, unit)
            result["version"] = version
        self._record(actor_id, "unit.updated", unit_id, before=before, after=result, **audit_context)
        return result

    def publish_unit(
        self,
        unit_id: UUID,
        *,
        expected_version: int,
        actor_id: UUID,
        **audit_context: Any,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            unit = session.get(Unit, unit_id)
            if unit is None:
                raise ApplicationError("unit_not_found", "Unit was not found", 404)
            self._ensure_version(session, "unit", unit_id, expected_version)
            grounded = session.scalar(
                select(SourceFragment.id)
                .join(Activity, SourceFragment.activity_id == Activity.id)
                .join(Section, Activity.section_id == Section.id)
                .where(
                    Section.unit_id == unit_id,
                    SourceFragment.printed_page.is_not(None),
                    SourceFragment.review_status == ReviewStatus.VERIFIED,
                    SourceFragment.is_published == true(),
                )
                .limit(1)
            )
            if grounded is None:
                raise ApplicationError(
                    "grounding_required",
                    "Publish at least one verified fragment with a textbook page first",
                    422,
                )
            before = self._unit_snapshot(unit)
            unit.is_published = True
            version = self._add_revision(
                session,
                entity_type="unit",
                entity_id=unit.id,
                snapshot=self._unit_snapshot(unit),
                actor_id=actor_id,
                status="published",
            )
            session.commit()
            result = self._unit_view(session, unit)
            result.update(version=version, status="published")
        self._record(actor_id, "unit.published", unit_id, before=before, after=result, **audit_context)
        return result

    def archive_unit(self, unit_id: UUID, *, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            unit = session.get(Unit, unit_id)
            if unit is None:
                raise ApplicationError("unit_not_found", "Unit was not found", 404)
            before = self._unit_snapshot(unit)
            unit.is_published = False
            version = self._add_revision(
                session,
                entity_type="unit",
                entity_id=unit.id,
                snapshot=self._unit_snapshot(unit),
                actor_id=actor_id,
                status="archived",
            )
            session.commit()
            result = self._unit_view(session, unit)
            result.update(version=version, status="archived")
        self._record(actor_id, "unit.archived", unit_id, before=before, after=result, **audit_context)
        return result

    def create_section(self, unit_id: UUID, *, title: str, section_type: str, position: int, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            if session.get(Unit, unit_id) is None:
                raise ApplicationError("unit_not_found", "Unit was not found", 404)
            section = Section(unit_id=unit_id, title=title.strip(), section_type=section_type, position=position)
            session.add(section)
            session.flush()
            snapshot = self._section_snapshot(section)
            version = self._add_revision(session, entity_type="section", entity_id=section.id, snapshot=snapshot, actor_id=actor_id, status="draft")
            session.commit()
        result = {"id": section.id, **snapshot, "version": version, "status": "draft"}
        self._record(actor_id, "section.created", section.id, after=result, **audit_context)
        return result

    def list_sections(self, unit_id: UUID) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            sections = list(session.scalars(select(Section).where(Section.unit_id == unit_id).order_by(Section.position, Section.id)))
            return [self._versioned_view(session, "section", item.id, self._section_snapshot(item)) for item in sections]

    def update_section(self, section_id: UUID, changes: dict[str, Any], *, expected_version: int, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        allowed = {"title", "section_type", "position"}
        if set(changes) - allowed:
            raise ApplicationError("content_fields_invalid", "Section contains unsupported fields", 422)
        with self._session_factory() as session:
            section = session.get(Section, section_id)
            if section is None:
                raise ApplicationError("section_not_found", "Section was not found", 404)
            self._ensure_version(session, "section", section_id, expected_version)
            before = self._section_snapshot(section)
            for field, value in changes.items():
                setattr(section, field, value.strip() if isinstance(value, str) else value)
            snapshot = self._section_snapshot(section)
            version = self._add_revision(session, entity_type="section", entity_id=section_id, snapshot=snapshot, actor_id=actor_id, status="draft")
            session.commit()
        result = {"id": section_id, **snapshot, "version": version, "status": "draft"}
        self._record(actor_id, "section.updated", section_id, before=before, after=result, **audit_context)
        return result

    def delete_section(self, section_id: UUID, *, actor_id: UUID, **audit_context: Any) -> None:
        with self._session_factory() as session:
            section = session.get(Section, section_id)
            if section is None:
                raise ApplicationError("section_not_found", "Section was not found", 404)
            if session.scalar(select(Activity.id).where(Activity.section_id == section_id).limit(1)) is not None:
                raise ApplicationError("content_has_related_data", "Archive content that has related learning data", 409)
            before = self._section_snapshot(section)
            session.execute(delete(ContentRevision).where(ContentRevision.entity_type == "section", ContentRevision.entity_id == section_id))
            session.delete(section)
            session.commit()
        self._record(actor_id, "section.deleted", section_id, before=before, **audit_context)

    def create_activity(self, section_id: UUID, *, number: str | None, activity_type: str, instruction: str | None, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            if session.get(Section, section_id) is None:
                raise ApplicationError("section_not_found", "Section was not found", 404)
            activity = Activity(section_id=section_id, number=number, activity_type=activity_type, instruction=instruction)
            session.add(activity)
            session.flush()
            snapshot = self._activity_snapshot(activity)
            version = self._add_revision(session, entity_type="activity", entity_id=activity.id, snapshot=snapshot, actor_id=actor_id, status="draft")
            session.commit()
        result = {"id": activity.id, **snapshot, "version": version, "status": "draft"}
        self._record(actor_id, "activity.created", activity.id, after=result, **audit_context)
        return result

    def list_activities(self, section_id: UUID) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            activities = list(session.scalars(select(Activity).where(Activity.section_id == section_id).order_by(Activity.number, Activity.id)))
            return [self._versioned_view(session, "activity", item.id, self._activity_snapshot(item)) for item in activities]

    def update_activity(self, activity_id: UUID, changes: dict[str, Any], *, expected_version: int, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        allowed = {"number", "activity_type", "instruction"}
        if set(changes) - allowed:
            raise ApplicationError("content_fields_invalid", "Activity contains unsupported fields", 422)
        with self._session_factory() as session:
            activity = session.get(Activity, activity_id)
            if activity is None:
                raise ApplicationError("activity_not_found", "Activity was not found", 404)
            self._ensure_version(session, "activity", activity_id, expected_version)
            before = self._activity_snapshot(activity)
            for field, value in changes.items():
                setattr(activity, field, value.strip() if isinstance(value, str) else value)
            snapshot = self._activity_snapshot(activity)
            version = self._add_revision(session, entity_type="activity", entity_id=activity_id, snapshot=snapshot, actor_id=actor_id, status="draft")
            session.commit()
        result = {"id": activity_id, **snapshot, "version": version, "status": "draft"}
        self._record(actor_id, "activity.updated", activity_id, before=before, after=result, **audit_context)
        return result

    def delete_activity(self, activity_id: UUID, *, actor_id: UUID, **audit_context: Any) -> None:
        with self._session_factory() as session:
            activity = session.get(Activity, activity_id)
            if activity is None:
                raise ApplicationError("activity_not_found", "Activity was not found", 404)
            has_fragment = session.scalar(select(SourceFragment.id).where(SourceFragment.activity_id == activity_id).limit(1))
            has_audio = session.scalar(select(AudioTrack.id).where(AudioTrack.activity_id == activity_id).limit(1))
            if has_fragment is not None or has_audio is not None:
                raise ApplicationError("content_has_related_data", "Archive content that has related learning data", 409)
            before = self._activity_snapshot(activity)
            session.execute(delete(ContentRevision).where(ContentRevision.entity_type == "activity", ContentRevision.entity_id == activity_id))
            session.delete(activity)
            session.commit()
        self._record(actor_id, "activity.deleted", activity_id, before=before, **audit_context)

    def create_fragment(
        self,
        *,
        source_document_id: UUID,
        activity_id: UUID,
        pdf_page: int,
        printed_page: int | None,
        normalized_text: str,
        actor_id: UUID,
        **audit_context: Any,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            if session.get(SourceDocument, source_document_id) is None:
                raise ApplicationError("source_document_not_found", "Source document was not found", 404)
            if session.get(Activity, activity_id) is None:
                raise ApplicationError("activity_not_found", "Activity was not found", 404)
            fragment = SourceFragment(
                source_document_id=source_document_id,
                activity_id=activity_id,
                pdf_page=pdf_page,
                printed_page=printed_page,
                region_type="text",
                x=0,
                y=0,
                width=0,
                height=0,
                normalized_text=normalized_text.strip(),
                review_status=ReviewStatus.DRAFT,
                is_published=False,
            )
            session.add(fragment)
            session.flush()
            version = self._add_revision(session, entity_type="fragment", entity_id=fragment.id, snapshot=self._fragment_snapshot(fragment), actor_id=actor_id, status="draft")
            session.commit()
            result = self._fragment_view(fragment, version, "draft")
        self._record(actor_id, "fragment.created", fragment.id, after=result, **audit_context)
        return result

    @staticmethod
    def _fragment_view(fragment: SourceFragment, version: int, status: str) -> dict[str, Any]:
        return {"id": fragment.id, **AdminContentService._fragment_snapshot(fragment), "version": version, "status": status}

    def update_fragment(self, fragment_id: UUID, changes: dict[str, Any], *, expected_version: int, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        allowed = {"pdf_page", "printed_page", "normalized_text", "review_status", "activity_id"}
        if set(changes) - allowed:
            raise ApplicationError("content_fields_invalid", "Fragment contains unsupported fields", 422)
        with self._session_factory() as session:
            fragment = session.get(SourceFragment, fragment_id)
            if fragment is None:
                raise ApplicationError("fragment_not_found", "Fragment was not found", 404)
            self._ensure_version(session, "fragment", fragment_id, expected_version)
            before = self._fragment_snapshot(fragment)
            for field, value in changes.items():
                if field == "review_status":
                    value = ReviewStatus(value)
                setattr(fragment, field, value.strip() if field == "normalized_text" else value)
            fragment.is_published = False
            version = self._add_revision(session, entity_type="fragment", entity_id=fragment.id, snapshot=self._fragment_snapshot(fragment), actor_id=actor_id, status="draft")
            session.commit()
            result = self._fragment_view(fragment, version, "draft")
        self._record(actor_id, "fragment.updated", fragment_id, before=before, after=result, **audit_context)
        return result

    def publish_fragment(self, fragment_id: UUID, *, expected_version: int, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            fragment = session.get(SourceFragment, fragment_id)
            if fragment is None:
                raise ApplicationError("fragment_not_found", "Fragment was not found", 404)
            self._ensure_version(session, "fragment", fragment_id, expected_version)
            if fragment.activity_id is None or fragment.printed_page is None:
                raise ApplicationError("grounding_required", "Unit and printed textbook page are required", 422)
            if fragment.review_status != ReviewStatus.VERIFIED:
                raise ApplicationError("fragment_not_verified", "Verify the fragment before publishing", 422)
            before = self._fragment_snapshot(fragment)
            fragment.is_published = True
            version = self._add_revision(session, entity_type="fragment", entity_id=fragment.id, snapshot=self._fragment_snapshot(fragment), actor_id=actor_id, status="published")
            session.commit()
            result = self._fragment_view(fragment, version, "published")
        self._record(actor_id, "fragment.published", fragment_id, before=before, after=result, **audit_context)
        return result

    def list_fragments(self, activity_id: UUID | None = None) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            query = select(SourceFragment).order_by(SourceFragment.pdf_page, SourceFragment.id)
            if activity_id is not None:
                query = query.where(SourceFragment.activity_id == activity_id)
            fragments = list(session.scalars(query))
            return [self._versioned_view(session, "fragment", item.id, self._fragment_snapshot(item)) for item in fragments]

    def archive_fragment(self, fragment_id: UUID, *, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            fragment = session.get(SourceFragment, fragment_id)
            if fragment is None:
                raise ApplicationError("fragment_not_found", "Fragment was not found", 404)
            before = self._fragment_snapshot(fragment)
            fragment.is_published = False
            snapshot = self._fragment_snapshot(fragment)
            version = self._add_revision(session, entity_type="fragment", entity_id=fragment_id, snapshot=snapshot, actor_id=actor_id, status="archived")
            session.commit()
        result = {"id": fragment_id, **snapshot, "version": version, "status": "archived"}
        self._record(actor_id, "fragment.archived", fragment_id, before=before, after=result, **audit_context)
        return result

    def delete_fragment(self, fragment_id: UUID, *, actor_id: UUID, **audit_context: Any) -> None:
        with self._session_factory() as session:
            fragment = session.get(SourceFragment, fragment_id)
            if fragment is None:
                raise ApplicationError("fragment_not_found", "Fragment was not found", 404)
            in_question = session.scalar(select(QuestionSource.id).where(QuestionSource.source_fragment_id == fragment_id).limit(1))
            in_card = session.scalar(select(Flashcard.id).where(Flashcard.source_fragment_id == fragment_id).limit(1))
            in_audio = session.scalar(select(AudioTrack.id).where(AudioTrack.transcript_fragment_id == fragment_id).limit(1))
            if in_question is not None or in_card is not None or in_audio is not None:
                raise ApplicationError("content_has_related_data", "Archive content that has related learning data", 409)
            before = self._fragment_snapshot(fragment)
            session.execute(delete(ContentRevision).where(ContentRevision.entity_type == "fragment", ContentRevision.entity_id == fragment_id))
            session.delete(fragment)
            session.commit()
        self._record(actor_id, "fragment.deleted", fragment_id, before=before, **audit_context)

    def _versioned_view(self, session: Session, entity_type: str, entity_id: UUID, snapshot: dict[str, Any]) -> dict[str, Any]:
        version = self._current_version(session, entity_type, entity_id)
        status = session.scalar(select(ContentRevision.status).where(ContentRevision.entity_type == entity_type, ContentRevision.entity_id == entity_id).order_by(ContentRevision.version.desc()).limit(1)) or "draft"
        return {"id": entity_id, **snapshot, "version": version, "status": status}

    def preview(self, entity_type: str, entity_id: UUID) -> dict[str, Any]:
        model_and_snapshot = {
            "unit": (Unit, self._unit_snapshot),
            "section": (Section, self._section_snapshot),
            "activity": (Activity, self._activity_snapshot),
            "fragment": (SourceFragment, self._fragment_snapshot),
        }
        if entity_type not in model_and_snapshot:
            raise ApplicationError("content_type_invalid", "Content type cannot be previewed", 422)
        model, snapshotter = model_and_snapshot[entity_type]
        with self._session_factory() as session:
            entity = session.get(model, entity_id)
            if entity is None:
                raise ApplicationError(f"{entity_type}_not_found", f"{entity_type.title()} was not found", 404)
            return self._versioned_view(session, entity_type, entity_id, snapshotter(entity))

    def versions(self, entity_type: str, entity_id: UUID) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            revisions = list(session.scalars(select(ContentRevision).where(ContentRevision.entity_type == entity_type, ContentRevision.entity_id == entity_id).order_by(ContentRevision.version.desc())))
            return [{"id": item.id, "version": item.version, "status": item.status, "snapshot": item.snapshot, "created_at": item.created_at, "published_at": item.published_at} for item in revisions]

    def restore(self, entity_type: str, entity_id: UUID, *, version: int, actor_id: UUID, **audit_context: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            revision = session.scalar(select(ContentRevision).where(ContentRevision.entity_type == entity_type, ContentRevision.entity_id == entity_id, ContentRevision.version == version))
            if revision is None:
                raise ApplicationError("content_revision_not_found", "Content revision was not found", 404)
            if entity_type == "unit":
                entity = session.get(Unit, entity_id)
                if entity is None:
                    raise ApplicationError("unit_not_found", "Unit was not found", 404)
                before = self._unit_snapshot(entity)
                entity.number = int(revision.snapshot["number"])
                entity.title = str(revision.snapshot["title"])
                entity.is_published = False
                snapshot = self._unit_snapshot(entity)
            elif entity_type == "fragment":
                entity = session.get(SourceFragment, entity_id)
                if entity is None:
                    raise ApplicationError("fragment_not_found", "Fragment was not found", 404)
                before = self._fragment_snapshot(entity)
                for field in ("pdf_page", "printed_page", "normalized_text", "review_status"):
                    if field in revision.snapshot:
                        setattr(entity, field, revision.snapshot[field])
                entity.is_published = False
                snapshot = self._fragment_snapshot(entity)
            else:
                raise ApplicationError("content_type_invalid", "Content type cannot be restored", 422)
            new_version = self._add_revision(session, entity_type=entity_type, entity_id=entity_id, snapshot=snapshot, actor_id=actor_id, status="draft")
            session.commit()
            result = {"id": entity_id, **snapshot, "version": new_version, "status": "draft"}
        self._record(actor_id, f"{entity_type}.restored", entity_id, before=before, after=result, **audit_context)
        return result

    def delete_unit(self, unit_id: UUID, *, actor_id: UUID, **audit_context: Any) -> None:
        with self._session_factory() as session:
            unit = session.get(Unit, unit_id)
            if unit is None:
                raise ApplicationError("unit_not_found", "Unit was not found", 404)
            if session.scalar(select(Section.id).where(Section.unit_id == unit_id).limit(1)) is not None:
                raise ApplicationError("content_has_related_data", "Archive content that has related learning data", 409)
            before = self._unit_snapshot(unit)
            session.execute(delete(ContentRevision).where(ContentRevision.entity_type == "unit", ContentRevision.entity_id == unit_id))
            session.delete(unit)
            session.commit()
        self._record(actor_id, "unit.deleted", unit_id, before=before, **audit_context)

    def _record(self, actor_id: UUID, action: str, entity_id: UUID, *, before: dict[str, Any] | None = None, after: dict[str, Any] | None = None, **context: Any) -> None:
        self._audit.record(actor_id=actor_id, action=action, entity_type=action.split(".", 1)[0], entity_id=entity_id, before=before, after=after, request_id=context.get("request_id"), ip_address=context.get("ip_address"), platform=context.get("platform"))
