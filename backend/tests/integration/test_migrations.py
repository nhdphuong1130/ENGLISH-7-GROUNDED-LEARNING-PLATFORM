from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from english7.db.session import get_engine


def test_initial_migration_creates_expected_tables() -> None:
    config = Config("alembic.ini")
    command.upgrade(config, "head")

    table_names = set(inspect(get_engine()).get_table_names())

    assert {
        "users",
        "source_documents",
        "source_fragments",
        "quiz_questions",
        "test_attempts",
        "audio_playbacks",
        "knowledge_concepts",
        "fragment_concept_assertions",
        "concept_relation_assertions",
        "unit_concept_assertions",
        "graph_builds",
        "tutor_conversations",
        "tutor_chats",
    } <= table_names

    user_columns = {
        column["name"] for column in inspect(get_engine()).get_columns("users")
    }
    assert {
        "full_name",
        "date_of_birth",
        "gender",
        "school_name",
        "class_name",
    } <= user_columns

    chat_columns = {
        column["name"]
        for column in inspect(get_engine()).get_columns("tutor_chats")
    }
    assert {"conversation_id", "sequence_number"} <= chat_columns
