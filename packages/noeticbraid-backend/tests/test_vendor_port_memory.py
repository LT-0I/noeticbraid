# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Parity tests for additive memory vendor-port adapters."""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest
from pydantic import ValidationError

from noeticbraid_backend.memory.l0 import (
    extract_user_assistant_messages,
    prepare_l0_capture,
    sanitize_text,
    should_capture_l0,
    strip_code_blocks,
)
from noeticbraid_backend.memory.recall_ranker import (
    RecallResult,
    RecencyDecayConfig,
    apply_recency_boost,
    apply_source_boost,
    dedup_results,
    enforce_token_budget,
    estimate_tokens,
    rank_recall_results,
    result_tokens,
)
from noeticbraid_backend.memory.rrf import rrf_merge
from noeticbraid_backend.memory.schemas import ContextPack, MemoryItem, MemorySource


def _result(
    slug: str,
    score: float,
    text: str,
    *,
    source: str = "chunk",
    kind: str = "note",
    source_id: str | None = None,
    effective_date: datetime | None = None,
) -> RecallResult:
    return RecallResult(
        slug=slug,
        title=slug,
        chunk_text=text,
        score=score,
        type=kind,
        chunk_source=source,
        source_id=source_id,
        effective_date=effective_date,
    )


def test_rrf_merge_sums_duplicate_ids_and_preserves_top_item_payload() -> None:
    merged = rrf_merge(
        [
            [{"id": "a", "ranker": "fts"}, {"id": "b", "ranker": "fts"}],
            [{"id": "b", "ranker": "vec"}, {"id": "a", "ranker": "vec"}],
        ],
        lambda item: item["id"],
    )

    assert [item["id"] for item in merged] == ["a", "b"]
    assert merged[0]["ranker"] == "fts"
    assert merged[0]["rrfScore"] == pytest.approx(1 / 61 + 1 / 62)
    assert merged[1]["rrfScore"] == pytest.approx(1 / 62 + 1 / 61)


def test_token_budget_uses_char_four_heuristic_and_strict_cap() -> None:
    first = _result("a", 1, "abcd", kind="note")
    second = _result("b", 0.9, "abcdefgh", kind="note")

    assert estimate_tokens("") == 0
    assert estimate_tokens("a") == 1
    assert result_tokens(first) == 2

    no_budget = enforce_token_budget([first, second], None)
    assert no_budget.meta.used == result_tokens(first) + result_tokens(second)
    assert no_budget.meta.dropped == 0

    capped = enforce_token_budget([first, second], 2)
    assert capped.results == (first,)
    assert capped.meta.kept == 1
    assert capped.meta.dropped == 1

    too_small = enforce_token_budget([first, second], 1)
    assert too_small.results == ()
    assert too_small.meta.dropped == 2


def test_recall_ranker_text_similarity_matches_js_whitespace_split_parity() -> None:
    empty_dup = dedup_results(
        [
            _result("empty-a", 1.0, ""),
            _result("empty-b", 0.9, ""),
        ],
        cosine_threshold=0.85,
        max_type_ratio=1.0,
    )
    assert [item.slug for item in empty_dup] == ["empty-a"]

    assert set(re.split(r"\s+", " a".lower())) == {"", "a"}

    leading_whitespace = dedup_results(
        [
            _result("leading", 1.0, " a"),
            _result("plain", 0.9, "a"),
        ],
        cosine_threshold=0.85,
        max_type_ratio=1.0,
    )
    assert [item.slug for item in leading_whitespace] == ["leading", "plain"]


def test_dedup_pipeline_caps_pages_and_guarantees_compiled_truth() -> None:
    items = [
        _result("page", 1.0, "alpha beta gamma", source="chunk", kind="note"),
        _result("page", 0.9, "delta epsilon zeta", source="chunk", kind="note"),
        _result("page", 0.2, "compiled canonical fact", source="compiled_truth", kind="note"),
        _result("other", 0.8, "alpha beta gamma", source="chunk", kind="guide"),
        _result("same-slug", 0.7, "source one", source_id="one", kind="guide"),
        _result("same-slug", 0.6, "source two", source_id="two", kind="guide"),
    ]

    deduped = dedup_results(items, cosine_threshold=0.85, max_type_ratio=1.0, max_per_page=2)
    page_items = [item for item in deduped if item.slug == "page"]
    assert len(page_items) == 2
    assert any(item.chunk_source == "compiled_truth" for item in page_items)
    assert len([item for item in deduped if item.slug == "same-slug"]) == 2
    assert len([item for item in deduped if item.chunk_text == "alpha beta gamma"]) == 1


