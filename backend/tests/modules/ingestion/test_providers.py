import sys
from types import SimpleNamespace

from english7.modules.ingestion import providers
from english7.modules.ingestion.device import InferenceDevice
from english7.modules.ingestion.providers import DocLayoutYOLOProvider, PaddleOCRProvider


def test_doclayout_loads_hugging_face_repository_id(monkeypatch) -> None:
    calls = []

    class FakeYOLO:
        def __init__(self, model_id):
            calls.append(("local", model_id))

    monkeypatch.setitem(
        sys.modules,
        "doclayout_yolo",
        SimpleNamespace(YOLOv10=FakeYOLO),
    )
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(
            hf_hub_download=lambda **kwargs: calls.append(
                ("hugging-face", kwargs["repo_id"], kwargs["filename"])
            )
            or "/models/doclayout.pt"
        ),
    )

    DocLayoutYOLOProvider(
        model_id="juliozhao/DocLayout-YOLO-DocStructBench",
        device=InferenceDevice.CPU,
        confidence_threshold=0.5,
    )

    assert calls == [
        (
            "hugging-face",
            "juliozhao/DocLayout-YOLO-DocStructBench",
            "doclayout_yolo_docstructbench_imgsz1024.pt",
        ),
        ("local", "/models/doclayout.pt"),
    ]


def test_doclayout_falls_back_to_whole_image_when_no_region_is_detected(
    monkeypatch,
) -> None:
    image = SimpleNamespace(shape=(240, 320, 3))
    monkeypatch.setattr(providers, "_decode_image", lambda _: image)
    provider = DocLayoutYOLOProvider.__new__(DocLayoutYOLOProvider)
    provider._model = SimpleNamespace(predict=lambda **_: [])
    provider._device = "cpu"
    provider._confidence = 0.5

    assert provider(b"small exercise image") == [
        providers.ImageRegion(0, 0, 320, 240, "page", 1.0)
    ]


def test_paddle_ocr_disables_unsupported_cpu_mkldnn_path(monkeypatch) -> None:
    configurations = []

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            configurations.append(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        SimpleNamespace(PaddleOCR=FakePaddleOCR),
    )

    PaddleOCRProvider(languages=("en", "vi"), version="PP-OCRv5")

    assert len(configurations) == 2
    assert all(config["enable_mkldnn"] is False for config in configurations)
