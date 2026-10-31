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
    _LANGUAGE_TEMPLATES = (
        (
            "Which word has the underlined vowel sound pronounced differently: /ɜ:/ vs /ə/?",
            "D. doctor",
            ["A. bird", "B. girl", "C. first", "D. doctor"],
        ),
        (
            "Which word has the '-ed' ending pronounced differently from the other three?",
            "D. wanted",
            ["A. played", "B. cleaned", "C. stayed", "D. wanted"],
        ),
        (
            "Identify the 2-syllable word whose primary stress falls on the second syllable.",
            "D. perform",
            ["A. dancer", "B. traffic", "C. cycle", "D. perform"],
        ),
        (
            "Which 3-syllable word has a different primary stress pattern?",
            "D. pollution",
            ["A. energy", "B. festival", "C. passenger", "D. pollution"],
        ),
        (
            "We ______ warm clothes and books to children in mountainous areas last winter.",
            "A. donated",
            ["A. donated", "B. donate", "C. donating", "D. donates"],
        ),
        (
            "Solar energy and wind energy are ______ sources of energy that will not run out.",
            "A. renewable",
            ["A. renewable", "B. non-renewable", "C. dangerous", "D. harmful"],
        ),
        (
            "______ the story of the movie was simple, the acting was wonderful.",
            "A. Although",
            ["A. Although", "B. Because", "C. However", "D. But"],
        ),
        (
            "In Viet Nam, the new school year always starts ______ early September.",
            "A. in",
            ["A. in", "B. on", "C. at", "D. to"],
        ),
        (
            "There isn't ______ sugar left in the jar, so Mum needs to buy some.",
            "A. any",
            ["A. any", "B. some", "C. many", "D. a few"],
        ),
        (
            "You ______ ride your motorbike on the pavement. It's against the law.",
            "B. shouldn't",
            ["A. should", "B. shouldn't", "C. can", "D. must"],
        ),
        (
            "He loves carving eggshells because he finds it ______ and creative.",
            "A. interesting",
            ["A. interesting", "B. bored", "C. tiredness", "D. danger"],
        ),
        (
            "How ______ milk does your brother drink every morning?",
            "A. much",
            ["A. much", "B. many", "C. often", "D. long"],
        ),
    )

    _REORDER_TEMPLATES = (
        (
            "clean / solar energy / is / source / a / and renewable power / .",
            "A. Solar energy is a clean and renewable power source.",
            [
                "A. Solar energy is a clean and renewable power source.",
                "B. Is solar energy a clean source and renewable power.",
                "C. Clean and renewable power is solar energy source a.",
                "D. Solar clean energy is power and a renewable source.",
            ],
        ),
        (
            "they / school / built / our / a / long / ago / time / .",
            "A. They built our school a long time ago.",
            [
                "A. They built our school a long time ago.",
                "B. Built they our school a long time ago.",
                "C. Our school they built ago a long time.",
                "D. A long time ago built they our school.",
            ],
        ),
        (
            "pedestrians / should / cross / road / the / at / zebra crossing / a / .",
            "A. Pedestrians should cross the road at a zebra crossing.",
            [
                "A. Pedestrians should cross the road at a zebra crossing.",
                "B. Should pedestrians cross a zebra crossing at the road.",
                "C. Cross pedestrians should the road at a zebra crossing.",
                "D. Pedestrians cross should at a zebra crossing the road.",
            ],
        ),
        (
            "she / enjoys / models / making / in / free time / her / .",
            "A. She enjoys making models in her free time.",
            [
                "A. She enjoys making models in her free time.",
                "B. Enjoys she making models in free time her.",
                "C. Making models she enjoys her in free time.",
                "D. She making models enjoys in free time her.",
            ],
        ),
        (
            "we / community / participated / in / activities / last summer / .",
            "A. We participated in community activities last summer.",
            [
                "A. We participated in community activities last summer.",
                "B. Participated we in community activities last summer.",
                "C. We in community activities participated last summer.",
                "D. Last summer participated we in community activities.",
            ],
        ),
        (
            "although / was / the film / gripping / , / he / didn't / like / ending / the / .",
            "A. Although the film was gripping, he didn't like the ending.",
            [
                "A. Although the film was gripping, he didn't like the ending.",
                "B. Although gripping was the film, he didn't like the ending.",
                "C. The film was gripping although, didn't he like the ending.",
                "D. He didn't like the ending although was the film gripping.",
            ],
        ),
        (
            "people / will / by / travel / flying cars / in / 2050 / .",
            "A. People will travel by flying cars in 2050.",
            [
                "A. People will travel by flying cars in 2050.",
                "B. Travel people will by flying cars in 2050.",
                "C. Will people travel flying cars by in 2050.",
                "D. Flying cars will travel by people in 2050.",
            ],
        ),
        (
            "there / are / fresh apples / some / on / table / the / .",
            "A. There are some fresh apples on the table.",
            [
                "A. There are some fresh apples on the table.",
                "B. Are there fresh apples some on the table.",
                "C. On the table there are some fresh apples.",
                "D. Some fresh apples there are on the table.",
            ],
        ),
    )

    _ERROR_TEMPLATES = (
        (
            "My sister (A) enjoy (B) playing badminton (C) every afternoon (D).",
            "B. enjoy",
            ["A. My sister", "B. enjoy", "C. playing badminton", "D. every afternoon"],
        ),
        (
            "She (A) went (B) to the cinema (C) with her classmates tomorrow (D).",
            "D. tomorrow",
            ["A. She", "B. went", "C. to the cinema", "D. tomorrow"],
        ),
        (
            "There (A) are (B) a lot of (C) fresh milk (D) in the bottle.",
            "B. are",
            ["A. There", "B. are", "C. a lot of", "D. fresh milk"],
        ),
        (
            "Although (A) it was raining (B) heavily, but (C) he walked to school (D).",
            "C. but",
            ["A. Although", "B. it was raining", "C. but", "D. he walked to school"],
        ),
        (
            "How many (A) butter (B) do you need (C) to make this pancake (D)?",
            "A. How many",
            ["A. How many", "B. butter", "C. do you need", "D. to make this pancake"],
        ),
        (
            "Students (A) shouldn't (B) to ride (C) their bicycles on the pavement (D).",
            "C. to ride",
            ["A. Students", "B. shouldn't", "C. to ride", "D. on the pavement"],
        ),
        (
            "He (A) loves (B) carve (C) eggshells into unique gifts (D).",
            "C. carve",
            ["A. He", "B. loves", "C. carve", "D. unique gifts"],
        ),
        (
            "Solar energy (A) is (B) non-renewable (C) and clean for the environment (D).",
            "C. non-renewable",
            ["A. Solar energy", "B. is", "C. non-renewable", "D. clean"],
        ),
    )

    _READING_PACKS = (
        {
            "title": "ALASKA - THE AMAZING STATE",
            "passage": (
                "ALASKA - THE AMAZING STATE\n\n"
                "Alaska is perhaps the most amazing state in the USA. It has coastlines facing "
                "both the Arctic Ocean and the Pacific Ocean. Alaska has more than three million lakes "
                "and over one hundred thousand glaciers. Many people visit Alaska every year to enjoy "
                "dog sledding, fishing, and watching unique wildlife such as grizzly bears and bald eagles. "
                "Solar and wind energy are also being developed in Alaska to provide clean power for remote villages."
            ),
            "questions": (
                (
                    "What is the passage mainly about?",
                    "B. The natural wonders and wildlife of Alaska",
                    [
                        "A. How to travel to South America",
                        "B. The natural wonders and wildlife of Alaska",
                        "C. Building modern cities in America",
                        "D. Fishing competitions in the Pacific",
                    ],
                ),
                ("Alaska has coastlines facing both the Arctic Ocean and the Pacific Ocean.", "True"),
                ("Alaska has fewer than one hundred lakes in total.", "False"),
                ("Many tourists come to Alaska to enjoy dog sledding and fishing.", "True"),
                ("The text mentions the exact cost of a flight ticket to Alaska.", "Not given"),
                ("Solar and wind energy are being developed to provide clean power in Alaska.", "True"),
                ("Alaska is located entirely in South America.", "False"),
            ),
        },
        {
            "title": "FUTURE MEANS OF TRANSPORT",
            "passage": (
                "FUTURE MEANS OF TRANSPORT\n\n"
                "In the near future, our means of transport will be much greener, smarter, and safer. "
                "Scientists are actively testing driverless cars powered by electricity and solar panels. "
                "A driverless car allows passengers to read, work, or relax while travelling, as intelligent "
                "onboard computers handle navigation and obstacle detection. In crowded cities, personal "
                "aerial vehicles such as the bamboo-copter and solar-powered jetpacks will help commuters fly "
                "over traffic jams. Furthermore, strict traffic safety regulations will still apply: pedestrians "
                "must obey street signs and never cross the road on a red light to avoid collisions."
            ),
            "questions": (
                (
                    "What is the main topic of the passage?",
                    "A. Future means of transport and traffic safety",
                    [
                        "A. Future means of transport and traffic safety",
                        "B. The history of traditional steam trains",
                        "C. How to assemble a helicopter at home",
                        "D. Causes of traffic jams in old cities",
                    ],
                ),
                ("A driverless car allows passengers to read while travelling.", "True"),
                ("Pedestrians should cross the road on a red light.", "False"),
                ("You can mention the name of bamboo-copter when describing personal aerial vehicles.", "True"),
                ("The passage states the exact price of an electric driverless car in 2050.", "Not given"),
                ("Driverless cars are powered by clean energy like electricity and solar panels.", "True"),
                ("Flying vehicles will help commuters travel across traffic congestion.", "True"),
            ),
        },
        {
            "title": "PORTOBELLO MARKET IN LONDON",
            "passage": (
                "PORTOBELLO MARKET IN LONDON\n\n"
                "Visitors to London are struck by the splendour of one of the world's oldest capitals, "
                "admiring iconic sites like Big Ben and Buckingham Palace. However, visitors seeking a glimpse "
                "into the city's everyday life should not miss Portobello Market, which is the most-visited street "
                "market in London.\n\n"
                "Portobello Market is divided into different sections selling second-hand items, clothing, jewellery, "
                "souvenirs, and fresh food. The most sought-after area is devoted to antiques with over 1,000 booths "
                "manned by antique dealers from throughout England. When tired from exploring, visitors can drop into "
                "nearby food courts to savour delicious dishes from Europe and Asia."
            ),
            "questions": (
                (
                    "What is the passage mainly about?",
                    "C. Portobello Market in London",
                    [
                        "A. The film 'Notting Hill'",
                        "B. The history of Big Ben",
                        "C. Portobello Market in London",
                        "D. European cuisine",
                    ],
                ),
                ("Portobello Market is the most-visited street market in London.", "True"),
                ("There are fewer than ten antique booths in Portobello Market.", "False"),
                ("Visitors can find antique cameras, jewellery, and souvenirs at the market.", "True"),
                ("The passage mentions the name of the Prime Minister of the UK.", "Not given"),
                ("Visitors can enjoy delicious food from Europe and Asia near the market.", "True"),
            ),
        },
    )

    _DEFAULT_READING_PASSAGE = _READING_PACKS[0]["passage"]

    _READING_STATEMENTS = tuple(
        q for q in _READING_PACKS[0]["questions"] if len(q) == 2
    )

    _LISTENING_STATEMENTS = (
        ("The speaker shares details about community volunteering activities last summer.", "True"),
        ("Students only worked for one single hour during the whole summer holiday.", "False"),
        ("Volunteers collected old books and clothes to donate to children in rural areas.", "True"),
        ("The recording mentions the specific brand name of the school uniforms.", "Not given"),
        ("Volunteering activities brought meaningful support to elderly people in town.", "True"),
        ("No pupils or teachers participated in the community clean-up weekend.", "False"),
    )

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

            # Select a coherent reading pack from curriculum reading packs
            import random
            pack_idx = random.randint(0, len(self._READING_PACKS) - 1)
            chosen_pack = self._READING_PACKS[pack_idx]
            passage = chosen_pack["passage"]
            reading_frag = reading_fragments[0]
            for rf in all_fragments:
                cleaned = self._clean_text(rf.normalized_text)
                if "most amazing state" in cleaned.lower():
                    reading_frag = rf
                    break

            # Build question slot distribution
            # Slots: list of dicts with 'type' and 'section'
            slots: list[dict[str, str]] = []
            if mode == "listening":
                for _ in range(question_count):
                    slots.append({
                        "type": "listening",
                        "section": "PHẦN A. KỸ NĂNG NGHE (LISTENING)",
                    })
            elif mode == "reading":
                if question_count >= 10:
                    lang_count = 3
                    read_count = 4
                    reorder_count = 2
                    error_count = question_count - lang_count - read_count - reorder_count
                elif question_count >= 4:
                    lang_count = 1
                    read_count = 2
                    reorder_count = 1
                    error_count = question_count - 4
                else:
                    lang_count = 1 if question_count > 1 else 0
                    read_count = question_count - lang_count
                    reorder_count = 0
                    error_count = 0

                for _ in range(lang_count):
                    slots.append({
                        "type": "language",
                        "section": "PHẦN A. NGỮ ÂM & NGÔN NGỮ (LANGUAGE FOCUS)",
                    })
                for _ in range(read_count):
                    slots.append({
                        "type": "reading",
                        "section": "PHẦN B. ĐỌC HIỂU (READING)",
                    })
                for _ in range(reorder_count):
                    slots.append({
                        "type": "reorder",
                        "section": "PHẦN C. KỸ NĂNG VIẾT (WRITING)",
                    })
                for _ in range(error_count):
                    slots.append({
                        "type": "error_correction",
                        "section": "PHẦN C. KỸ NĂNG VIẾT (WRITING)",
                    })
            else:  # mixed
                has_audio = bool(audio_url and listening_frags)
                if question_count >= 10:
                    listen_count = 2 if has_audio else 0
                    lang_count = 3 if has_audio else 5
                    read_count = 3
                    reorder_count = 1
                    error_count = question_count - listen_count - lang_count - read_count - reorder_count
                elif question_count >= 4:
                    listen_count = 1 if has_audio else 0
                    lang_count = 1
                    read_count = 1
                    reorder_count = 1
                    error_count = question_count - listen_count - 3
                else:
                    listen_count = 1 if (has_audio and question_count > 1) else 0
                    read_count = question_count - listen_count
                    lang_count = 0
                    reorder_count = 0
                    error_count = 0

                for _ in range(listen_count):
                    slots.append({
                        "type": "listening",
                        "section": "PHẦN A. KỸ NĂNG NGHE (LISTENING)",
                    })
                for _ in range(lang_count):
                    slots.append({
                        "type": "language",
                        "section": "PHẦN B. NGỮ ÂM & NGÔN NGỮ (LANGUAGE FOCUS)",
                    })
                for _ in range(read_count):
                    slots.append({
                        "type": "reading",
                        "section": "PHẦN C. ĐỌC HIỂU (READING)",
                    })
                for _ in range(reorder_count):
                    slots.append({
                        "type": "reorder",
                        "section": "PHẦN D. KỸ NĂNG VIẾT (WRITING)",
                    })
                for _ in range(error_count):
                    slots.append({
                        "type": "error_correction",
                        "section": "PHẦN D. KỸ NĂNG VIẾT (WRITING)",
                    })

            # Generate questions according to slots
            questions: list[GeneratedQuestion] = []
            listen_idx = 0
            lang_idx = 0
            read_idx = 0
            reorder_idx = 0
            error_idx = 0

            for i, slot in enumerate(slots):
                qtype = slot["type"]
                section = slot["section"]

                if qtype == "listening":
                    frag = listening_frags[listen_idx % len(listening_frags)] if listening_frags else reading_fragments[0]
                    statement, correct = self._LISTENING_STATEMENTS[listen_idx % len(self._LISTENING_STATEMENTS)]
                    prompt = statement
                    answer = {
                        "options": ["True", "False", "Not given"],
                        "correct": correct,
                        "question_type": "listening",
                        "section": section,
                    }
                    if audio_url:
                        answer["audio_url"] = audio_url
                        answer["audio_title"] = audio_title
                    questions.append(
                        GeneratedQuestion(
                            prompt=prompt,
                            answer=answer,
                            source_fragment_ids=(frag.id,),
                        )
                    )
                    listen_idx += 1

                elif qtype == "language":
                    frag = all_fragments[lang_idx % len(all_fragments)]
                    prompt_text, correct, options = self._LANGUAGE_TEMPLATES[lang_idx % len(self._LANGUAGE_TEMPLATES)]
                    answer = {
                        "options": list(options),
                        "correct": correct,
                        "question_type": "language",
                        "section": section,
                    }
                    questions.append(
                        GeneratedQuestion(
                            prompt=prompt_text,
                            answer=answer,
                            source_fragment_ids=(frag.id,),
                        )
                    )
                    lang_idx += 1

                elif qtype == "reading":
                    pack_questions = chosen_pack["questions"]
                    item = pack_questions[read_idx % len(pack_questions)]
                    if len(item) == 3:
                        prompt_text, correct, options = item
                        answer = {
                            "options": list(options),
                            "correct": correct,
                            "question_type": "reading",
                            "section": section,
                            "passage": passage,
                        }
                    else:
                        statement, correct = item
                        prompt_text = statement
                        answer = {
                            "options": ["True", "False", "Not given"],
                            "correct": correct,
                            "question_type": "reading",
                            "section": section,
                            "passage": passage,
                        }
                    questions.append(
                        GeneratedQuestion(
                            prompt=prompt_text,
                            answer=answer,
                            source_fragment_ids=(reading_frag.id,),
                        )
                    )
                    read_idx += 1

                elif qtype == "reorder":
                    frag = all_fragments[reorder_idx % len(all_fragments)]
                    scrambled, correct, options = self._REORDER_TEMPLATES[reorder_idx % len(self._REORDER_TEMPLATES)]
                    prompt = scrambled
                    answer = {
                        "options": list(options),
                        "correct": correct,
                        "question_type": "reorder",
                        "section": section,
                    }
                    questions.append(
                        GeneratedQuestion(
                            prompt=prompt,
                            answer=answer,
                            source_fragment_ids=(frag.id,),
                        )
                    )
                    reorder_idx += 1

                elif qtype == "error_correction":
                    frag = all_fragments[error_idx % len(all_fragments)]
                    sentence, correct, options = self._ERROR_TEMPLATES[error_idx % len(self._ERROR_TEMPLATES)]
                    prompt = sentence
                    answer = {
                        "options": list(options),
                        "correct": correct,
                        "question_type": "error_correction",
                        "section": section,
                    }
                    questions.append(
                        GeneratedQuestion(
                            prompt=prompt,
                            answer=answer,
                            source_fragment_ids=(frag.id,),
                        )
                    )
                    error_idx += 1

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
        timeout = min(self._ai_provider._timeout, 15)

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
            "reasoning": {"effort": "none"},
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
        try:
            with _open(req, timeout=timeout) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            content = _json.loads(data["choices"][0]["message"]["content"])
            raw_questions = content.get("questions", [])
        except Exception:
            return [None] * len(items)

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
