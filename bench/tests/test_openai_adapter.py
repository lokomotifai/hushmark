"""Offset resolution for the LLM adapter, which never trusts model-reported offsets."""

from __future__ import annotations

from hushmark_bench.adapters.openai_llm import resolve_offsets


def test_resolves_first_occurrence_by_surface_string() -> None:
    text = "Ahmet Yılmaz için TCKN 12345678901 kaydedildi."
    spans = resolve_offsets(text, [{"type": "PERSON", "text": "Ahmet Yılmaz", "occurrence": 1}])
    assert spans == [{"type": "PERSON", "start": 0, "end": 12, "confidence": 1.0, "layer": "llm"}]


def test_resolves_repeated_surface_by_occurrence_index() -> None:
    text = "Ali geldi, sonra Ali gitti."
    spans = resolve_offsets(
        text,
        [
            {"type": "PERSON", "text": "Ali", "occurrence": 1},
            {"type": "PERSON", "text": "Ali", "occurrence": 2},
        ],
    )
    assert [(span["start"], span["end"]) for span in spans] == [(0, 3), (17, 20)]


def test_drops_hallucinated_spans_absent_from_the_text() -> None:
    text = "Sadece bir cümle."
    spans = resolve_offsets(text, [{"type": "PERSON", "text": "Mehmet", "occurrence": 1}])
    assert spans == []


def test_drops_occurrence_beyond_the_last_match() -> None:
    text = "Ali geldi."
    spans = resolve_offsets(text, [{"type": "PERSON", "text": "Ali", "occurrence": 3}])
    assert spans == []


def test_skips_entries_without_a_surface_string() -> None:
    assert resolve_offsets("herhangi bir metin", [{"type": "PERSON", "text": ""}]) == []
