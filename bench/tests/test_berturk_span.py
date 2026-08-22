from __future__ import annotations

from types import SimpleNamespace

import torch
from hushmark_bench.berturk_span import BerturkSpanModel, candidate_spans, training_spans
from torch import nn


class FakeEncoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.config = SimpleNamespace(hidden_size=8)
        self.embedding = nn.Embedding(32, 8)

    def forward(self, input_ids: torch.Tensor, **_: object) -> SimpleNamespace:
        return SimpleNamespace(last_hidden_state=self.embedding(input_ids))


def test_candidate_spans_respect_inclusive_width() -> None:
    assert candidate_spans(3, 2) == [(0, 0), (0, 1), (1, 1), (1, 2), (2, 2)]


def test_training_spans_keep_gold_and_deterministically_sample_background() -> None:
    record = {
        "id": "row-1",
        "tokenized_text": ["Ali", "Ankara", "geldi"],
        "ner": [[0, 0, "person"]],
    }
    first = training_spans(
        record,
        {"person": 1},
        max_width=2,
        seed=7,
        negative_ratio=1,
        minimum_negatives=2,
    )
    second = training_spans(
        record,
        {"person": 1},
        max_width=2,
        seed=7,
        negative_ratio=1,
        minimum_negatives=2,
    )
    assert first == second
    assert (first[0][0], first[1][0], first[2][0]) == (0, 0, 1)
    assert first[2].count(0) == 2


def test_span_model_forward_produces_finite_weighted_loss() -> None:
    model = BerturkSpanModel(
        FakeEncoder(),
        tokenizer=SimpleNamespace(is_fast=True),
        label_names=["person", "full address"],
        max_length=16,
        max_width=3,
        width_embedding_size=4,
        dropout=0.0,
    )
    output = model(
        input_ids=torch.tensor([[1, 2, 3, 4]]),
        attention_mask=torch.tensor([[1, 1, 1, 1]]),
        word_starts=torch.tensor([[1, 2]]),
        word_mask=torch.tensor([[True, True]]),
        span_starts=torch.tensor([[0, 0, 1]]),
        span_ends=torch.tensor([[0, 1, 1]]),
        span_mask=torch.tensor([[True, True, True]]),
        span_targets=torch.tensor([[1, 0, 2]]),
    )
    assert output["logits"].shape == (1, 3, 3)
    assert torch.isfinite(output["loss"])
