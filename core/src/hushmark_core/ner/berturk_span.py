"""Fixed-taxonomy span NER head on top of the Turkish BERT encoder."""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import torch
from torch import nn
from torch.nn import functional as F

TOKEN_PATTERN = re.compile(r"\w+(?:[-_]\w+)*|\S", re.UNICODE)


def tokenized_text(text: str) -> list[tuple[str, int, int]]:
    """Split text into the word/punctuation units used during training."""

    return [(match.group(), match.start(), match.end()) for match in TOKEN_PATTERN.finditer(text)]


def candidate_spans(word_count: int, max_width: int) -> list[tuple[int, int]]:
    """Enumerate inclusive word spans in a stable order."""

    if word_count < 0 or max_width < 1:
        raise ValueError("word count and max width are invalid")
    return [
        (start, end)
        for start in range(word_count)
        for end in range(start, min(word_count, start + max_width))
    ]


def training_spans(
    record: Mapping[str, Any],
    label_to_id: Mapping[str, int],
    *,
    max_width: int,
    seed: int,
    negative_ratio: int = 8,
    minimum_negatives: int = 16,
) -> tuple[list[int], list[int], list[int]]:
    """Keep every positive span and a deterministic sample of background spans."""

    tokens = record.get("tokenized_text")
    raw_entities = record.get("ner")
    if not isinstance(tokens, list) or not isinstance(raw_entities, list):
        raise ValueError("span training record is malformed")
    positives: dict[tuple[int, int], int] = {}
    for raw in raw_entities:
        if (
            not isinstance(raw, list)
            or len(raw) != 3
            or not isinstance(raw[0], int)
            or not isinstance(raw[1], int)
            or not isinstance(raw[2], str)
        ):
            raise ValueError("span training entity is malformed")
        start, end, label = raw
        if label not in label_to_id:
            raise ValueError(f"unknown model label: {label}")
        if end - start + 1 > max_width:
            raise ValueError("gold entity exceeds the configured maximum span width")
        key = (start, end)
        target = label_to_id[label]
        if key in positives and positives[key] != target:
            raise ValueError("one gold span has conflicting labels")
        positives[key] = target

    negatives = [span for span in candidate_spans(len(tokens), max_width) if span not in positives]
    record_id = str(record.get("id", "unknown"))
    digest = hashlib.sha256(f"{seed}:{record_id}".encode()).hexdigest()
    random.Random(digest).shuffle(negatives)
    negative_count = min(
        len(negatives),
        max(minimum_negatives, len(positives) * negative_ratio),
    )
    selected = [(*span, target) for span, target in sorted(positives.items())]
    selected.extend((*span, 0) for span in negatives[:negative_count])
    if not selected:
        raise ValueError("span training record produced no candidates")
    return (
        [start for start, _, _ in selected],
        [end for _, end, _ in selected],
        [target for _, _, target in selected],
    )


