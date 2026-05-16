# SPDX-License-Identifier: Apache-2.0
"""Shared model cost estimation ported from everything-claude-code."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ModelRates:
    """Per-1M-token input/output USD rates."""

    input: float
    output: float


RATE_TABLE = MappingProxyType(
    {
        "haiku": ModelRates(input=0.8, output=4.0),
        "sonnet": ModelRates(input=3.0, output=15.0),
        "opus": ModelRates(input=15.0, output=75.0),
    }
)


def select_model_rates(model: str | None) -> ModelRates:
    """Select rates by substring; default to upstream sonnet rates."""

    normalized = str(model or "").lower()
    rates = RATE_TABLE["sonnet"]
    if "haiku" in normalized:
        rates = RATE_TABLE["haiku"]
    if "opus" in normalized:
        rates = RATE_TABLE["opus"]
    return rates


def estimate_cost(model: str | None, input_tokens: int | float, output_tokens: int | float) -> float:
    """Estimate USD cost, rounded to six decimals like the JS upstream."""

    rates = select_model_rates(model)
    cost = (input_tokens / 1_000_000) * rates.input
    cost += (output_tokens / 1_000_000) * rates.output
    return round(cost, 6)


__all__ = ["RATE_TABLE", "ModelRates", "estimate_cost", "select_model_rates"]
