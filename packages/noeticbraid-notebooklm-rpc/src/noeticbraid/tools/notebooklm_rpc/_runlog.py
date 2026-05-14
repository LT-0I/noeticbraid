from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Schema definition (constant; tests assert against this)
PoolEventNDJSONSchema: dict = {
    "version": 1,
    "required_fields": ["ts", "kind", "account_id", "payload"],
    "kind_enum": [
        "pool.pick",
        "pool.mark_success",
        "pool.mark_failure",
        "pool.rotation",
        "pool.quota_exhausted",
        "pool.unavailable",
        "pool.state_persisted",
    ],
}


def _default_runlog_path() -> Path:
    raw = os.environ.get("NOETICBRAID_NOTEBOOKLM_RUNLOG_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".noeticbraid" / "notebooklm" / "runlog.ndjson"


def emit_runlog_event(
    kind: str,
    payload: dict[str, Any],
    *,
    account_id: Optional[str] = None,
    runlog_path: Optional[Path] = None,
    _now_fn=None,
) -> None:
    """Append one JSON line to runlog_path (default: env var or ~/.noeticbraid/notebooklm/runlog.ndjson).
    Schema:
      {"ts": "2026-05-14T12:00:00.000000+00:00", "kind": "pool.pick",
       "account_id": "alice-xxx" | null, "payload": {...}}
    `kind` must be in PoolEventNDJSONSchema["kind_enum"], else raise ValueError.
    Best-effort: any file-IO error is swallowed and printed to stderr; never raises into user code.
    THIS IS NOT FROZEN RUNRECORD 1.0.0 — separate observability channel.
    """

    if kind not in PoolEventNDJSONSchema["kind_enum"]:
        raise ValueError(f"invalid pool runlog kind: {kind}")
    now_fn = _now_fn or (lambda: datetime.now(timezone.utc))
    ts = now_fn()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts = ts.astimezone(timezone.utc)
    event = {
        "ts": ts.isoformat(),
        "kind": kind,
        "account_id": account_id,
        "payload": payload,
    }
    path = Path(runlog_path).expanduser() if runlog_path is not None else _default_runlog_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"warning: failed to write NotebookLM pool runlog {path}: {exc}", file=sys.stderr)
