# SPDX-License-Identifier: Apache-2.0
"""Private JSON/JSONL persistence for local account quota state."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from noeticbraid_core.account.models import (
    AccountRegistryRecord,
    PublicProfileSummary,
    QuotaEventRecord,
    QuotaStateRecord,
    public_summary_from,
)

ACCOUNTS_FILENAME = "accounts.private.json"
STATE_FILENAME = "quota_state.json"
EVENTS_FILENAME = "quota_events.jsonl"


class AccountQuotaStoreError(Exception):
    """Base exception for private account/quota persistence failures."""


class MalformedAccountQuotaState(AccountQuotaStoreError):
    """Raised when private account/quota JSON cannot be trusted."""

    def __init__(self, filename: str, kind: str) -> None:
        super().__init__(f"malformed account quota {kind} in {filename}")
        self.filename = filename
        self.kind = kind


class AccountQuotaStore:
    """Local single-process account pool + quota store.

    This store is guarded only inside the current Python process. Cross-process
    callers must serialize access via an external advisory lock; that broader
    file-lock contract is deferred to the 1.3.x backlog.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: object) -> "AccountQuotaStore":
        """Create a store from a settings-like object with account_quota_dir."""

        try:
            root = getattr(settings, "account_quota_dir")
        except AttributeError:
            raise TypeError("settings must expose account_quota_dir") from None
        return cls(Path(root))

    @property
    def accounts_path(self) -> Path:
        return self.root / ACCOUNTS_FILENAME

    @property
    def state_path(self) -> Path:
        return self.root / STATE_FILENAME

    @property
    def events_path(self) -> Path:
        return self.root / EVENTS_FILENAME

    @contextmanager
    def _store_lock(self):
        with self._lock:
            yield

    def load_registry(self) -> tuple[AccountRegistryRecord, ...]:
        """Load private account registry records; missing file means empty."""

        payload = self._read_json_or_none(self.accounts_path, "registry")
        if payload is None:
            return ()
        if isinstance(payload, dict):
            raw_accounts = payload.get("accounts", [])
        elif isinstance(payload, list):
            raw_accounts = payload
        else:
            raise MalformedAccountQuotaState(self.accounts_path.name, "registry")
        if not isinstance(raw_accounts, list):
            raise MalformedAccountQuotaState(self.accounts_path.name, "registry")
        records: list[AccountRegistryRecord] = []
        try:
            for item in raw_accounts:
                if not isinstance(item, dict):
                    raise TypeError("registry item must be an object")
                records.append(AccountRegistryRecord.model_validate(item))
        except Exception:
            raise MalformedAccountQuotaState(self.accounts_path.name, "registry") from None
        return tuple(records)

    def load_state(self) -> dict[str, QuotaStateRecord]:
        """Load latest quota state by alias; missing file means empty."""

        payload = self._read_json_or_none(self.state_path, "state")
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise MalformedAccountQuotaState(self.state_path.name, "state")
        state: dict[str, QuotaStateRecord] = {}
        try:
            for alias, raw_record in payload.items():
                if not isinstance(alias, str) or not isinstance(raw_record, dict):
                    raise TypeError("state must map alias strings to objects")
                state[alias] = QuotaStateRecord.model_validate(raw_record)
        except Exception:
            raise MalformedAccountQuotaState(self.state_path.name, "state") from None
        return state

    def write_state(self, state: Mapping[str, QuotaStateRecord]) -> None:
        """Atomically replace quota_state.json after parse-valid JSON validation."""

        with self._store_lock():
            self._write_state_unlocked(state)

    def _write_state_unlocked(self, state: Mapping[str, QuotaStateRecord]) -> None:
        """Write state while the caller already holds the store lock."""

        payload = {
            alias: record.model_dump(mode="json", exclude_none=True)
            for alias, record in sorted(state.items(), key=lambda item: item[0])
        }
        self._atomic_write_json(self.state_path, payload)

    def update_state_record(
        self,
        alias: str,
        updater: Callable[[QuotaStateRecord], QuotaStateRecord],
    ) -> QuotaStateRecord:
        """Load, update, atomically persist, and return one state record."""

        updated_record: QuotaStateRecord | None = None

        def _update(state: dict[str, QuotaStateRecord]) -> None:
            nonlocal updated_record
            updated_record = updater(state.get(alias, QuotaStateRecord()))
            state[alias] = updated_record

        self.update_state(_update)
        if updated_record is None:  # pragma: no cover - updater contract guard
            raise RuntimeError("state updater did not produce a record")
        return updated_record

    def update_state(self, updater: Callable[[dict[str, QuotaStateRecord]], None]) -> dict[str, QuotaStateRecord]:
        """Load, mutate under the single-process lock, write, and return state."""

        with self._store_lock():
            state = self.load_state()
            updater(state)
            self._write_state_unlocked(state)
            return state

    def append_event(self, event: QuotaEventRecord) -> None:
        """Append one compact parse-valid JSON object to quota_events.jsonl."""

        with self._store_lock():
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            payload = event.model_dump(mode="json", exclude_none=True)
            line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            json.loads(line)
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

    def load_events(self) -> tuple[QuotaEventRecord, ...]:
        """Load appended quota events; missing file means empty."""

        try:
            lines = self.events_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return ()
        except OSError:
            raise MalformedAccountQuotaState(self.events_path.name, "events") from None
        events: list[QuotaEventRecord] = []
        try:
            for line in lines:
                if not line.strip():
                    continue
                events.append(QuotaEventRecord.model_validate(json.loads(line)))
        except Exception:
            raise MalformedAccountQuotaState(self.events_path.name, "events") from None
        return tuple(events)

    def public_profile_summaries(self) -> tuple[PublicProfileSummary, ...]:
        """Return sanitized summaries derived from private registry/state."""

        registry = self.load_registry()
        state = self.load_state()
        return tuple(public_summary_from(account, state.get(account.alias)) for account in registry)

    def _read_json_or_none(self, path: Path, kind: str) -> Any | None:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            raise MalformedAccountQuotaState(path.name, kind) from None
        try:
            return json.loads(text)
        except Exception:
            raise MalformedAccountQuotaState(path.name, kind) from None

    def _atomic_write_json(self, path: Path, payload: object) -> None:
        try:
            text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MalformedAccountQuotaState(path.name, "state") from exc

        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(text + "\n", encoding="utf-8")
        os.replace(temp_path, path)


__all__ = [
    "ACCOUNTS_FILENAME",
    "EVENTS_FILENAME",
    "STATE_FILENAME",
    "AccountQuotaStore",
    "AccountQuotaStoreError",
    "MalformedAccountQuotaState",
]
