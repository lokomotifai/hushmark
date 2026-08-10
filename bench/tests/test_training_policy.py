from __future__ import annotations

import torch
from hushmark_bench.training_state import linear_warmup_decay, optimizer_parameter_groups


class TinyModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.token_rep_layer = torch.nn.Module()
        self.token_rep_layer.bert_layer = torch.nn.Linear(2, 2)
        self.head = torch.nn.Linear(2, 1)

    def freeze_component(self, name: str) -> None:
        assert name == "text_encoder"
        for parameter in self.token_rep_layer.bert_layer.parameters():
            parameter.requires_grad = False


def test_optimizer_policy_freezes_encoder_by_default() -> None:
    model = TinyModel()
    groups, trainable = optimizer_parameter_groups(
        model,
        train_text_encoder=False,
        encoder_learning_rate=5e-6,
        head_learning_rate=1e-5,
    )
    assert [group["group_name"] for group in groups] == ["head"]
    assert groups[0]["lr"] == 1e-5
    assert len(trainable) == 2
    assert not any(
        parameter.requires_grad for parameter in model.token_rep_layer.bert_layer.parameters()
    )


def test_optimizer_policy_never_applies_head_rate_to_encoder() -> None:
    groups, _ = optimizer_parameter_groups(
        TinyModel(),
        train_text_encoder=True,
        encoder_learning_rate=5e-6,
        head_learning_rate=1e-5,
    )
    rates = {group["group_name"]: group["lr"] for group in groups}
    assert rates == {"head": 1e-5, "text_encoder": 5e-6}


def test_linear_warmup_decay_is_bounded_and_reaches_zero() -> None:
    assert linear_warmup_decay(0, warmup_steps=10, total_steps=100) == 0.1
    assert linear_warmup_decay(9, warmup_steps=10, total_steps=100) == 1.0
    assert linear_warmup_decay(50, warmup_steps=10, total_steps=100) < 1.0
    assert linear_warmup_decay(100, warmup_steps=10, total_steps=100) == 0.0
