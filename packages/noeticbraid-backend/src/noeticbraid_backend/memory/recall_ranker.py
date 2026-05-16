# SPDX-License-Identifier: Apache-2.0
"""Recall ranking hygiene primitives ported from gbrain search utilities."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from datetime import UTC, datetime
from typing import Literal, Mapping, Sequence


@dataclass(frozen=True)
class RecallResult:
    """Small Python search-result shape used by the adapter."""

    slug: str
    title: str
    chunk_text: str
    score: float
    type: str
    chunk_source: str = "chunk"
    source_id: str | None = None
    effective_date: datetime | None = None


@dataclass(frozen=True)
class TokenBudgetMeta:
    budget: int
    used: int
    dropped: int
    kept: int


@dataclass(frozen=True)
class TokenBudgetResult:
    results: tuple[RecallResult, ...]
    meta: TokenBudgetMeta


@dataclass(frozen=True)
class RecencyDecayConfig:
    halflife_days: float
    coefficient: float


RecencyStrength = Literal["off", "on", "strong"]

COSINE_DEDUP_THRESHOLD = 0.85
MAX_TYPE_RATIO = 0.6
MAX_PER_PAGE = 2
DEFAULT_FALLBACK_RECENCY = RecencyDecayConfig(halflife_days=90, coefficient=0.5)


def _page_key(result: RecallResult) -> str:
    source = result.source_id or "default"
    return f"{source}:{result.slug}"


def estimate_tokens(text: str | None) -> int:
    """Cheap char/4 token estimate; empty strings cost zero."""

    if not text:
        return 0
    return (len(text) + 3) // 4


def result_tokens(result: RecallResult) -> int:
    """Token cost for title plus chunk text, matching upstream."""

    return estimate_tokens(result.title) + estimate_tokens(result.chunk_text)


def enforce_token_budget(
    results: Sequence[RecallResult],
    budget: int | None,
) -> TokenBudgetResult:
    """Greedy top-down budget enforcement preserving caller ranking."""

    safe_budget = budget if isinstance(budget, int) and budget > 0 else 0
    result_tuple = tuple(results)
    if safe_budget == 0 or not result_tuple:
        used = sum(result_tokens(item) for item in result_tuple)
        return TokenBudgetResult(
            results=result_tuple,
            meta=TokenBudgetMeta(
                budget=safe_budget,
                used=used,
                dropped=0,
                kept=len(result_tuple),
            ),
        )

    kept: list[RecallResult] = []
    used = 0
    for item in result_tuple:
        cost = result_tokens(item)
        if used + cost > safe_budget:
            break
        kept.append(item)
        used += cost
    return TokenBudgetResult(
        results=tuple(kept),
        meta=TokenBudgetMeta(
            budget=safe_budget,
            used=used,
            dropped=len(result_tuple) - len(kept),
            kept=len(kept),
        ),
    )


def dedup_results(
    results: Sequence[RecallResult],
    *,
    cosine_threshold: float = COSINE_DEDUP_THRESHOLD,
    max_type_ratio: float = MAX_TYPE_RATIO,
    max_per_page: int = MAX_PER_PAGE,
) -> list[RecallResult]:
    """Apply gbrain's layered dedup pipeline with compiled-truth guarantee."""

    pre_dedup = list(results)
    deduped = _dedup_by_source(pre_dedup)
    deduped = _dedup_by_text_similarity(deduped, cosine_threshold)
    deduped = _enforce_type_diversity(deduped, max_type_ratio)
    deduped = _cap_per_page(deduped, max_per_page)
    return _guarantee_compiled_truth(deduped, pre_dedup)


def _dedup_by_source(results: Sequence[RecallResult]) -> list[RecallResult]:
    by_page: dict[str, list[RecallResult]] = {}
    for item in results:
        by_page.setdefault(_page_key(item), []).append(item)
    kept: list[RecallResult] = []
    for chunks in by_page.values():
        kept.extend(sorted(chunks, key=lambda item: item.score, reverse=True)[:3])
    return sorted(kept, key=lambda item: item.score, reverse=True)


def _dedup_by_text_similarity(
    results: Sequence[RecallResult],
    threshold: float,
) -> list[RecallResult]:
    kept: list[RecallResult] = []
    for item in results:
        item_words = set(re.split(r"\s+", item.chunk_text.lower()))
        too_similar = False
        for kept_item in kept:
            kept_words = set(re.split(r"\s+", kept_item.chunk_text.lower()))
            union = item_words | kept_words
            jaccard = len(item_words & kept_words) / len(union) if union else 0
            if jaccard > threshold:
                too_similar = True
                break
        if not too_similar:
            kept.append(item)
    return kept


def _enforce_type_diversity(
    results: Sequence[RecallResult],
    max_ratio: float,
) -> list[RecallResult]:
    max_per_type = max(1, _ceil(len(results) * max_ratio))
    type_counts: dict[str, int] = {}
    kept: list[RecallResult] = []
    for item in results:
        count = type_counts.get(item.type, 0)
        if count < max_per_type:
            kept.append(item)
            type_counts[item.type] = count + 1
    return kept


