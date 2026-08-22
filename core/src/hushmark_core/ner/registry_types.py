"""Structural model-registry types without backend import cycles."""

from typing import Protocol


class ModelSpecLike(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def architecture(self) -> str: ...

    @property
    def primary_file(self) -> str: ...

    @property
    def artifact_sha256(self) -> str: ...

    @property
    def sha256(self) -> str: ...

    @property
    def size(self) -> int: ...

    @property
    def labels(self) -> dict[str, str]: ...

    @property
    def onnx_confidence_scale(self) -> float: ...

    @property
    def onnx_file(self) -> str | None: ...

    @property
    def onnx_size(self) -> int | None: ...

    @property
    def onnx_sha256(self) -> str | None: ...

    @property
    def runtime_files(self) -> tuple[tuple[str, int, str], ...]: ...
