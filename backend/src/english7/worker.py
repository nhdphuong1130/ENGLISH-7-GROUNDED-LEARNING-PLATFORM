import logging
import signal
from collections.abc import Callable
from threading import Event

from minio import Minio

from english7.core.settings import get_settings
from english7.db.session import get_session_factory
from english7.modules.image_uploads.processor import ImageUploadProcessor
from english7.modules.image_uploads.repository import SQLAlchemyImageUploadRepository
from english7.modules.ingestion.device import resolve_device, torch_cuda_available
from english7.modules.ingestion.providers import DocLayoutYOLOProvider, PaddleOCRProvider
from english7.modules.media.storage import MinioUploadStorage

logger = logging.getLogger(__name__)


def run_worker(
    stop_event: Event,
    poll_interval_seconds: float,
    *,
    process_once: Callable[[], object] = lambda: None,
) -> None:
    if poll_interval_seconds <= 0:
        raise ValueError("Worker poll interval must be positive")
    logger.info("ingestion_worker_started")
    while not stop_event.wait(poll_interval_seconds):
        process_once()


def _required(value, name: str):
    if value is None or (
        isinstance(value, str)
        and (
            not value.strip()
            or value.strip().lower().startswith("replace-with-")
        )
    ):
        raise RuntimeError(f"{name} is required for the image worker")
    return value


def build_image_processor() -> ImageUploadProcessor:
    settings = get_settings()
    endpoint = str(_required(settings.minio_endpoint, "ENGLISH7_MINIO_ENDPOINT"))
    secure = endpoint.startswith("https://")
    endpoint = endpoint.removeprefix("https://").removeprefix("http://")
    secret = _required(settings.minio_secret_key, "ENGLISH7_MINIO_SECRET_KEY")
    client = Minio(
        endpoint,
        access_key=str(
            _required(settings.minio_access_key, "ENGLISH7_MINIO_ACCESS_KEY")
        ),
        secret_key=secret.get_secret_value(),
        secure=secure,
    )
    device = resolve_device(
        str(_required(settings.ingestion_device, "ENGLISH7_INGESTION_DEVICE")),
        cuda_available=torch_cuda_available,
    )
    detector = DocLayoutYOLOProvider(
        model_id=str(_required(settings.layout_model_id, "ENGLISH7_LAYOUT_MODEL_ID")),
        device=device,
        confidence_threshold=float(
            _required(
                settings.layout_confidence_threshold,
                "ENGLISH7_LAYOUT_CONFIDENCE_THRESHOLD",
            )
        ),
    )
    recognizer = PaddleOCRProvider(
        languages=tuple(
            item.strip()
            for item in str(
                _required(settings.ocr_languages, "ENGLISH7_OCR_LANGUAGES")
            ).split(",")
            if item.strip()
        ),
        version=str(_required(settings.ocr_version, "ENGLISH7_OCR_VERSION")),
    )
    return ImageUploadProcessor(
        repository=SQLAlchemyImageUploadRepository(
            lambda: get_session_factory()()
        ),
        storage=MinioUploadStorage(
            client,
            bucket=str(
                _required(settings.minio_upload_bucket, "ENGLISH7_MINIO_UPLOAD_BUCKET")
            ),
        ),
        detector=detector,
        recognizer=recognizer,
        minimum_confidence=float(
            _required(
                settings.ocr_minimum_confidence,
                "ENGLISH7_OCR_MINIMUM_CONFIDENCE",
            )
        ),
    )


def main() -> None:
    settings = get_settings()
    interval = settings.worker_poll_interval_seconds
    if interval is None:
        raise RuntimeError("ENGLISH7_WORKER_POLL_INTERVAL_SECONDS is required")
    stop_event = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    processor = build_image_processor()
    run_worker(stop_event, interval, process_once=processor.process_next)


if __name__ == "__main__":
    main()