def _ceil(value: float) -> int:
    as_int = int(value)
    return as_int if value == as_int else as_int + 1


def _cap_per_page(results: Sequence[RecallResult], max_per_page: int) -> list[RecallResult]:
    page_counts: dict[str, int] = {}
    kept: list[RecallResult] = []
    for item in results:
        key = _page_key(item)
        count = page_counts.get(key, 0)
        if count < max_per_page:
            kept.append(item)
            page_counts[key] = count + 1
    return kept


def _guarantee_compiled_truth(
    results: Sequence[RecallResult],
    pre_dedup: Sequence[RecallResult],
) -> list[RecallResult]:
    by_page: dict[str, list[RecallResult]] = {}
    for item in results:
        by_page.setdefault(_page_key(item), []).append(item)
    output = list(results)
    for key, page_chunks in by_page.items():
        if any(item.chunk_source == "compiled_truth" for item in page_chunks):
            continue
        candidates = sorted(
            (
                item
                for item in pre_dedup
                if _page_key(item) == key and item.chunk_source == "compiled_truth"
            ),
            key=lambda item: item.score,
            reverse=True,
        )
        if not candidates:
            continue
        lowest_index = -1
        for index, item in enumerate(output):
            if _page_key(item) != key:
                continue
            if lowest_index == -1 or item.score < output[lowest_index].score:
                lowest_index = index
        if lowest_index != -1:
            output[lowest_index] = candidates[0]
    return output


def apply_source_boost(
    results: Sequence[RecallResult],
    boosts: Mapping[str, float],
) -> list[RecallResult]:
    """Apply longest-prefix source boost factors to scores."""

    prefixes = sorted(boosts, key=len, reverse=True)
    boosted: list[RecallResult] = []
    for item in results:
        factor = 1.0
        for prefix in prefixes:
            if item.slug.startswith(prefix):
                factor = boosts[prefix]
                break
        boosted.append(replace(item, score=item.score * factor))
    return boosted


def apply_recency_boost(
    results: Sequence[RecallResult],
    decay_map: Mapping[str, RecencyDecayConfig],
    *,
    fallback: RecencyDecayConfig = DEFAULT_FALLBACK_RECENCY,
    strength: RecencyStrength = "on",
    now: datetime | None = None,
) -> list[RecallResult]:
    """Apply gbrain's hyperbolic per-prefix recency boost."""

    if strength == "off":
        return list(results)
    now_value = now or datetime.now(UTC)
    if now_value.tzinfo is None:
        now_value = now_value.replace(tzinfo=UTC)
    now_value = now_value.astimezone(UTC)
    strength_mul = 1.5 if strength == "strong" else 1.0
    prefixes = sorted(decay_map, key=len, reverse=True)
    boosted: list[RecallResult] = []
    for item in results:
        if item.effective_date is None:
            boosted.append(item)
            continue
        effective_date = item.effective_date
        if effective_date.tzinfo is None:
            effective_date = effective_date.replace(tzinfo=UTC)
        effective_date = effective_date.astimezone(UTC)
        days_old = max(0.0, (now_value - effective_date).total_seconds() / 86_400)
        config = fallback
        for prefix in prefixes:
            if item.slug.startswith(prefix):
                config = decay_map[prefix]
                break
        if config.halflife_days == 0 or config.coefficient == 0:
            boosted.append(item)
            continue
        component = config.coefficient * config.halflife_days / (
            config.halflife_days + days_old
        )
        boosted.append(replace(item, score=item.score * (1.0 + strength_mul * component)))
    return boosted


def rank_recall_results(
    results: Sequence[RecallResult],
    *,
    source_boosts: Mapping[str, float] | None = None,
    recency_decay: Mapping[str, RecencyDecayConfig] | None = None,
    recency_strength: RecencyStrength = "off",
    token_budget: int | None = None,
    now: datetime | None = None,
) -> TokenBudgetResult:
    """Boost, sort, dedup, then enforce the token budget."""

    ranked = list(results)
    if source_boosts:
        ranked = apply_source_boost(ranked, source_boosts)
    if recency_decay and recency_strength != "off":
        ranked = apply_recency_boost(
            ranked,
            recency_decay,
            strength=recency_strength,
            now=now,
        )
    ranked = sorted(ranked, key=lambda item: item.score, reverse=True)
    ranked = dedup_results(ranked)
    return enforce_token_budget(ranked, token_budget)


__all__ = [
    "COSINE_DEDUP_THRESHOLD",
    "DEFAULT_FALLBACK_RECENCY",
    "MAX_PER_PAGE",
    "MAX_TYPE_RATIO",
    "RecallResult",
    "RecencyDecayConfig",
    "RecencyStrength",
    "TokenBudgetMeta",
    "TokenBudgetResult",
    "apply_recency_boost",
    "apply_source_boost",
    "dedup_results",
    "enforce_token_budget",
    "estimate_tokens",
    "rank_recall_results",
    "result_tokens",
]
