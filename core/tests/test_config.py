import pytest
from hushmark_core.config import Settings, get_settings
from pydantic import ValidationError


def test_defaults_select_the_offline_torch_backend(monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.delenv("HUSHMARK_CORE_NER_BACKEND", raising=False)
    settings = Settings()
    assert settings.port == 8000
    assert settings.ner_backend == "torch"
    assert settings.ner_threshold == 0.55


def test_legacy_backend_environment_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HUSHMARK_CORE_NER_BACKEND", raising=False)
    monkeypatch.setenv("HUSHMARK_NER_BACKEND", "onnx")
    get_settings.cache_clear()
    assert get_settings().ner_backend == "onnx"
    get_settings.cache_clear()


def test_per_type_thresholds_are_closed_to_ner_taxonomy() -> None:
    assert Settings(ner_thresholds={"PERSON": 0.7}).ner_thresholds == {"PERSON": 0.7}
    with pytest.raises(ValidationError, match="unknown type"):
        Settings(ner_thresholds={"TR_TCKN": 0.7})


def test_environment_namespace(monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setenv("HUSHMARK_CORE_PORT", "8123")
    assert Settings().port == 8123
