import os
from types import SimpleNamespace

from pydantic import SecretStr

from english7.bootstrap import configure_runtime
from english7.core.settings import Settings


class FakeClient:
    pass


def runtime_settings() -> Settings:
    return Settings(
        database_url=SecretStr("sqlite+pysqlite:///:memory:"),
        neo4j_uri="bolt://neo4j:7687",
        neo4j_user="neo4j",
        neo4j_password=SecretStr("password"),
        neo4j_vector_index="source_fragment_embedding",
        embedding_dimensions=3,
        retrieval_top_k=8,
        retrieval_min_score=0.7,
        retrieval_graph_depth=2,
        retrieval_rrf_constant=60,
        retrieval_max_context_fragments=6,
        retrieval_allowed_units="1,2",
        openrouter_api_key=SecretStr("key"),
        openrouter_endpoint="https://openrouter.example/api/v1/chat/completions",
        openrouter_model="configured/chat-model",
        openrouter_timeout_seconds=30,
        openrouter_embedding_endpoint="https://openrouter.example/api/v1/embeddings",
        openrouter_embedding_model="configured/embedding-model",
        upload_max_bytes=1024,
        image_upload_prefix="student-images",
        image_upload_retention_minutes=60,
        image_upload_allowed_types="image/jpeg,image/png,image/webp",
        tutor_query_max_characters=4000,
        minio_upload_bucket="uploads",
    )


def test_configures_real_tutor_and_upload_services_from_settings() -> None:
    app = SimpleNamespace(state=SimpleNamespace())

    runtime = configure_runtime(
        app,
        runtime_settings(),
        session_factory=lambda: None,
        neo4j_driver=FakeClient(),
        minio_client=FakeClient(),
        http_client=FakeClient(),
    )

    assert runtime is not None
    assert app.state.tutor_service is not None
    assert app.state.tutor_service._conversations is not None
    assert app.state.image_upload_service is not None


def test_incomplete_local_settings_leave_optional_runtime_unconfigured(
    monkeypatch,
) -> None:
    for name in tuple(os.environ):
        if name.startswith("ENGLISH7_"):
            monkeypatch.delenv(name)
    app = SimpleNamespace(state=SimpleNamespace())

    runtime = configure_runtime(app, Settings())

    assert runtime is None
    assert not hasattr(app.state, "tutor_service")
