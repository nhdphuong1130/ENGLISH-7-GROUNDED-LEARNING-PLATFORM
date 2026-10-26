from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from minio import Minio
from neo4j import GraphDatabase
from difflib import SequenceMatcher
from sqlalchemy import select

from english7.api.errors import ApplicationError
from english7.core.settings import Settings
from english7.db.models import (
    Activity,
    AudioTrack,
    ReviewStatus,
    Section,
    SourceFragment,
    Unit,
)
from english7.db.session import get_session_factory
from english7.modules.ai.openrouter import (
    OpenRouterEmbedder,
    OpenRouterProvider,
    UrllibJSONClient,
)
from english7.modules.image_uploads.repository import SQLAlchemyImageUploadRepository
from english7.modules.image_uploads.service import ImageUploadService
from english7.modules.knowledge.neo4j_repository import Neo4jKnowledgeRepository
from english7.modules.media.storage import MinioUploadStorage
from english7.modules.quizzes.blueprint import BlueprintSelector
from english7.modules.quizzes.domain import GeneratedQuestion
from english7.modules.quizzes.repository import (
    SQLAlchemyBlueprintRepository,
    SQLAlchemyQuizRepository,
)
from english7.modules.quizzes.service import QuizService
from english7.modules.quizzes.validator import QuestionValidator
from english7.modules.retrieval.service import RetrievalService
from english7.modules.tutor.conversations import (
    ConversationHistoryService,
    SQLAlchemyConversationRepository,
)
from english7.modules.tutor.service import TutorService


class SequenceSimilarity:
    def compare(self, left: str, right: str) -> float:
        return SequenceMatcher(None, left.lower(), right.lower()).ratio()


