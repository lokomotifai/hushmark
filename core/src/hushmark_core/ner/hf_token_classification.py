"""Offline Hugging Face token-classification adapter with pinned remote code."""

from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from hashlib import file_digest
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from hushmark_core.ner.base import NerSpan
from hushmark_core.ner.decode_bio import (
    TokenPrediction,
    decode_bio_predictions,
    merge_chunk_spans,
)
from hushmark_core.ner.integrity import verify_runtime_artifacts
from hushmark_core.ner.registry_types import ModelSpecLike

if TYPE_CHECKING:
    from torch import Tensor

DEFAULT_MAX_LENGTH = 8192
DEFAULT_STRIDE = 256


class TokenClassifierOutputLike(Protocol):
    @property
    def logits(self) -> Tensor: ...


class TokenClassifierModel(Protocol):
    def eval(self) -> TokenClassifierModel: ...

    def __call__(
        self,
        *,
        input_ids: Tensor,
        attention_mask: Tensor,
    ) -> TokenClassifierOutputLike: ...


class FastTokenizer(Protocol):
    @property
    def model_max_length(self) -> int: ...

    def __call__(
        self,
        text: str,
        *,
        return_offsets_mapping: bool,
        return_overflowing_tokens: bool,
        truncation: bool,
        max_length: int,
        stride: int,
        padding: bool,
        return_tensors: str,
    ) -> Mapping[str, Tensor]: ...


class HfTokenClassificationBackend:
    def __init__(
        self,
        *,
        model_dir: Path,
        spec: ModelSpecLike,
        max_length: int = DEFAULT_MAX_LENGTH,
        stride: int = DEFAULT_STRIDE,
    ) -> None:
        self._model_dir = model_dir
        self._spec = spec
        self._max_length = max_length
        self._stride = stride
        self._model: TokenClassifierModel | None = None
        self._tokenizer: FastTokenizer | None = None
        self._id2label: dict[int, str] = {}
        self._measured_sha256: str | None = None
        self._label_to_type = dict(spec.label_to_type)

    @property
    def model_id(self) -> str:
        return self._spec.id

    @property
    def model_sha256(self) -> str | None:
        return self._measured_sha256

    def load(self) -> None:
        if self._model is not None:
            return
        weight_file = self._model_dir / self._spec.weight_file
        if not weight_file.is_file():
            raise FileNotFoundError(
                f"model weights are not installed at {self._model_dir}; "
                f"run scripts/fetch-models.py {self._spec.id}"
            )
        if weight_file.stat().st_size != self._spec.size:
            raise ValueError(f"model weight size verification failed: {weight_file}")
        with weight_file.open("rb") as weight_stream:
            measured_sha256 = file_digest(weight_stream, "sha256").hexdigest()
        if measured_sha256 != self._spec.sha256:
            raise ValueError(f"model weight SHA-256 verification failed: {weight_file}")
        # Every runtime artifact, including the pinned remote-code module, is
        # hash-verified above/below before transformers may execute it.
        verify_runtime_artifacts(self._model_dir, self._spec)
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        transformers_module = importlib.import_module("transformers")
        tokenizer = transformers_module.AutoTokenizer.from_pretrained(
            str(self._model_dir),
            local_files_only=True,
        )
        if not bool(getattr(tokenizer, "is_fast", False)):
            raise ValueError(f"model {self._spec.id} requires a fast tokenizer with offset mapping")
        model = transformers_module.AutoModelForTokenClassification.from_pretrained(
            str(self._model_dir),
            local_files_only=True,
            trust_remote_code=True,
        )
        raw_id2label = getattr(model.config, "id2label", None)
        if not isinstance(raw_id2label, Mapping) or not raw_id2label:
            raise ValueError(f"model {self._spec.id} declares no id2label mapping")
        self._id2label = {int(key): str(value) for key, value in raw_id2label.items()}
        self._measured_sha256 = measured_sha256
        self._tokenizer = cast(FastTokenizer, tokenizer)
        self._model = cast(TokenClassifierModel, model.eval())

    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        if self._model is None:
            self.load()
        assert self._model is not None
        assert self._tokenizer is not None
        import torch

        max_length = min(self._max_length, int(self._tokenizer.model_max_length))
        encoding = self._tokenizer(
            text,
            return_offsets_mapping=True,
            return_overflowing_tokens=True,
            truncation=True,
            max_length=max_length,
            stride=self._stride,
            padding=True,
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"]
        attention_mask = encoding["attention_mask"]
        offset_mapping = encoding["offset_mapping"]
        with torch.no_grad():
            logits = self._model(input_ids=input_ids, attention_mask=attention_mask).logits
        probabilities = torch.softmax(logits, dim=-1)
        scores, label_ids = probabilities.max(dim=-1)
        spans: list[NerSpan] = []
        for chunk_index in range(int(offset_mapping.shape[0])):
            chunk_tokens: list[TokenPrediction] = []
            for token_index in range(int(offset_mapping.shape[1])):
                if int(attention_mask[chunk_index, token_index].item()) != 1:
                    continue
                label_id = int(label_ids[chunk_index, token_index].item())
                label = self._id2label.get(label_id)
                if label is None:
                    raise ValueError(f"model emitted an unknown label id: {label_id}")
                chunk_tokens.append(
                    TokenPrediction(
                        label=label,
                        score=float(scores[chunk_index, token_index].item()),
                        start=int(offset_mapping[chunk_index, token_index, 0].item()),
                        end=int(offset_mapping[chunk_index, token_index, 1].item()),
                    )
                )
            spans.extend(decode_bio_predictions(chunk_tokens, self._label_to_type))
        results: list[NerSpan] = []
        for span in merge_chunk_spans(spans):
            if span.confidence < threshold:
                continue
            # The tokenizer's offset mapping folds leading whitespace into the
            # first token of a word; trim it so placeholders replace only the
            # entity text.
            start, end = span.start, span.end
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if start < end:
                results.append(NerSpan(span.entity_type, start, end, span.confidence))
        return results
