from __future__ import annotations

import pytest
from hushmark_core.engine import Entity
from hushmark_core.masking import PlaceholderCollision, mask_text, unmask_text


def test_repeated_value_reuses_placeholder_within_request() -> None:
    text = "Ayşe aradı, Ayşe yazdı."
    entities = [
        Entity("PERSON", 0, 4, 0.9, "ner"),
        Entity("PERSON", 12, 16, 0.9, "ner"),
    ]
    result = mask_text(text, entities, session="s1")
    assert result.masked_text == "[KISI_1] aradı, [KISI_1] yazdı."
    assert [mapping.placeholder for mapping in result.mappings] == ["[KISI_1]", "[KISI_1]"]
    assert unmask_text(result.masked_text, result.mappings) == text


def test_collision_rejects_by_default() -> None:
    with pytest.raises(PlaceholderCollision):
        mask_text("Önceden [KISI_1] var", [], session="s1")


def test_prefix_mode_issues_a_deterministic_collision_suffix() -> None:
    text = "[KISI_1] ve Ayşe"
    entity = Entity("PERSON", 12, 16, 0.9, "ner")
    first = mask_text(text, [entity], session="s1", collision_mode="prefix")
    second = mask_text(text, [entity], session="s1", collision_mode="prefix")
    assert first == second
    assert first.mappings[0].placeholder.startswith("[KISI_1]#")
    assert first.masked_text.startswith("[KISI_1] ve [KISI_1]#")


def test_unknown_placeholder_is_never_guessed() -> None:
    assert unmask_text("Yanıt [KISI_999]", []) == "Yanıt [KISI_999]"
