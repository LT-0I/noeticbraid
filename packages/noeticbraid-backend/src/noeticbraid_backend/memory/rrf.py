# SPDX-License-Identifier: Apache-2.0
"""Reciprocal Rank Fusion merge ported from TencentDB-Agent-Memory."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, is_dataclass
from typing import Any, TypeVar

T = TypeVar("T")
RRF_K = 60


def _attach_score(item: T, score: float) -> dict[str, Any]:
    if isinstance(item, Mapping):
        out = dict(item)
    elif is_dataclass(item) and not isinstance(item, type):
        out = asdict(item)
    else:
        out = {"item": item}
    out["rrfScore"] = score
    return out


def rrf_merge(
    lists: Iterable[Iterable[T]],
    get_id: Callable[[T], str],
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    """Merge ranked lists by `sum(1 / (k + rank + 1))`."""

    merged: dict[str, tuple[T, float]] = {}
    for ranked_list in lists:
        for rank, item in enumerate(ranked_list):
            item_id = get_id(item)
            score = 1 / (k + rank + 1)
            if item_id in merged:
                existing_item, existing_score = merged[item_id]
                merged[item_id] = (existing_item, existing_score + score)
            else:
                merged[item_id] = (item, score)
    return [
        _attach_score(item, score)
        for item, score in sorted(merged.values(), key=lambda entry: entry[1], reverse=True)
    ]


__all__ = ["RRF_K", "rrf_merge"]
