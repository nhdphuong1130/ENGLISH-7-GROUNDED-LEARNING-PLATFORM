from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ENGLISH7_",
        extra="ignore",
    )

    service_name: str = "english7-api"
    speech_runtime_url: str = 'http://speech-runtime:8010'
    speech_timeout_seconds: float = 120.0
    vocab_audio_cache_dir: str | None = None
    api_prefix: str = "/api/v1"
    database_url: SecretStr | None = None
    jwt_secret: SecretStr | None = None
    jwt_algorithm: str | None = None
    access_token_minutes: int | None = None
    worker_poll_interval_seconds: float | None = None
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: SecretStr | None = None
    neo4j_vector_index: str | None = None
    embedding_provider: str = "fastembed"
    embedding_model: str | None = None
    embedding_model_version: str | None = None
    embedding_dimensions: int | None = None
    embedding_cache_dir: str = "/app/cache/fastembed"
    embedding_batch_size: int = 32
    embedding_query_prefix: str = ""
    embedding_passage_prefix: str = ""
    embedding_preprocessing_version: str = "v1"
    knowledge_graph_index_timeout_seconds: float = 60.0
    retrieval_top_k: int | None = None
    retrieval_min_score: float | None = None
    retrieval_graph_depth: int | None = None
    retrieval_rrf_constant: int | None = None
    retrieval_max_context_fragments: int | None = None
    retrieval_allowed_units: str | None = None
    openrouter_api_key: SecretStr | None = None
    openrouter_endpoint: str | None = None
    openrouter_model: str | None = None
    openrouter_timeout_seconds: float | None = None
    openrouter_embedding_endpoint: str | None = None
    openrouter_embedding_model: str | None = None
    quiz_duplicate_threshold: float | None = None
    quiz_max_audio_plays: int | None = None
    ingestion_device: str | None = None
    layout_model_id: str | None = None
    layout_confidence_threshold: float | None = None
    ocr_engine: str | None = None
    ocr_version: str | None = None
    ingestion_version: str | None = None
    source_object_prefix: str | None = None
    upload_max_bytes: int | None = None
    image_upload_prefix: str | None = None
    image_upload_retention_minutes: int | None = None
    image_upload_allowed_types: str | None = None
    ocr_languages: str | None = None
    ocr_minimum_confidence: float | None = None
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: SecretStr | None = None
    minio_upload_bucket: str | None = None
    tutor_query_max_characters: int | None = None
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr | None = None
    twilio_from_phone: str = ""
    sms_gateway_url: str | None = "http://127.0.0.1:8080"
    sms_gateway_username: str | None = "sms"
    sms_gateway_password: SecretStr | None = None
    admin_otp_phone: str | None = None
    clicksend_username: str | None = None
    clicksend_api_key: SecretStr | None = None

    def require_database_url(self) -> str:
        if self.database_url is None:
            raise RuntimeError("ENGLISH7_DATABASE_URL is required for database access")
        return self.database_url.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
