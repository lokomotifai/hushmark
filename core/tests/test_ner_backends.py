from __future__ import annotations

from pathlib import Path

import pytest
from hushmark_core.ner.decode import decode_predictions
from hushmark_core.ner.integrity import verify_runtime_artifacts
from hushmark_core.ner.onnx_backend import OnnxNerBackend, OnnxUnsupported
from hushmark_core.ner.registry import load_model_spec
from hushmark_core.ner.torch_backend import TorchNerBackend

ROOT = Path(__file__).resolve().parents[2]


def test_registry_pins_adopted_hushmark_tr_artifacts() -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "hushmark-tr")
    assert spec.distribution == "remote"
    assert spec.revision == "31a6896cc6c1a0eb6efd53b782716207313066ac"
    assert spec.sha256 == "a8f8bc87fdd4d4a92898513fd87eed9e7ccd2b6603ef1d1d5ce152e49192b6c2"
    assert spec.labels["PERSON"] == "person"
    assert spec.onnx_confidence_scale == pytest.approx(0.4 / 0.55)
    assert spec.onnx_file == "model.onnx"
    assert spec.onnx_size == 1157113250
    assert spec.onnx_sha256 == ("c5e72ca974f2e671325314f5a2d1d7eb2e1951ccd3d5250b0e223787f22c35ed")
    assert (
        "gliner_config.json",
        2312,
        "61a066493aa5b64280be2af4686337553e9f7119f5c77f52e301e8b0ce5c2577",
    ) in spec.runtime_files


def test_registry_pins_model_revision_hash_and_closed_labels() -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "gliner_multi_pii-v1")
    assert spec.distribution == "remote"
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
    spec = load_model_spec(ROOT / "core" / "models.yaml", "hushmark-tr")
    backend = TorchNerBackend(model_dir=ROOT / "models" / spec.id, spec=spec)
    backend.load()
    text = "Müşterimiz Ayşe Yılmaz ödeme desteği istiyor."
    spans = backend.predict(text, threshold=0.55)
    assert any(
        span.entity_type == "PERSON" and text[span.start : span.end] == "Ayşe Yılmaz"
        for span in spans
    )
    assert backend.model_sha256 == spec.sha256


def test_torch_backend_rejects_tampered_weights_before_import(tmp_path: Path) -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "hushmark-tr")
    model_dir = tmp_path / spec.id
    model_dir.mkdir()
    (model_dir / "pytorch_model.bin").write_bytes(b"tampered")
    backend = TorchNerBackend(model_dir=model_dir, spec=spec)
    with pytest.raises(ValueError, match="size verification"):
        backend.load()
    assert backend.model_sha256 is None


def test_runtime_integrity_rejects_tampered_config(tmp_path: Path) -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "hushmark-tr")
    filename, size, _sha256 = spec.runtime_files[0]
    (tmp_path / filename).write_bytes(b"x" * size)
    with pytest.raises(ValueError, match="SHA-256 verification"):
        verify_runtime_artifacts(tmp_path, spec)


def test_torch_and_onnx_backends_have_span_parity_on_turkish_fixture() -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "hushmark-tr")
    model_dir = ROOT / "models" / spec.id
    torch_backend = TorchNerBackend(model_dir=model_dir, spec=spec)
    onnx_backend = OnnxNerBackend(
        model_dir=model_dir,
        spec=spec,
        onnx_model_file="model.onnx",
    )
    text = "Müşterimiz Ayşe Yılmaz ödeme desteği istiyor."

    torch_spans = torch_backend.predict(text, threshold=0.55)
    onnx_spans = onnx_backend.predict(text, threshold=0.55)

    assert [(span.entity_type, span.start, span.end) for span in onnx_spans] == [
        (span.entity_type, span.start, span.end) for span in torch_spans
    ]
