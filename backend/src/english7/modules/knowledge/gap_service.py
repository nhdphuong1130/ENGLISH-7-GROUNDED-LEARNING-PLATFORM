from dataclasses import dataclass
from typing import Any
from uuid import UUID

from neo4j import Driver
from sqlalchemy import select

from english7.db.models import (
    Activity,
    QuestionSource,
    QuizQuestion,
    Section,
    SourceFragment,
    StudentAnswer,
    TestAttempt,
    Unit,
)


@dataclass(frozen=True)
class KnowledgeGapItem:
    concept_key: str
    concept_name: str
    category: str
    unit_number: int
    unit_title: str
    mastery_score: float
    total_attempts: int
    incorrect_count: int
    summary: str
    textbook_citation: str
    suggested_prompt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_key": self.concept_key,
            "concept_name": self.concept_name,
            "category": self.category,
            "unit_number": self.unit_number,
            "unit_title": self.unit_title,
            "mastery_score": round(self.mastery_score, 2),
            "total_attempts": self.total_attempts,
            "incorrect_count": self.incorrect_count,
            "summary": self.summary,
            "textbook_citation": self.textbook_citation,
            "suggested_prompt": self.suggested_prompt,
        }


@dataclass(frozen=True)
class KnowledgeGapAnalysis:
    total_tested_concepts: int
    weak_concepts_count: int
    average_mastery: float
    gaps: list[KnowledgeGapItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tested_concepts": self.total_tested_concepts,
            "weak_concepts_count": self.weak_concepts_count,
            "average_mastery": round(self.average_mastery, 2),
            "gaps": [g.to_dict() for g in self.gaps],
        }


