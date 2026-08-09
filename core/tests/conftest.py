from __future__ import annotations

import os

if "HUSHMARK_CORE_NER_BACKEND" not in os.environ and "HUSHMARK_NER_BACKEND" not in os.environ:
    os.environ["HUSHMARK_CORE_NER_BACKEND"] = "disabled"