def test_source_and_recency_boosts_feed_ranker() -> None:
    now = datetime(2026, 5, 16, tzinfo=UTC)
    recent = _result(
        "daily/today",
        1.0,
        "recent note",
        effective_date=now - timedelta(days=7),
    )
    old = _result(
        "concepts/evergreen",
        1.0,
        "evergreen note",
        effective_date=now - timedelta(days=7),
    )

    source_boosted = apply_source_boost(
        [recent, old],
        {"daily/": 2.0, "daily/t": 3.0, "concepts/": 1.0},
    )
    assert source_boosted[0].score == 3.0
    assert source_boosted[1].score == 1.0

    recency_boosted = apply_recency_boost(
        [recent, old],
        {
            "daily/": RecencyDecayConfig(halflife_days=7, coefficient=1.0),
            "concepts/": RecencyDecayConfig(halflife_days=0, coefficient=0),
        },
        now=now,
    )
    assert recency_boosted[0].score == pytest.approx(1.5)
    assert recency_boosted[1].score == 1.0

    ranked = rank_recall_results(
        [old, recent],
        source_boosts={"daily/": 2.0},
        recency_decay={"daily/": RecencyDecayConfig(halflife_days=7, coefficient=1.0)},
        recency_strength="on",
        token_budget=20,
        now=now,
    )
    assert ranked.results[0].slug == "daily/today"


def test_memory_schemas_accept_upstream_aliases_and_reject_invalid_values() -> None:
    item = MemoryItem.model_validate(
        {
            "id": "m1",
            "projectId": "p1",
            "kind": "observation",
            "type": "note",
            "createdAtEpoch": 1,
            "updatedAtEpoch": 2,
        }
    )
    assert item.project_id == "p1"
    assert item.facts == []
    assert item.model_dump(by_alias=True)["projectId"] == "p1"

    source = MemorySource.model_validate(
        {
            "id": "s1",
            "memoryItemId": "m1",
            "sourceType": "manual",
            "createdAtEpoch": 3,
        }
    )
    pack = ContextPack.model_validate(
        {
            "projectId": "p1",
            "generatedAtEpoch": 4,
            "tokenBudget": 100,
            "items": [item.model_dump(by_alias=True)],
        }
    )
    assert source.source_type == "manual"
    assert pack.items[0].id == "m1"

    with pytest.raises(ValidationError):
        MemoryItem.model_validate(
            {
                "id": "m2",
                "projectId": "p1",
                "kind": "unknown",
                "type": "note",
                "createdAtEpoch": 1,
                "updatedAtEpoch": 2,
            }
        )


def test_l0_capture_extracts_sanitizes_filters_and_dedupes() -> None:
    raw = [
        {"role": "system", "content": "ignore", "timestamp": 1},
        {"role": "user", "content": "old", "timestamp": 10, "id": "old"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "<relevant-memories>x</relevant-memories>Clean ask"},
            ],
            "timestamp": 20,
            "id": "u1",
        },
        {
            "role": "assistant",
            "content": "Answer\n```python\nprint('x')\n```\nDone",
            "timestamp": 30,
            "id": "a1",
        },
        {"role": "user", "content": "/reset", "timestamp": 40, "id": "cmd"},
    ]

    extracted = extract_user_assistant_messages(raw, now_ms=99)
    assert [message.id for message in extracted] == ["old", "u1", "a1", "cmd"]
    assert sanitize_text("A\n\n\nB") == "A\n\nB"
    assert strip_code_blocks("A\n```ts\nconst x = 1\n```\nB") == "A\n\nB"
    assert not should_capture_l0("/new")

    batch = prepare_l0_capture(
        session_key="sk",
        session_id="sid",
        raw_messages=raw,
        after_timestamp=10,
        original_user_text="Original clean ask",
        original_user_message_count=2,
        recorded_at=datetime(2026, 5, 16, tzinfo=UTC),
        seen_ids={"a1"},
    )
    assert [record.id for record in batch.records] == ["u1"]
    assert batch.records[0].content == "Original clean ask"
    assert batch.records[0].to_json_dict()["sessionKey"] == "sk"
    assert batch.max_timestamp == 20
