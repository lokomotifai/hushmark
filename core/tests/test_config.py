from hushmark_core.config import Settings


def test_defaults_are_safe_and_l0_only() -> None:
    settings = Settings()
    assert settings.port == 8000
    assert settings.ner_backend == "disabled"
    assert settings.ner_threshold == 0.55


def test_environment_namespace(monkeypatch: object) -> None:
    from pytest import MonkeyPatch

    assert isinstance(monkeypatch, MonkeyPatch)
    monkeypatch.setenv("HUSHMARK_CORE_PORT", "8123")
    assert Settings().port == 8123
