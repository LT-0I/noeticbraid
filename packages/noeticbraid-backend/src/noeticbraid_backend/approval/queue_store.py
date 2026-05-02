# SPDX-License-Identifier: Apache-2.0
"""Small JSONL approval queue reader rooted under Settings.state_dir."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator

from noeticbraid_backend.contracts import ApprovalRequest

APPROVAL_QUEUE_RELATIVE_PATH = Path("approval") / "queue.jsonl"
_FALLBACK_RED_LINE_ACTIONS = frozenset(
    {
        "write_user_raw_vault",
        "rewrite_sidenote_existing",
        "cross_account_transfer",
    }
)

try:  # Backend may import core guard; guard never imports backend.
    from noeticbraid_core.guard import RED_LINE_ACTIONS
except Exception:  # pragma: no cover - fallback for backend skeleton isolation
    _RED_LINE_ACTION_VALUES = _FALLBACK_RED_LINE_ACTIONS
else:
    _RED_LINE_ACTION_VALUES = frozenset(action.value for action in RED_LINE_ACTIONS)


class ApprovalQueueStore:
    """Append/read ApprovalRequest JSONL records with corrupt-row isolation."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / APPROVAL_QUEUE_RELATIVE_PATH

    def append(self, record: ApprovalRequest | dict) -> None:
        """Append one contract-valid approval record for tests and local wiring."""

        approval = ApprovalRequest.model_validate(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(approval.model_dump(mode="json"), sort_keys=False))
            fh.write("\n")

    def extend(self, records: Iterable[ApprovalRequest | dict]) -> None:
        """Append multiple approval records."""

        for record in records:
            self.append(record)

    def iter_records(self) -> Iterator[ApprovalRequest]:
        """Yield valid ApprovalRequest records, skipping corrupt or invalid rows."""

        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    yield ApprovalRequest.model_validate(payload)
                except Exception:
                    continue

    def iter_pending(self) -> Iterator[ApprovalRequest]:
        """Yield pending, user-decision records excluding red-line actions."""

        for record in self.iter_records():
            if _is_red_line_action(record):
                continue
            if _needs_user_decision(record):
                yield record


def _needs_user_decision(record: ApprovalRequest) -> bool:
    method = getattr(record, "needs_user_decision", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            return False
    status = getattr(record, "status", "pending")
    approval_level = getattr(record, "approval_level", "none")
    return status == "pending" and approval_level not in ("none", "forbidden")


def _is_red_line_action(record: ApprovalRequest) -> bool:
    requested_action = getattr(record, "requested_action", "")
    return str(requested_action) in _RED_LINE_ACTION_VALUES


__all__ = ["APPROVAL_QUEUE_RELATIVE_PATH", "ApprovalQueueStore"]