class SpanBatchCollator:
    """Tokenize pre-split words and construct padded span tensors."""

    def __init__(
        self,
        tokenizer: Any,
        label_names: Sequence[str],
        *,
        max_length: int,
        max_width: int,
        seed: int,
        training: bool,
        negative_ratio: int = 8,
        minimum_negatives: int = 16,
    ) -> None:
        if not getattr(tokenizer, "is_fast", False):
            raise ValueError("BERTurk span alignment requires a fast tokenizer")
        if max_length < 8 or max_width < 1 or not label_names:
            raise ValueError("span collator configuration is invalid")
        self.tokenizer = tokenizer
        self.label_names = tuple(label_names)
        self.label_to_id = {label: index + 1 for index, label in enumerate(label_names)}
        self.max_length = max_length
        self.max_width = max_width
        self.seed = seed
        self.training = training
        self.negative_ratio = negative_ratio
        self.minimum_negatives = minimum_negatives

    def __call__(self, records: Sequence[Mapping[str, Any]]) -> dict[str, torch.Tensor]:
        if not records:
            raise ValueError("cannot collate an empty batch")
        raw_token_lists = [record.get("tokenized_text") for record in records]
        if not all(
            isinstance(tokens, list)
            and tokens
            and all(isinstance(token, str) and token for token in tokens)
            for tokens in raw_token_lists
        ):
            raise ValueError("span batch contains invalid token lists")
        token_lists = cast(list[list[str]], raw_token_lists)
        encoded = self.tokenizer(
            token_lists,
            is_split_into_words=True,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )

        word_start_rows: list[list[int]] = []
        word_mask_rows: list[list[bool]] = []
        span_start_rows: list[list[int]] = []
        span_end_rows: list[list[int]] = []
        span_target_rows: list[list[int]] = []
        for batch_index, (record, raw_tokens) in enumerate(zip(records, token_lists, strict=True)):
            tokens = list(raw_tokens)
            word_ids = encoded.word_ids(batch_index=batch_index)
            first_subword: dict[int, int] = {}
            for token_index, word_id in enumerate(word_ids):
                if word_id is not None and word_id not in first_subword:
                    first_subword[word_id] = token_index
            if len(first_subword) != len(tokens):
                raise ValueError(
                    f"record {record.get('id', 'unknown')} exceeds max_length={self.max_length}"
                )
            word_start_rows.append([first_subword[index] for index in range(len(tokens))])
            word_mask_rows.append([True] * len(tokens))
            if self.training:
                starts, ends, targets = training_spans(
                    record,
                    self.label_to_id,
                    max_width=self.max_width,
                    seed=self.seed,
                    negative_ratio=self.negative_ratio,
                    minimum_negatives=self.minimum_negatives,
                )
            else:
                spans = candidate_spans(len(tokens), self.max_width)
                starts = [start for start, _ in spans]
                ends = [end for _, end in spans]
                targets = [0] * len(spans)
            span_start_rows.append(starts)
            span_end_rows.append(ends)
            span_target_rows.append(targets)

        max_words = max(map(len, word_start_rows))
        max_spans = max(map(len, span_start_rows))

        def padded(values: Sequence[int], size: int, fill: int = 0) -> list[int]:
            return [*values, *([fill] * (size - len(values)))]

        batch: dict[str, torch.Tensor] = {
            key: value for key, value in encoded.items() if isinstance(value, torch.Tensor)
        }
        batch.update(
            {
                "word_starts": torch.tensor(
                    [padded(row, max_words) for row in word_start_rows], dtype=torch.long
                ),
                "word_mask": torch.tensor(
                    [padded(row, max_words, False) for row in word_mask_rows], dtype=torch.bool
                ),
                "span_starts": torch.tensor(
                    [padded(row, max_spans) for row in span_start_rows], dtype=torch.long
                ),
                "span_ends": torch.tensor(
                    [padded(row, max_spans) for row in span_end_rows], dtype=torch.long
                ),
                "span_mask": torch.tensor(
                    [padded([True] * len(row), max_spans, False) for row in span_start_rows],
                    dtype=torch.bool,
                ),
                "span_targets": torch.tensor(
                    [padded(row, max_spans) for row in span_target_rows], dtype=torch.long
                ),
            }
        )
        return batch


