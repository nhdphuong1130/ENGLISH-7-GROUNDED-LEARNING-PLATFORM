from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.db.base import Base
from english7.db.models import (
    Activity,
    QuestionSource,
    Quiz,
    QuizBlueprint,
    QuizQuestion,
    Role,
    Section,
    SourceDocument,
    SourceFragment,
    StudentAnswer,
    TestAttempt,
    Textbook,
    Unit,
    User,
)
from english7.modules.knowledge.gap_service import (
    KnowledgeGapAnalysis,
    KnowledgeGapItem,
    KnowledgeGapService,
)


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def test_diagnose_gaps_identifies_weak_grammar_concept(session_factory):
    user_id = uuid4()
    quiz_id = uuid4()
    blueprint_id = uuid4()
    textbook_id = uuid4()
    unit_id = uuid4()
    section_id = uuid4()
    activity_id = uuid4()
    doc_id = uuid4()
    frag_id = uuid4()

    with session_factory.begin() as session:
        role = Role(name="student")
        session.add(role)
        session.flush()

        user = User(id=user_id, email="student@example.com", password_hash="x", role_id=role.id)
        session.add(user)

        tb = Textbook(id=textbook_id, title="Tiếng Anh 7 Global Success", publisher="NXBGD")
        session.add(tb)
        u = Unit(id=unit_id, textbook_id=textbook_id, number=1, title="Hobbies", is_published=True)
        session.add(u)
        sec = Section(id=section_id, unit_id=unit_id, title="A Closer Look 2", section_type="grammar", position=1)
        session.add(sec)
        act = Activity(id=activity_id, section_id=section_id, activity_type="grammar", instruction="Grammar")
        session.add(act)

        doc = SourceDocument(
            id=doc_id,
            textbook_id=textbook_id,
            original_filename="unit1.pdf",
            object_key="unit1.pdf",
            file_hash="hash1",
            page_count=120,
            ingestion_version="1.0",
        )
        session.add(doc)

        frag = SourceFragment(
            id=frag_id,
            source_document_id=doc_id,
            activity_id=activity_id,
            pdf_page=13,
            printed_page=11,
            normalized_text="Present simple tense rules",
            x=0, y=0, width=100, height=100,
        )
        session.add(frag)

        bp = QuizBlueprint(
            id=blueprint_id,
            name="Unit 1 Practice",
            duration_minutes=15,
            difficulty="medium",
            policy={},
            is_active=True,
        )
        session.add(bp)

        quiz = Quiz(id=quiz_id, blueprint_id=blueprint_id, created_for_user_id=user_id)
        session.add(quiz)

        # 3 questions on this fragment: 2 wrong, 1 correct => 33% mastery
        q1 = QuizQuestion(id=uuid4(), quiz_id=quiz_id, prompt="Q1", answer_payload={"correct": "A"})
        q2 = QuizQuestion(id=uuid4(), quiz_id=quiz_id, prompt="Q2", answer_payload={"correct": "B"})
        q3 = QuizQuestion(id=uuid4(), quiz_id=quiz_id, prompt="Q3", answer_payload={"correct": "C"})
        session.add_all([q1, q2, q3])
        session.flush()

        session.add(QuestionSource(question_id=q1.id, source_fragment_id=frag_id))
        session.add(QuestionSource(question_id=q2.id, source_fragment_id=frag_id))
        session.add(QuestionSource(question_id=q3.id, source_fragment_id=frag_id))

        attempt = TestAttempt(
            id=uuid4(),
            quiz_id=quiz_id,
            user_id=user_id,
            status="submitted",
        )
        session.add(attempt)
        session.flush()

        # Student answers: q1 wrong, q2 wrong, q3 correct
        session.add(StudentAnswer(test_attempt_id=attempt.id, question_id=q1.id, answer_payload={"choice": "X"}, is_correct=False))
        session.add(StudentAnswer(test_attempt_id=attempt.id, question_id=q2.id, answer_payload={"choice": "Y"}, is_correct=False))
        session.add(StudentAnswer(test_attempt_id=attempt.id, question_id=q3.id, answer_payload={"choice": "C"}, is_correct=True))

    # Mock Neo4j driver providing grammar rule info
    mock_session = MagicMock()
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session

    mock_session.run.return_value.data.return_value = [
        {
            "fid": str(frag_id),
            "concept_id": "grammar-u1-present-simple",
            "concept_name": "Present Simple Tense",
            "category": "grammar",
            "unit_num": 1,
            "unit_title": "Hobbies",
            "explanation": "Thì hiện tại đơn diễn tả thói quen hoặc sở thích.",
        }
    ]

    service = KnowledgeGapService(session_factory, neo4j_driver=mock_driver)
    analysis = service.diagnose_gaps(user_id)

    assert isinstance(analysis, KnowledgeGapAnalysis)
    assert analysis.total_tested_concepts == 1
    assert analysis.weak_concepts_count == 1
    assert len(analysis.gaps) == 1

    gap = analysis.gaps[0]
    assert gap.concept_key == "grammar-u1-present-simple"
    assert gap.concept_name == "Present Simple Tense"
    assert gap.category == "grammar"
    assert gap.unit_number == 1
    assert gap.total_attempts == 3
    assert gap.incorrect_count == 2
    assert abs(gap.mastery_score - 1 / 3) < 0.01
    assert "SGK Tiếng Anh 7 Unit 1, Trang 11" in gap.textbook_citation
    assert "Present Simple Tense" in gap.suggested_prompt