class GroundedQuestionGenerator:
    _CORRECT_OPTIONS = ("True", "False", "Not given")

    def __init__(self, session_factory, *, ai_provider=None) -> None:
        self._session_factory = session_factory
        self._ai_provider = ai_provider

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove markdown images, [image:...] refs, HTML tags, normalize whitespace."""
        import re
        # Remove markdown images: ![alt](url)
        text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", text)
        # Remove [image:...] style references
        text = re.sub(r"\[image:[^\]]*\]", "", text)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _is_suitable_fragment(text: str) -> bool:
        """Return True only for fragments suitable as True/False/Not given questions.

        Unsuitable fragments:
        - Contain markdown images or [image:...] refs
        - Contain raw Options lists (exercise format)
        - Contain matching arrows (->)
        - Too short to be meaningful
        - Pure numbered lists with no prose
        """
        import re
        # Has markdown image syntax
        if re.search(r"!\[[^\]]*\]\([^\)]*\)", text):
            return False
        # Has [image:...] style reference
        if re.search(r"\[image:[^\]]*\]", text):
            return False
        # Has raw Options list (exercise instructions)
        if re.search(r"Options:\s*\[", text):
            return False
        # Has matching exercise arrows
        if re.search(r"\s->\s", text):
            return False
        # Too short
        if len(text.strip()) < 40:
            return False
        # Pure numbered list without enough prose
        lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        if lines and all(re.match(r"^\d+\.", ln) for ln in lines):
            return False
        return True

    def generate(
        self, *, duration_minutes: int, difficulty: str, question_count: int, mode: str = "mixed"
    ) -> list[GeneratedQuestion]:
        with self._session_factory() as session:
            # Query listening audio tracks and activities if mode requires audio
            audio_url: str | None = None
            audio_title: str | None = None
            listening_frags: list[SourceFragment] = []

            if mode in ("listening", "mixed"):
                try:
                    stmt = (
                        select(SourceFragment, AudioTrack, Activity, Section, Unit)
                        .join(Activity, SourceFragment.activity_id == Activity.id)
                        .join(AudioTrack, AudioTrack.activity_id == Activity.id)
                        .join(Section, Activity.section_id == Section.id)
                        .join(Unit, Section.unit_id == Unit.id)
                        .where(
                            SourceFragment.review_status == ReviewStatus.VERIFIED.value,
                            SourceFragment.is_published == True,
                        )
                    )
                    records = session.execute(stmt).all()
                    preferred = [
                        r
                        for r in records
                        if "skills 2" in r[3].title.lower()
                        or "listening" in (r[2].instruction or "").lower()
                    ]
                    pool = preferred if preferred else records
                    if pool:
                        by_track = {}
                        for f, tr, ac, se, un in pool:
                            by_track.setdefault((tr.track_number, un.number, un.title), []).append(f)
                        if by_track:
                            import random
                            chosen_track_key = random.choice(list(by_track.keys()))
                            tr_num, un_num, un_title = chosen_track_key
                            audio_url = f"/api/v1/media/audio/{tr_num}"
                            audio_title = f"Unit {un_num}: {un_title} (Track {tr_num})"
                            chosen_frags = by_track[chosen_track_key]
                            other_frags = [
                                r[0]
                                for r in pool
                                if r[1].track_number != tr_num
                                and self._is_suitable_fragment(r[0].normalized_text)
                            ]
                            listening_frags = chosen_frags + other_frags
                except Exception:
                    pass

            all_fragments = session.scalars(
                select(SourceFragment).where(
                    SourceFragment.review_status == ReviewStatus.VERIFIED.value,
                    SourceFragment.is_published == True,
                )
            ).all()
            if not all_fragments and not listening_frags:
                raise ApplicationError(
                    "insufficient_sources",
                    "Not enough verified textbook fragments to generate quiz",
                    503,
                )

            # Filter reading fragments suitable for True/False/Not given questions
            reading_fragments = [
                f for f in all_fragments
                if self._is_suitable_fragment(f.normalized_text)
            ]
            if not reading_fragments:
                reading_fragments = list(all_fragments) if all_fragments else listening_frags

            # Determine how many questions are listening questions
            if mode == "listening":
                listening_count = question_count if listening_frags else 0
            elif mode == "mixed" and listening_frags:
                listening_count = min(len(listening_frags), max(1, question_count // 2))
            else:
                listening_count = 0

            # Shuffle fragments to ensure diverse questions across textbook units
            import random
            shuffled_listening = list(listening_frags)
            random.shuffle(shuffled_listening)
            shuffled_reading = list(reading_fragments)
            random.shuffle(shuffled_reading)

            # Build question item specs: (frag, is_listening)
            question_specs = []
            for i in range(question_count):
                if i < listening_count and shuffled_listening:
                    frag = shuffled_listening[i % len(shuffled_listening)]
                    question_specs.append((frag, True))
                else:
                    frag = shuffled_reading[i % len(shuffled_reading)]
                    question_specs.append((frag, False))

            items = []
            for i, (frag, is_listen) in enumerate(question_specs):
                clean = self._clean_text(frag.normalized_text)
                target = self._CORRECT_OPTIONS[i % len(self._CORRECT_OPTIONS)]
                items.append((frag, clean, target, is_listen))

            # Try one batch AI call for all questions
            ai_results: list[tuple[str, str] | None] = [None] * question_count
            if self._ai_provider is not None:
                try:
                    ai_items = [(f, c, t) for (f, c, t, _) in items]
                    ai_results = self._ai_generate_batch(ai_items)
                except Exception:
                    pass

            questions: list[GeneratedQuestion] = []
            for i, (frag, clean, target, is_listen) in enumerate(items):
                ai = ai_results[i] if ai_results else None
                if ai is not None:
                    prompt, correct = ai
                else:
                    prompt, correct = self._make_fallback(
                        clean, i, is_listening=is_listen, audio_title=audio_title
                    )
                answer: dict[str, Any] = {
                    "options": list(self._CORRECT_OPTIONS),
                    "correct": correct,
                }
                if is_listen and audio_url:
                    answer["audio_url"] = audio_url
                    answer["audio_title"] = audio_title
                questions.append(
                    GeneratedQuestion(
                        prompt=prompt,
                        answer=answer,
                        source_fragment_ids=(frag.id,),
                    )
                )
            return questions

    def _make_fallback(
        self,
        clean_text: str,
        index: int,
        is_listening: bool = False,
        audio_title: str | None = None,
    ) -> tuple[str, str]:
        """Deterministic fallback: cycle True/False/Not given, use clean text statement."""
        import re
        correct = self._CORRECT_OPTIONS[index % len(self._CORRECT_OPTIONS)]

        dialogue = [
            ln.strip()
            for ln in clean_text.splitlines()
            if ":" in ln and len(ln.strip()) > 15
        ]
        if dialogue:
            statement = dialogue[index % len(dialogue)]
        else:
            sentences = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", clean_text)
                if len(s.strip()) > 20 and not s.strip().startswith("http")
            ]
            if sentences:
                statement = sentences[index % len(sentences)]
            else:
                statement = clean_text[:120].strip()

        if len(statement) > 120:
            last_space = statement[:120].rfind(" ")
            if last_space > 40:
                statement = statement[:last_space]
            else:
                statement = statement[:120]
            statement += "..."

        prompt = f'"{statement}"'
        return prompt, correct

    def _ai_generate_batch(
        self,
        items: list[tuple[Any, str, str]],
    ) -> list[tuple[str, str] | None]:
        """Generate all questions in ONE AI call to avoid rate-limit.

        Each item is (fragment, clean_text, target_answer).
        Returns list of (prompt, correct) or None per item on parse failure.
        """
        import json as _json
        from urllib.request import Request as _Req, urlopen as _open

        api_key = (
            self._ai_provider._api_key.get_secret_value()
            if hasattr(self._ai_provider._api_key, "get_secret_value")
            else str(self._ai_provider._api_key or "")
        )
        if not api_key or "replace" in api_key.lower():
            return [None] * len(items)
        model = self._ai_provider._model
        endpoint = self._ai_provider._endpoint
        timeout = min(self._ai_provider._timeout, 60)

        type_instructions = {
            "True": "Write a statement DIRECTLY confirmed by the passage (answer: True).",
            "False": "Write a statement that CONTRADICTS the passage by changing a key fact (answer: False).",
            "Not given": "Write a statement about a related topic NOT mentioned in the passage (answer: Not given).",
        }

        passages_json = []
        for idx, (_frag, clean, target) in enumerate(items):
            passages_json.append({
                "id": idx,
                "passage": clean[:300],
                "instruction": type_instructions.get(target, type_instructions["True"]),
                "required_answer": target,
            })

        system = (
            "You are an English 7 quiz item writer. "
            "For each passage, follow the instruction to write exactly one statement. "
            "Ensure every statement is completely unique and differs in topic or subject from others. "
            "Return a JSON object with key 'questions' containing an array. "
            "Each array element: {\"id\": <number>, \"statement\": \"...\", \"correct\": \"True|False|Not given\"}. "
            "The 'correct' field MUST match the required_answer for each passage."
        )
        user = (
            "Generate quiz questions for each passage below.\n\n"
            + _json.dumps({"passages": passages_json}, ensure_ascii=False)
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        body = _json.dumps(payload).encode("utf-8")
        req = _Req(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with _open(req, timeout=timeout) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        content = _json.loads(data["choices"][0]["message"]["content"])
        raw_questions = content.get("questions", [])

        # Map results back by id
        result_map: dict[int, tuple[str, str]] = {}
        for item in raw_questions:
            try:
                idx = int(item["id"])
                statement = str(item.get("statement", "")).strip()
                correct = str(item.get("correct", "True")).strip()
                if correct not in self._CORRECT_OPTIONS:
                    correct = self._CORRECT_OPTIONS[idx % len(self._CORRECT_OPTIONS)]
                if statement:
                    prompt = f'"{statement}"'
                    result_map[idx] = (prompt, correct)
            except (KeyError, ValueError, TypeError):
                continue

        return [result_map.get(i) for i in range(len(items))]


@dataclass(slots=True)
class RuntimeResources:
    neo4j_driver: Any

    def close(self) -> None:
        close = getattr(self.neo4j_driver, "close", None)
        if close is not None:
            close()


def _complete(settings: Settings) -> bool:
    required = (
        settings.database_url,
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
        settings.neo4j_vector_index,
        settings.embedding_dimensions,
        settings.retrieval_top_k,
        settings.retrieval_min_score,
        settings.retrieval_graph_depth,
        settings.retrieval_rrf_constant,
        settings.retrieval_max_context_fragments,
        settings.retrieval_allowed_units,
        settings.openrouter_api_key,
        settings.openrouter_endpoint,
        settings.openrouter_model,
        settings.openrouter_timeout_seconds,
        settings.openrouter_embedding_endpoint,
        settings.openrouter_embedding_model,
        settings.upload_max_bytes,
        settings.image_upload_prefix,
        settings.image_upload_retention_minutes,
        settings.image_upload_allowed_types,
        settings.tutor_query_max_characters,
        settings.minio_upload_bucket,
    )
    return all(value is not None and value != "" for value in required)


def configure_runtime(
    app,
    settings: Settings,
    *,
    session_factory=None,
    neo4j_driver=None,
    minio_client=None,
    http_client=None,
) -> RuntimeResources | None:
    if not _complete(settings):
        return None
    sessions = session_factory or (lambda: get_session_factory()())
    if neo4j_driver is None:
        neo4j_driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(
                settings.neo4j_user,
                settings.neo4j_password.get_secret_value(),
            ),
        )
    if minio_client is None:
        if not all(
            (
                settings.minio_endpoint,
                settings.minio_access_key,
                settings.minio_secret_key,
            )
        ):
            raise RuntimeError("MinIO runtime settings are incomplete")
        endpoint = settings.minio_endpoint
        secure = endpoint.startswith("https://")
        endpoint = endpoint.removeprefix("https://").removeprefix("http://")
        minio_client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key.get_secret_value(),
            secure=secure,
        )
    http = http_client or UrllibJSONClient()
    uploads = SQLAlchemyImageUploadRepository(sessions)
    app.state.image_upload_service = ImageUploadService(
        repository=uploads,
        storage=MinioUploadStorage(
            minio_client, bucket=settings.minio_upload_bucket
        ),
        maximum_bytes=settings.upload_max_bytes,
        allowed_media_types=tuple(
            item.strip()
            for item in settings.image_upload_allowed_types.split(",")
            if item.strip()
        ),
        object_prefix=settings.image_upload_prefix,
        retention=timedelta(minutes=settings.image_upload_retention_minutes),
    )
    repository = Neo4jKnowledgeRepository(
        neo4j_driver,
        vector_index_name=settings.neo4j_vector_index,
        embedding_dimensions=settings.embedding_dimensions,
        graph_result_limit=settings.retrieval_top_k,
    )
    key_str = (
        settings.openrouter_api_key.get_secret_value()
        if hasattr(settings.openrouter_api_key, "get_secret_value")
        else str(settings.openrouter_api_key or "")
    )
    if settings.embedding_dimensions == 384 or not key_str or "replace" in key_str.lower():
        from english7.modules.knowledge.fastembed_service import FastEmbedService

        embedder = FastEmbedService(cache_dir=settings.embedding_cache_dir)
    else:
        embedder = OpenRouterEmbedder(
            http=http,
            api_key=settings.openrouter_api_key,
            endpoint=settings.openrouter_embedding_endpoint,
            model=settings.openrouter_embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.openrouter_timeout_seconds,
        )
    retrieval = RetrievalService(
        repository=repository,
        embedder=embedder,
        allowed_units=frozenset(
            int(value.strip())
            for value in settings.retrieval_allowed_units.split(",")
            if value.strip()
        ),
        top_k=settings.retrieval_top_k,
        min_vector_score=settings.retrieval_min_score,
        graph_depth=settings.retrieval_graph_depth,
        rrf_constant=settings.retrieval_rrf_constant,
        max_context_fragments=settings.retrieval_max_context_fragments,
    )
    provider = OpenRouterProvider(
        http=http,
        api_key=settings.openrouter_api_key,
        endpoint=settings.openrouter_endpoint,
        model=settings.openrouter_model,
        timeout_seconds=settings.openrouter_timeout_seconds,
    )
    app.state.pronunciation_provider = provider
    app.state.tutor_service = TutorService(
        retrieval,
        provider,
        uploads=uploads,
        conversations=ConversationHistoryService(
            SQLAlchemyConversationRepository(sessions)
        ),
        maximum_query_characters=settings.tutor_query_max_characters,
    )
    blueprint_repo = SQLAlchemyBlueprintRepository(sessions)
    quiz_repo = SQLAlchemyQuizRepository(sessions)
    selector = BlueprintSelector(blueprint_repo)
    validator = QuestionValidator(
        SequenceSimilarity(),
        duplicate_threshold=settings.quiz_duplicate_threshold or 0.85,
    )
    generator = GroundedQuestionGenerator(sessions, ai_provider=provider)
    app.state.quiz_service = QuizService(
        selector=selector,
        generator=generator,
        validator=validator,
        repository=quiz_repo,
        max_audio_plays=settings.quiz_max_audio_plays or 2,
    )
    from english7.modules.knowledge.gap_service import KnowledgeGapService

    app.state.knowledge_gap_service = KnowledgeGapService(
        sessions,
        neo4j_driver=neo4j_driver,
        neo4j_database=getattr(settings, "neo4j_database", None),
    )
    return RuntimeResources(neo4j_driver)
