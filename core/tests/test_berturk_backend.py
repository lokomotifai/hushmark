from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from hushmark_core.ner.berturk_backend import BerturkNerBackend
from hushmark_core.ner.berturk_span import BerturkSpanModel
from hushmark_core.ner.registry import ModelSpec, create_backend, load_model_spec

ROOT = Path(__file__).resolve().parents[2]


def tiny_spec(payload: bytes) -> ModelSpec:
    primary_sha256 = hashlib.sha256(payload).hexdigest()
    artifact_sha256 = hashlib.sha256(
        f"{primary_sha256}  encoder/model.safetensors\n".encode()
    ).hexdigest()
    return ModelSpec(
        id="tiny-berturk",
        architecture="berturk-fixed-span-ner",
        source="lokomotifai/tiny-private",
        revision="a" * 40,
        distribution="private-huggingface",
        primary_file="encoder/model.safetensors",
        artifact_sha256=artifact_sha256,
        sha256=primary_sha256,
        size=len(payload),
        labels={"PERSON": "person"},
        onnx_confidence_scale=1.0,
        onnx_file=None,
        onnx_size=None,
        onnx_sha256=None,
        runtime_files=(("encoder/model.safetensors", len(payload), primary_sha256),),
    )


class FakeModel:
    label_names = ("person",)

    def eval(self) -> FakeModel:
        return self

    def predict_entities(
        self, text: str, labels: list[str], threshold: float
    ) -> list[dict[str, object]]:
        assert text == "Ayşe geldi."
        assert labels == ["person"]
        assert threshold == 0.5
        return [{"label": "person", "start": 0, "end": 4, "score": 0.99}]


def test_registry_pins_private_berturk_release() -> None:
    spec = load_model_spec(ROOT / "core" / "models.yaml", "hushmark-berturk-112m")

    assert spec.architecture == "berturk-fixed-span-ner"
    assert spec.distribution == "private-huggingface"
    assert spec.source == "lokomotifai/hushmark-berturk-112m"
    assert spec.revision == "49ed7596936fd1ba28a26b788abcfb8c7b963a5c"
    assert spec.primary_file == "encoder/model.safetensors"
    assert spec.artifact_sha256 == (
        "ce319a22f131fd62b49df85261fb33c1dff871c075f3bc37d2d3be0fb9db383a"
    )
    assert spec.sha256 == "a2426b32e90cc97909bcdb1e8518d0bfd5fbf6e7d4e9401565a389fb23807d2f"
    assert spec.size == 442491744
    assert len(spec.runtime_files) == 6
    assert spec.onnx_file is None


def test_backend_verifies_and_decodes_private_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"verified-model"
    model_file = tmp_path / "encoder" / "model.safetensors"
    model_file.parent.mkdir()
    model_file.write_bytes(payload)
    fake_model = FakeModel()
    monkeypatch.setattr(
        BerturkSpanModel,
        "load_artifact",
        classmethod(lambda cls, source, local_files_only=True: fake_model),
    )
    backend = BerturkNerBackend(model_dir=tmp_path, spec=tiny_spec(payload))

    spans = backend.predict("Ayşe geldi.", threshold=0.5)

    assert [(span.entity_type, span.start, span.end, span.confidence) for span in spans] == [
        ("PERSON", 0, 4, 0.99)
    ]
    assert backend.model_sha256 == tiny_spec(payload).artifact_sha256


def test_backend_rejects_tampering_before_model_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"verified-model"
    model_file = tmp_path / "encoder" / "model.safetensors"
    model_file.parent.mkdir()
    model_file.write_bytes(b"tampered")
    called = False

    def fake_load(*_args: object, **_kwargs: object) -> FakeModel:
        nonlocal called
        called = True
        return FakeModel()

    monkeypatch.setattr(BerturkSpanModel, "load_artifact", fake_load)
    backend = BerturkNerBackend(model_dir=tmp_path, spec=tiny_spec(payload))

    with pytest.raises(ValueError, match="size verification"):
        backend.load()
    assert called is False
    assert backend.model_sha256 is None


def test_registry_selects_only_compatible_backend() -> None:
    registry = ROOT / "core" / "models.yaml"
    backend = create_backend(
        backend="berturk",
        registry_path=registry,
        model_root=ROOT / "models",
        model_id="hushmark-berturk-112m",
        onnx_model_file="model.onnx",
    )
    assert isinstance(backend, BerturkNerBackend)

    with pytest.raises(ValueError, match="not compatible"):
        create_backend(
            backend="torch",
            registry_path=registry,
            model_root=ROOT / "models",
            model_id="hushmark-berturk-112m",
            onnx_model_file="model.onnx",
        )
