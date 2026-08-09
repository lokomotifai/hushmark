from hushmark_core.taxonomy_gen import ENTITY_TYPES, TAXONOMY, TAXONOMY_VERSION


def test_generated_taxonomy_is_closed_and_complete() -> None:
    assert TAXONOMY_VERSION == 1
    assert len(ENTITY_TYPES) == 24
    assert set(ENTITY_TYPES) == set(TAXONOMY)
    assert TAXONOMY["TR_TCKN"]["tr_label"] == "TCKN"
    assert TAXONOMY["HEALTH"]["kvkk_class"] == "special"
