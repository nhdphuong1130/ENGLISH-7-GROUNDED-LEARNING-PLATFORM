import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from english7.modules.image_uploads.domain import ImageUploadRecord


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImageRegion:
    x: int
    y: int
    width: int
    height: int
    region_type: str
    confidence: float


@dataclass(frozen=True, slots=True)
class RecognizedText:
    text: str
    confidence: float


class ProcessingRepository(Protocol):
    def claim_next(self) -> ImageUploadRecord | None: ...

    def mark_ready(self, upload_id: UUID, text: str, confidence: float) -> None: ...

    def mark_failed(self, upload_id: UUID, failure_code: str) -> None: ...


class DownloadStorage(Protocol):
    def get(self, object_key: str) -> bytes: ...


class ImageUploadProcessor:
    def __init__(
        self,
        *,
        repository: ProcessingRepository,
        storage: DownloadStorage,
        detector: Callable[[bytes], list[ImageRegion]],
        recognizer: Callable[[bytes, ImageRegion], RecognizedText],
        minimum_confidence: float,
    ) -> None:
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("OCR confidence must be between zero and one")
        self._repository = repository
        self._storage = storage
        self._detector = detector
        self._recognizer = recognizer
        self._minimum_confidence = minimum_confidence

    def process_next(self) -> bool:
        upload = self._repository.claim_next()
        if upload is None:
            return False
        try:
            image = self._storage.get(upload.object_key)
            regions = sorted(self._detector(image), key=lambda item: (item.y, item.x))
            recognized = [self._recognizer(image, region) for region in regions]
            usable = [
                item
                for item in recognized
                if item.confidence >= self._minimum_confidence and item.text.strip()
            ]
            if not usable:
                self._repository.mark_failed(upload.id, "image_text_not_found")
                return True
            text = "\n".join(" ".join(item.text.split()) for item in usable)
            confidence = round(
                sum(item.confidence for item in usable) / len(usable), 6
            )
            self._repository.mark_ready(upload.id, text, confidence)
        except Exception:
            logger.exception("Image upload processing failed for %s", upload.id)
            self._repository.mark_failed(upload.id, "image_processing_failed")
        return True
