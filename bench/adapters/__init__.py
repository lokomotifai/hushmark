"""Compatibility namespace for plan-specified adapter paths."""

from hushmark_bench.adapters.core_adapter import CoreAdapter
from hushmark_bench.adapters.presidio_default import PresidioDefaultAdapter

__all__ = ["CoreAdapter", "PresidioDefaultAdapter"]
