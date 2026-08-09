from __future__ import annotations

from pathlib import Path

from hushmark_bench.dataset import generate_examples, load_dataset, write_dataset
from hushmark_bench.templates import DOMAINS, TEMPLATES
from hushmark_core.taxonomy_gen import ENTITY_TYPES


def test_template_bank_covers_six_domains_and_full_taxonomy() -> None:
    assert len(DOMAINS) == 6
    assert all(sum(template.domain == domain for template in TEMPLATES) >= 40 for domain in DOMAINS)
    rendered_types = {
        entity.type
        for example in generate_examples(20260809, repetitions=1)
        for entity in example.entities
    }
    assert rendered_types == set(ENTITY_TYPES)


def test_generation_is_hash_identical_and_offsets_are_exact(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    assert write_dataset(first, 20260809, repetitions=1) == write_dataset(
        second, 20260809, repetitions=1
    )
    assert first.read_bytes() == second.read_bytes()
    assert len(load_dataset(first)) == len(TEMPLATES)
