"""JSON persistence for SideNote opt-out state."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from noeticbraid_core.schemas.side_note_opt_out import SideNoteOptOutState

LOGGER = logging.getLogger(__name__)
OPT_OUT_STATE_ENV_VAR = "NOETICBRAID_SIDE_NOTE_OPT_OUT_PATH"
DEFAULT_OPT_OUT_STATE_PATH = Path("~/.noeticbraid/side_note_opt_out.json")


def _resolve_path(path: Path | None = None) -> Path:
    """Resolve the opt-out state path, honoring explicit and env overrides."""

    if path is not None:
        return Path(path).expanduser()
    env_path = os.environ.get(OPT_OUT_STATE_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_OPT_OUT_STATE_PATH.expanduser()


def load_opt_out_state(path: Path | None = None) -> SideNoteOptOutState:
    """Load opt-out state from JSON, falling back permissively on corruption."""

    target = _resolve_path(path)
    if not target.exists():
        return SideNoteOptOutState()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("opt-out state must be a JSON object")
        return SideNoteOptOutState.model_validate(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        LOGGER.warning("failed to load SideNote opt-out state from %s; using permissive default: %s", target, exc)
        return SideNoteOptOutState()


def save_opt_out_state(state: SideNoteOptOutState, path: Path | None = None) -> None:
    """Atomically persist opt-out state to JSON."""

    target = _resolve_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = state.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)
