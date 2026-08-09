from __future__ import annotations

from hushmark_core.engine import Entity
from hushmark_core.masking import PLACEHOLDER_PATTERN, mask_text, unmask_text
from hypothesis import given
from hypothesis import strategies as st

UNICODE_PIECES = st.sampled_from(
    [
        "İstanbul",
        "ışık",
        "Iğdır",
        "i\u0307",
        "Çağla Öztürk",
        "🧿",
        "👩🏽‍💻",
        "özel-veri",
        "\n",
        " ",
    ]
)


@given(
    prefix=st.lists(UNICODE_PIECES, min_size=0, max_size=6).map("".join),
    value=st.lists(UNICODE_PIECES, min_size=1, max_size=5).map("".join),
    suffix=st.lists(UNICODE_PIECES, min_size=0, max_size=6).map("".join),
)
def test_roundtrip_preserves_exact_unicode_bytes(prefix: str, value: str, suffix: str) -> None:
    text = prefix + value + suffix
    if PLACEHOLDER_PATTERN.search(text):
        return
    entity = Entity(
        type="PERSON",
        start=len(prefix),
        end=len(prefix) + len(value),
        confidence=0.9,
        layer="ner",
    )
    result = mask_text(text, [entity], session="property")
    assert unmask_text(result.masked_text, result.mappings) == text
    assert result.mappings[0].value == value
