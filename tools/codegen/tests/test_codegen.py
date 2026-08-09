from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
PY_GENERATED = ROOT / "core" / "src" / "hushmark_core" / "taxonomy_gen.py"
TS_GENERATED = ROOT / "packages" / "shared" / "src" / "taxonomy.gen.ts"


def load_python_generated() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generated_taxonomy_test", PY_GENERATED)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_languages_share_identical_golden_json() -> None:
    module = load_python_generated()
    typescript = TS_GENERATED.read_text(encoding="utf-8")
    match = re.search(
        r"export const TAXONOMY = (\{.*\}) as const;",
        typescript,
        flags=re.DOTALL,
    )
    assert match is not None
    assert json.loads(match.group(1)) == module.TAXONOMY
    assert len(module.ENTITY_TYPES) == 24