class KnowledgeGapService:
    def __init__(
        self,
        session_factory,
        neo4j_driver: Driver | None = None,
        neo4j_database: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._driver = neo4j_driver
        self._database = neo4j_database

    def diagnose_gaps(self, user_id: UUID) -> KnowledgeGapAnalysis:
        with self._session_factory() as session:
            stmt = (
                select(
                    StudentAnswer.question_id,
                    StudentAnswer.is_correct,
                    QuestionSource.source_fragment_id,
                    SourceFragment.pdf_page,
                    SourceFragment.printed_page,
                    Unit.number.label("unit_number"),
                    Unit.title.label("unit_title"),
                )
                .join(TestAttempt, StudentAnswer.test_attempt_id == TestAttempt.id)
                .join(QuizQuestion, StudentAnswer.question_id == QuizQuestion.id)
                .outerjoin(QuestionSource, QuizQuestion.id == QuestionSource.question_id)
                .outerjoin(SourceFragment, QuestionSource.source_fragment_id == SourceFragment.id)
                .outerjoin(Activity, SourceFragment.activity_id == Activity.id)
                .outerjoin(Section, Activity.section_id == Section.id)
                .outerjoin(Unit, Section.unit_id == Unit.id)
                .where(TestAttempt.user_id == user_id, TestAttempt.status == "submitted")
            )
            rows = session.execute(stmt).all()

        if not rows:
            return KnowledgeGapAnalysis(
                total_tested_concepts=0,
                weak_concepts_count=0,
                average_mastery=1.0,
                gaps=[],
            )

        fragment_ids = [str(r.source_fragment_id) for r in rows if r.source_fragment_id is not None]
        neo4j_mapping: dict[str, dict[str, Any]] = {}

        if self._driver is not None and fragment_ids:
            try:
                with self._driver.session(database=self._database) as neo_sess:
                    query = """
                    UNWIND $fids AS fid
                    MATCH (f:SourceFragment {sql_id: fid})
                    OPTIONAL MATCH (g:GrammarRule)-[:TEACHES|PRACTICES]->(f)
                    OPTIONAL MATCH (v:Vocabulary)-[:EXPLAINS]->(f)
                    OPTIONAL MATCH (u:Unit)-[:HAS_SECTION]->()-[:HAS_ACTIVITY]->()-[:HAS_SOURCE]->(f)
                    RETURN fid,
                           g.id AS grammar_id, g.name AS grammar_name, g.unit_number AS grammar_unit, g.explanation_vi AS grammar_explanation,
                           v.word AS vocab_word, v.ipa AS vocab_ipa, v.example AS vocab_example,
                           u.number AS unit_num, u.title AS unit_title
                    """
                    records = neo_sess.run(query, {"fids": list(set(fragment_ids))}).data()
                    for rec in records:
                        fid = rec.get("fid")
                        if not fid:
                            continue
                        if rec.get("concept_id"):
                            neo4j_mapping[fid] = {
                                "concept_id": rec["concept_id"],
                                "concept_name": rec.get("concept_name"),
                                "category": rec.get("category", "grammar"),
                                "unit_number": rec.get("unit_num"),
                                "unit_title": rec.get("unit_title"),
                                "explanation": rec.get("explanation"),
                            }
                        elif rec.get("grammar_id"):
                            neo4j_mapping[fid] = {
                                "concept_id": rec["grammar_id"],
                                "concept_name": rec.get("grammar_name") or rec["grammar_id"],
                                "category": "grammar",
                                "unit_number": rec.get("grammar_unit") or rec.get("unit_num"),
                                "unit_title": rec.get("unit_title"),
                                "explanation": rec.get("grammar_explanation"),
                            }
                        elif rec.get("vocab_word"):
                            word = rec["vocab_word"]
                            neo4j_mapping[fid] = {
                                "concept_id": f"vocab-{word}",
                                "concept_name": f"Từ vựng: {word} {rec.get('vocab_ipa') or ''}".strip(),
                                "category": "vocabulary",
                                "unit_number": rec.get("unit_num"),
                                "unit_title": rec.get("unit_title"),
                                "explanation": rec.get("vocab_example") or f"Từ vựng '{word}' trong bài học.",
                            }
            except Exception:
                pass

        # Group attempts by concept
        concept_groups: dict[str, list[Any]] = {}
        concept_metadata: dict[str, dict[str, Any]] = {}

        for row in rows:
            fid_str = str(row.source_fragment_id) if row.source_fragment_id is not None else None
            meta = neo4j_mapping.get(fid_str) if fid_str else None

            if meta and meta.get("concept_id"):
                cid = meta["concept_id"]
                cname = meta.get("concept_name") or cid
                cat = meta.get("category") or "grammar"
                unit_num = meta.get("unit_number") or row.unit_number or 1
                unit_title = meta.get("unit_title") or row.unit_title or f"Unit {unit_num}"
                expl = meta.get("explanation") or f"Quy tắc và kiến thức trọng tâm bài học {unit_num}."
            else:
                unit_num = row.unit_number or 1
                unit_title = row.unit_title or f"Unit {unit_num}"
                cid = f"unit-{unit_num}"
                cname = f"Chủ điểm Unit {unit_num}: {unit_title}"
                cat = "topic"
                expl = f"Kiến thức tổng hợp trọng tâm trong Unit {unit_num} ({unit_title})."

            concept_groups.setdefault(cid, []).append(row)
            if cid not in concept_metadata:
                page = row.printed_page or row.pdf_page or (unit_num * 8)
                concept_metadata[cid] = {
                    "concept_name": cname,
                    "category": cat,
                    "unit_number": unit_num,
                    "unit_title": unit_title,
                    "explanation": expl,
                    "page": page,
                }

        items: list[KnowledgeGapItem] = []
        all_masteries: list[float] = []

        for cid, group in concept_groups.items():
            meta = concept_metadata[cid]
            total_attempts = len(group)
            incorrect_count = sum(1 for r in group if not r.is_correct)
            correct_count = total_attempts - incorrect_count
            mastery = correct_count / total_attempts if total_attempts > 0 else 1.0
            all_masteries.append(mastery)

            # Mark as weak if mastery < 70% or at least 2 wrong answers
            is_weak = mastery < 0.70 or incorrect_count >= 2
            if is_weak:
                citation = f"SGK Tiếng Anh 7 Unit {meta['unit_number']}, Trang {meta['page']}"
                prompt = (
                    f"Giải thích chi tiết về {meta['concept_name']} trong Unit {meta['unit_number']} ({meta['unit_title']}) giúp em."
                )
                items.append(
                    KnowledgeGapItem(
                        concept_key=cid,
                        concept_name=meta["concept_name"],
                        category=meta["category"],
                        unit_number=meta["unit_number"],
                        unit_title=meta["unit_title"],
                        mastery_score=mastery,
                        total_attempts=total_attempts,
                        incorrect_count=incorrect_count,
                        summary=meta["explanation"],
                        textbook_citation=citation,
                        suggested_prompt=prompt,
                    )
                )

        items.sort(key=lambda x: (x.mastery_score, -x.incorrect_count))
        avg_mastery = sum(all_masteries) / len(all_masteries) if all_masteries else 1.0

        return KnowledgeGapAnalysis(
            total_tested_concepts=len(concept_groups),
            weak_concepts_count=len(items),
            average_mastery=avg_mastery,
            gaps=items,
        )