class BerturkSpanModel(nn.Module):
    """BERTurk encoder with a closed, non-overlapping word-span classifier."""

    def __init__(
        self,
        encoder: nn.Module,
        tokenizer: Any,
        label_names: Sequence[str],
        *,
        max_length: int = 256,
        max_width: int = 24,
        width_embedding_size: int = 32,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        encoder_config: Any = encoder.config
        hidden_size = int(encoder_config.hidden_size)
        if (
            hidden_size < 1
            or max_length < 8
            or max_width < 1
            or not label_names
            or len(set(label_names)) != len(label_names)
        ):
            raise ValueError("BERTurk span model configuration is invalid")
        self.encoder = encoder
        self.tokenizer = tokenizer
        self.label_names = tuple(label_names)
        self.max_length = max_length
        self.max_width = max_width
        self.width_embedding_size = width_embedding_size
        self.dropout_probability = dropout
        self.width_embedding = nn.Embedding(max_width + 1, width_embedding_size)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size * 3 + width_embedding_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, len(label_names) + 1),
        )

    def forward(
        self,
        *,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        word_starts: torch.Tensor,
        word_mask: torch.Tensor,
        span_starts: torch.Tensor,
        span_ends: torch.Tensor,
        span_mask: torch.Tensor,
        span_targets: torch.Tensor | None = None,
        token_type_ids: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        encoder_inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
        if token_type_ids is not None:
            encoder_inputs["token_type_ids"] = token_type_ids
        hidden = self.encoder(**encoder_inputs).last_hidden_state
        hidden_size = hidden.shape[-1]
        word_index = word_starts.unsqueeze(-1).expand(-1, -1, hidden_size)
        words = hidden.gather(1, word_index)
        words = words * word_mask.unsqueeze(-1)

        span_index_start = span_starts.unsqueeze(-1).expand(-1, -1, hidden_size)
        span_index_end = span_ends.unsqueeze(-1).expand(-1, -1, hidden_size)
        start_vectors = words.gather(1, span_index_start)
        end_vectors = words.gather(1, span_index_end)
        prefix = F.pad(words.cumsum(dim=1), (0, 0, 1, 0))
        prefix_start = prefix.gather(1, span_index_start)
        prefix_end = prefix.gather(1, (span_ends + 1).unsqueeze(-1).expand_as(span_index_end))
        widths = span_ends - span_starts + 1
        mean_vectors = (prefix_end - prefix_start) / widths.clamp_min(1).unsqueeze(-1)
        features = torch.cat(
            [
                start_vectors,
                end_vectors,
                mean_vectors,
                self.width_embedding(widths.clamp(0, self.max_width)),
            ],
            dim=-1,
        )
        logits = self.classifier(features)
        result = {"logits": logits}
        if span_targets is not None:
            active_logits = logits[span_mask]
            active_targets = span_targets[span_mask]
            class_weights = torch.ones(
                len(self.label_names) + 1,
                dtype=active_logits.dtype,
                device=active_logits.device,
            )
            class_weights[0] = 0.25
            result["loss"] = F.cross_entropy(
                active_logits.float(), active_targets, weight=class_weights.float()
            )
        return result

    @property
    def device(self) -> torch.device:
        return next(self.parameters()).device

    def make_collator(self, *, training: bool, seed: int) -> SpanBatchCollator:
        return SpanBatchCollator(
            self.tokenizer,
            self.label_names,
            max_length=self.max_length,
            max_width=self.max_width,
            seed=seed,
            training=training,
        )

    def inference(
        self,
        texts: list[str],
        labels: list[str],
        *,
        threshold: float,
        batch_size: int,
    ) -> list[list[dict[str, object]]]:
        from torch.utils.data import DataLoader

        if set(labels) != set(self.label_names) or not 0.0 <= threshold <= 1.0:
            raise ValueError("inference label set or threshold is invalid")
        if batch_size < 1:
            raise ValueError("inference batch size must be positive")
        records: list[dict[str, Any]] = []
        offsets_by_record: list[list[tuple[int, int]]] = []
        for index, text in enumerate(texts):
            pieces = tokenized_text(text)
            if not pieces:
                records.append({"id": f"inference-{index}", "tokenized_text": ["[PAD]"], "ner": []})
                offsets_by_record.append([])
                continue
            records.append(
                {
                    "id": f"inference-{index}",
                    "tokenized_text": [token for token, _, _ in pieces],
                    "ner": [],
                }
            )
            offsets_by_record.append([(start, end) for _, start, end in pieces])

        loader: Any = DataLoader(
            cast(Any, records),
            batch_size=batch_size,
            shuffle=False,
            collate_fn=self.make_collator(training=False, seed=0),
        )
        documents: list[list[dict[str, object]]] = []
        record_offset = 0
        was_training = self.training
        self.eval()
        with torch.inference_mode():
            for batch in loader:
                batch = {key: value.to(self.device) for key, value in batch.items()}
                output = self(
                    **{key: value for key, value in batch.items() if key != "span_targets"}
                )
                probabilities = output["logits"].float().softmax(dim=-1)
                scores, label_ids = probabilities[..., 1:].max(dim=-1)
                for row_index in range(scores.shape[0]):
                    offsets = offsets_by_record[record_offset + row_index]
                    if not offsets:
                        documents.append([])
                        continue
                    active = int(batch["span_mask"][row_index].sum().item())
                    candidates: list[tuple[float, int, int, int]] = []
                    for span_index in range(active):
                        score = float(scores[row_index, span_index])
                        if score < threshold:
                            continue
                        start = int(batch["span_starts"][row_index, span_index])
                        end = int(batch["span_ends"][row_index, span_index])
                        label_id = int(label_ids[row_index, span_index])
                        candidates.append((score, start, end, label_id))
                    selected: list[tuple[float, int, int, int]] = []
                    occupied: set[int] = set()
                    for candidate in sorted(
                        candidates,
                        key=lambda value: (-value[0], value[2] - value[1], value[1]),
                    ):
                        _, start, end, _ = candidate
                        covered = set(range(start, end + 1))
                        if occupied & covered:
                            continue
                        selected.append(candidate)
                        occupied.update(covered)
                    documents.append(
                        [
                            {
                                "label": self.label_names[label_id],
                                "start": offsets[start][0],
                                "end": offsets[end][1],
                                "score": score,
                            }
                            for score, start, end, label_id in sorted(
                                selected, key=lambda value: (value[1], value[2])
                            )
                        ]
                    )
                record_offset += scores.shape[0]
        self.train(was_training)
        return documents

    def predict_entities(
        self,
        text: str,
        labels: list[str],
        threshold: float,
    ) -> list[dict[str, object]]:
        return self.inference([text], labels, threshold=threshold, batch_size=1)[0]

    def save_artifact(self, output: Path) -> None:
        from safetensors.torch import save_file

        output.mkdir(parents=True, exist_ok=True)
        encoder_to_save: Any = self.encoder
        encoder_to_save.save_pretrained(output / "encoder", safe_serialization=True)
        self.tokenizer.save_pretrained(output / "tokenizer")
        head_state = {
            name: value.detach().cpu().contiguous()
            for name, value in self.state_dict().items()
            if not name.startswith("encoder.")
        }
        save_file(head_state, output / "span_head.safetensors")
        (output / "hushmark_span_config.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "architecture": "berturk-fixed-span-ner",
                    "label_names": list(self.label_names),
                    "max_length": self.max_length,
                    "max_width": self.max_width,
                    "width_embedding_size": self.width_embedding_size,
                    "dropout": self.dropout_probability,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load_artifact(cls, source: Path, *, local_files_only: bool = True) -> BerturkSpanModel:
        from safetensors.torch import load_file
        from transformers import AutoModel, AutoTokenizer

        config = json.loads((source / "hushmark_span_config.json").read_text(encoding="utf-8"))
        if not isinstance(config, dict) or config.get("schema_version") != 1:
            raise ValueError("unsupported BERTurk span artifact config")
        if config.get("architecture") != "berturk-fixed-span-ner":
            raise ValueError("unexpected BERTurk span architecture")
        label_names = config.get("label_names")
        if not isinstance(label_names, list) or not all(
            isinstance(label, str) for label in label_names
        ):
            raise ValueError("BERTurk span artifact has invalid labels")
        encoder = AutoModel.from_pretrained(
            source / "encoder", local_files_only=local_files_only, use_safetensors=True
        )
        tokenizer = AutoTokenizer.from_pretrained(
            source / "tokenizer", local_files_only=local_files_only, use_fast=True
        )
        model = cls(
            encoder,
            tokenizer,
            label_names,
            max_length=int(config["max_length"]),
            max_width=int(config["max_width"]),
            width_embedding_size=int(config["width_embedding_size"]),
            dropout=float(config["dropout"]),
        )
        missing, unexpected = model.load_state_dict(
            load_file(source / "span_head.safetensors"), strict=False
        )
        missing_head = [name for name in missing if not name.startswith("encoder.")]
        if missing_head or unexpected:
            raise ValueError(
                f"span head state is incompatible: missing={missing_head}, unexpected={unexpected}"
            )
        return model