def test_diagnose_gaps_returns_empty_when_no_attempts(session_factory):
    user_id = uuid4()
    service = KnowledgeGapService(session_factory, neo4j_driver=None)
    analysis = service.diagnose_gaps(user_id)

    assert analysis.total_tested_concepts == 0
    assert analysis.weak_concepts_count == 0
    assert analysis.average_mastery == 1.0
    assert analysis.gaps == []


def test_diagnose_gaps_falls_back_to_unit_when_neo4j_empty(session_factory):
    user_id = uuid4()
    quiz_id = uuid4()
    bp_id = uuid4()
    tb_id = uuid4()
    u_id = uuid4()
    sec_id = uuid4()
    act_id = uuid4()
    doc_id = uuid4()
    frag_id = uuid4()

    with session_factory.begin() as session:
        role = Role(name="student")
        session.add(role)
        session.flush()

        user = User(id=user_id, email="s2@example.com", password_hash="x", role_id=role.id)
        session.add(user)

        tb = Textbook(id=tb_id, title="Tiếng Anh 7 Global Success", publisher="NXBGD")
        session.add(tb)
        u = Unit(id=u_id, textbook_id=tb_id, number=2, title="Healthy Living", is_published=True)
        session.add(u)
        sec = Section(id=sec_id, unit_id=u_id, title="Reading", section_type="reading", position=1)
        session.add(sec)
        act = Activity(id=act_id, section_id=sec_id, activity_type="reading", instruction="Read")
        session.add(act)

        doc = SourceDocument(
            id=doc_id, textbook_id=tb_id, original_filename="u2.pdf",
            object_key="u2.pdf", file_hash="hash2", page_count=120, ingestion_version="1.0"
        )
        session.add(doc)

        frag = SourceFragment(
            id=frag_id, source_document_id=doc_id, activity_id=act_id,
            pdf_page=20, printed_page=18, normalized_text="Healthy food",
            x=0, y=0, width=100, height=100,
        )
        session.add(frag)

        bp = QuizBlueprint(id=bp_id, name="U2 Practice", duration_minutes=15, difficulty="medium", policy={}, is_active=True)
        session.add(bp)
        quiz = Quiz(id=quiz_id, blueprint_id=bp_id, created_for_user_id=user_id)
        session.add(quiz)

        q1 = QuizQuestion(id=uuid4(), quiz_id=quiz_id, prompt="Q1", answer_payload={"correct": "A"})
        session.add(q1)
        session.flush()
        session.add(QuestionSource(question_id=q1.id, source_fragment_id=frag_id))

        attempt = TestAttempt(id=uuid4(), quiz_id=quiz_id, user_id=user_id, status="submitted")
        session.add(attempt)
        session.flush()
        session.add(StudentAnswer(test_attempt_id=attempt.id, question_id=q1.id, answer_payload={"choice": "B"}, is_correct=False))

    # Driver returns empty records
    mock_session = MagicMock()
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mock_session.run.return_value.data.return_value = []

    service = KnowledgeGapService(session_factory, neo4j_driver=mock_driver)
    analysis = service.diagnose_gaps(user_id)

    assert analysis.total_tested_concepts == 1
    assert analysis.weak_concepts_count == 1
    gap = analysis.gaps[0]
    assert gap.concept_key == "unit-2"
    assert "Healthy Living" in gap.concept_name
    assert gap.category == "topic"
    assert gap.unit_number == 2
    assert gap.mastery_score == 0.0
    assert "SGK Tiếng Anh 7 Unit 2, Trang 18" in gap.textbook_citation

