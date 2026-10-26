from pathlib import Path
from typing import Any

from english7.modules.image_uploads.processor import (
    ImageRegion,
    RecognizedText,
)
from english7.modules.ingestion.device import InferenceDevice


def _decode_image(content: bytes):
    import cv2
    import numpy as np

    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Image bytes could not be decoded")
    return image


class DocLayoutYOLOProvider:
    def __init__(
        self,
        *,
        model_id: str,
        device: InferenceDevice,
        confidence_threshold: float,
    ) -> None:
        from doclayout_yolo import YOLOv10

        if "/" in model_id and not Path(model_id).exists():
            from huggingface_hub import hf_hub_download

            checkpoint = hf_hub_download(
                repo_id=model_id,
                filename="doclayout_yolo_docstructbench_imgsz1024.pt",
            )
            self._model = YOLOv10(checkpoint)
        else:
            self._model = YOLOv10(model_id)
        self._device = device.doclayout_value
        self._confidence = confidence_threshold

    def __call__(self, content: bytes) -> list[ImageRegion]:
        image = _decode_image(content)
        results = self._model.predict(
            source=image,
            conf=self._confidence,
            device=self._device,
            verbose=False,
        )
        regions: list[ImageRegion] = []
        for result in results:
            names = result.names
            coordinates = result.boxes.xyxy.cpu().tolist()
            confidences = result.boxes.conf.cpu().tolist()
            classes = result.boxes.cls.cpu().tolist()
            for box, confidence, class_id in zip(
                coordinates, confidences, classes, strict=True
            ):
                x1, y1, x2, y2 = box
                label = (
                    names[int(class_id)]
                    if isinstance(names, (dict, list))
                    else str(class_id)
                )
                regions.append(
                    ImageRegion(
                        round(x1),
                        round(y1),
                        max(0, round(x2 - x1)),
                        max(0, round(y2 - y1)),
                        str(label),
                        float(confidence),
                    )
                )
        if not regions:
            height, width = image.shape[:2]
            regions.append(ImageRegion(0, 0, width, height, "page", 1.0))
        return regions


class PaddleOCRProvider:
    def __init__(self, *, languages: tuple[str, ...], version: str) -> None:
        from paddleocr import PaddleOCR

        if not languages:
            raise ValueError("At least one OCR language is required")
        self._engines = [
            PaddleOCR(
                lang=language,
                ocr_version=version,
                device="cpu",
                enable_mkldnn=False,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
            for language in languages
        ]

    @staticmethod
    def _payload(result: Any) -> dict[str, Any]:
        payload = getattr(result, "json", result)
        if callable(payload):
            payload = payload()
        if not isinstance(payload, dict):
            return {}
        nested = payload.get("res")
        return nested if isinstance(nested, dict) else payload

    def __call__(self, content: bytes, region: ImageRegion) -> RecognizedText:
        image = _decode_image(content)
        crop = image[
            region.y : region.y + region.height,
            region.x : region.x + region.width,
        ]
        best = RecognizedText("", 0.0)
        for engine in self._engines:
            results = engine.predict(crop)
            texts: list[str] = []
            scores: list[float] = []
            for result in results:
                payload = self._payload(result)
                texts.extend(str(value) for value in payload.get("rec_texts", []))
                scores.extend(float(value) for value in payload.get("rec_scores", []))
            confidence = sum(scores) / len(scores) if scores else 0.0
            candidate = RecognizedText(" ".join(texts), confidence)
            if candidate.confidence > best.confidence:
                best = candidate
        return best
