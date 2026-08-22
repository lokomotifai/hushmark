from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_fetch_models():
    script = Path(__file__).resolve().parents[2] / "scripts" / "fetch-models.py"
    spec = importlib.util.spec_from_file_location("hushmark_fetch_models_runtime", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_config_embeds_encoder_for_offline_gliner(tmp_path: Path) -> None:
    module = load_fetch_models()
    tokenizer_dir = tmp_path / "encoder"
    target_dir = tmp_path / "gliner"
    tokenizer_dir.mkdir()
    target_dir.mkdir()
    (tokenizer_dir / "config.json").write_text(
        json.dumps({"model_type": "deberta-v2", "vocab_size": 250_105}),
        encoding="utf-8",
    )

    config = module.embed_offline_encoder_config(
        {"model_name": "microsoft/mdeberta-v3-base"},
        tokenizer_dir,
        target_dir,
    )

    assert config["encoder_config"]["model_type"] == "deberta-v2"
    assert config["vocab_size"] == 250_105
    local = json.loads((target_dir / "config.json").read_text(encoding="utf-8"))
    assert local["transformers_version"] == "5.0.0"
