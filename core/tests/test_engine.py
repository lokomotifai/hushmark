from hushmark_core.engine import Entity, get_engine, resolve_overlaps


def test_l0_detects_demo_values_with_code_point_offsets() -> None:
    text = "TCKN 10000000146 IBAN TR330006100519786457841326"
    entities = get_engine().analyze(text, "tr")
    assert [(entity.type, entity.start, entity.end) for entity in entities] == [
        ("TR_TCKN", 5, 16),
        ("TR_IBAN", 22, 48),
    ]


def test_deterministic_layer_wins_overlap_before_span_length() -> None:
    entities = [
        Entity("PERSON", 0, 20, 0.99, "ner"),
        Entity("TR_TCKN", 5, 16, 1.0, "deterministic"),
    ]
    assert resolve_overlaps(entities) == [entities[1]]


def test_longer_span_then_confidence_resolves_within_layer() -> None:
    shorter = Entity("EMAIL", 2, 8, 1.0, "deterministic")
    longer = Entity("TR_SGK", 0, 13, 0.6, "deterministic")
    assert resolve_overlaps([shorter, longer]) == [longer]
