from __future__ import annotations

import statistics
import time

from hushmark_core.engine import get_engine


def benchmark_text() -> str:
    return (
        "Müşteri TCKN 10000000146 ve IBAN TR330006100519786457841326 ile destek istedi. "
        "İletişim adresi destek@example.com. "
    ) * 8


def test_l0_p95_is_under_five_ms() -> None:
    engine = get_engine()
    text = benchmark_text()
    engine.analyze(text, "tr")
    durations: list[float] = []
    for _ in range(120):
        started = time.perf_counter()
        engine.analyze(text, "tr")
        durations.append(time.perf_counter() - started)
    p95 = statistics.quantiles(durations, n=100, method="inclusive")[94]
    assert p95 < 0.005, f"L0 p95 was {p95 * 1000:.3f} ms"


def test_l0_benchmark_uses_one_kibibyte_input(benchmark: object) -> None:
    from pytest_benchmark.fixture import BenchmarkFixture

    assert isinstance(benchmark, BenchmarkFixture)
    text = benchmark_text()
    assert 900 <= len(text.encode("utf-8")) <= 1_200
    entities = benchmark(get_engine().analyze, text, "tr")
    assert len(entities) >= 3
