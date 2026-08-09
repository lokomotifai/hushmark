from __future__ import annotations

from pathlib import Path

import pytest
from hushmark_core.ner.decode import decode_predictions
from hushmark_core.ner.onnx_backend import OnnxNerBackend, OnnxUnsupported
from hushmark_core.ner.registry import load_model_spec
from hushmark_core.ner.torch_backend import TorchNerBackend

ROOT = Path(__file__).resolve().parents[2]


def test_registry_pins_model_revision_hash_and_closed_labels() -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "gliner_multi_pii-v1")
    assert spec.revision == "1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d"
    assert spec.sha256 == "3003753fba99e40645cf088c7367a2c6211fc174897dc64f1f9c147c29d18d2d"
    assert spec.labels["PERSON"] == "person"
    assert spec.onnx_confidence_scale == 0.5
    assert spec.onnx_file == "model_quantized.onnx"
    assert spec.onnx_size == 349099560
    assert spec.onnx_sha256 == "2c790b5ce622fe79225da1d4e0b1e00f7d5135229d0f8a010a0050d08529aa91"


def test_decoder_rejects_mapping_outside_ner_taxonomy() -> None:
    with pytest.raises(ValueError, match="outside"):
        decode_predictions(
            [{"label": "person", "start": 0, "end": 4, "score": 0.9}],
            {"person": "TR_TCKN"},
        )


def test_onnx_backend_has_explicit_unsupported_state(tmp_path: Path) -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "gliner_multi_pii-v1")
    backend = OnnxNerBackend(model_dir=tmp_path, spec=spec, onnx_model_file="model.onnx")
    with pytest.raises(OnnxUnsupported, match="absent"):
        backend.load()


def test_torch_backend_detects_turkish_person_from_offline_model() -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "gliner_multi_pii-v1")
    backend = TorchNerBackend(model_dir=ROOT / "models" / spec.id, spec=spec)
    backend.load()
    text = "Müşterimiz Ayşe Yılmaz ödeme desteği istiyor."
    spans = backend.predict(text, threshold=0.55)
    assert any(
        span.entity_type == "PERSON" and text[span.start : span.end] == "Ayşe Yılmaz"
        for span in spans
    )


def test_torch_and_onnx_backends_have_span_parity_on_turkish_fixture() -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "gliner_multi_pii-v1")
    model_dir = ROOT / "models" / spec.id
    torch_backend = TorchNerBackend(model_dir=model_dir, spec=spec)
    onnx_backend = OnnxNerBackend(
        model_dir=model_dir,
        spec=spec,
        onnx_model_file="model_quantized.onnx",
    )
    text = "Müşterimiz Ayşe Yılmaz ödeme desteği istiyor."

    torch_spans = torch_backend.predict(text, threshold=0.55)
    onnx_spans = onnx_backend.predict(text, threshold=0.55)

    assert [(span.entity_type, span.start, span.end) for span in onnx_spans] == [
        (span.entity_type, span.start, span.end) for span in torch_spans
    ]
