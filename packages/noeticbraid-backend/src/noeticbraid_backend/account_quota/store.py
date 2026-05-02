# SPDX-License-Identifier: Apache-2.0
"""Private JSON/JSONL persistence for local account quota state."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from noeticbraid_backend.account_quota.models import (
    AccountRegistryRecord,
    PublicProfileSummary,
    QuotaEventRecord,
    QuotaStateRecord,
    public_summary_from,
)
from noeticbraid_backend.settings import Settings

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
    """Local store rooted under Settings.state_dir / account_quota."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @classmethod
    def from_settings(cls, settings: Settings) -> "AccountQuotaStore":
        """Create a store from backend settings without reading private files."""

        return cls(settings.account_quota_dir)

    @property
    def accounts_path(self) -> Path:
        return self.root / ACCOUNTS_FILENAME

    @property
    def state_path(self) -> Path:
        return self.root / STATE_FILENAME

    @property
    def events_path(self) -> Path:
        return self.root / EVENTS_FILENAME

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

        state = self.load_state()
        updated = updater(state.get(alias, QuotaStateRecord()))
        state[alias] = updated
        self.write_state(state)
        return updated

    def append_event(self, event: QuotaEventRecord) -> None:
        """Append one compact parse-valid JSON object to quota_events.jsonl."""

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
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_name = handle.name
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temp_path = Path(temp_name)
            json.loads(temp_path.read_text(encoding="utf-8"))
            os.replace(temp_path, path)
            temp_name = None
        except Exception:
            raise MalformedAccountQuotaState(path.name, "state") from None
        finally:
            if temp_name is not None:
                try:
                    Path(temp_name).unlink()
                except OSError:
                    pass


__all__ = [
    "ACCOUNTS_FILENAME",
    "EVENTS_FILENAME",
    "STATE_FILENAME",
    "AccountQuotaStore",
    "AccountQuotaStoreError",
    "MalformedAccountQuotaState",
]
