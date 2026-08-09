from hushmark_core.engine import DetectionEngine, Entity, get_engine, resolve_overlaps
from hushmark_core.ner.base import NerSpan


class CountingBackend:
    model_id = "counting"
    model_sha256 = None

    def __init__(self) -> None:
        self.calls = 0
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def is_ready(self) -> bool:
        return self.loaded

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        del text, threshold
        self.calls += 1
        return []


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


def test_neutral_residual_skips_ner_after_deterministic_detection() -> None:
    backend = CountingBackend()
    engine = DetectionEngine(backend)

    entities = engine.analyze(f"{'ve ' * 511}10000000146", "tr")

    assert [(entity.type, entity.start, entity.end) for entity in entities] == [
        ("TR_TCKN", 1533, 1544),
    ]
    assert backend.calls == 0


def test_unknown_words_and_unclaimed_digits_still_run_ner() -> None:
    backend = CountingBackend()
    engine = DetectionEngine(backend)

    engine.analyze("Ali", "tr")
    engine.analyze("01.01.1990", "tr")

    assert backend.calls == 2
