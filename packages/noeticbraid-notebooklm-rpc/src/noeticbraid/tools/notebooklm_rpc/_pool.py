from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
import notebooklm

from ._config_schema import validate_pool_config, validate_pool_state
from ._errors import NotebookLMAccountUnavailableError, NotebookLMPoolStateError
from ._runlog import emit_runlog_event


def _default_config_path() -> Path:
    return Path.home() / ".noeticbraid" / "notebooklm" / "pool.json"


def _default_state_path() -> Path:
    return Path.home() / ".noeticbraid" / "notebooklm" / "pool-state.json"


_DEFAULT_COOL_DOWN_SECONDS = {
    "rate_limited": 3600,
    "login_required": 43200,
    "captcha": 86400,
    "server_error_streak": 1800,
}
_ERROR_TTL = timedelta(days=7)


@dataclass(frozen=True)
class AccountSpec:
    account_id: str
    storage_state_path: Path
    daily_quota: int = 100
    quota_reset_tz: str = "UTC"
    label: Optional[str] = None


@dataclass
class AccountRuntimeState:
    account_id: str
    used_today: int = 0
    quota_reset_at: Optional[datetime] = None
    last_429_at: Optional[datetime] = None
    last_captcha_at: Optional[datetime] = None
    last_login_required_at: Optional[datetime] = None
    cool_down_until: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    consecutive_failures: int = 0


# Sole source of truth for ineligibility reason strings.
INELIGIBILITY_REASONS: frozenset[str] = frozenset(
    {
        "all_rate_limited",
        "all_login_required",
        "all_captcha",
        "all_server_error_streak",
        "all_quota_exhausted",
        "all_excluded",
        "mixed",
        "pool_empty",
    }
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NotebookLMPoolStateError(f"invalid datetime in pool state: {value!r}") from exc
    return _as_utc(parsed)


def _iso_dt(value: datetime | None) -> str | None:
    return None if value is None else _as_utc(value).isoformat()


def _next_midnight(now: datetime, tz_str: str) -> datetime:
    """Next 00:00:00 local time in tz_str, returned as tz-aware UTC.
    Raises NotebookLMPoolStateError if tz_str is invalid (ZoneInfo).
    DST handling: standard ZoneInfo semantics; on DST spring-forward 02:30,
    next-midnight is correctly the *following* local-day's 00:00.
    """

    try:
        zone = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError as exc:
        raise NotebookLMPoolStateError(f"invalid quota_reset_tz: {tz_str}") from exc
    local_now = _as_utc(now).astimezone(zone)
    local_midnight = datetime.combine(local_now.date() + timedelta(days=1), time(0), tzinfo=zone)
    return local_midnight.astimezone(timezone.utc)


class NotebookLMAccountPool:
    """Multi-account NotebookLM pool with quota tracking + health degradation.

    Concurrency: pool is thread-safe via internal threading.Lock. For async
    callers, lock is released before any I/O (pure CPU under lock). Single-process
    only; multi-process locking is OUT OF SCOPE (D5-04).

    Time: all timestamps are tz-aware UTC. `now()` is injected via `_now_fn`
    parameter for test determinism; defaults to `lambda: datetime.now(timezone.utc)`.
    """

    def __init__(
        self,
        *,
        accounts: tuple[AccountSpec, ...],
        state_path: Path,
        cool_down_seconds: dict[str, int],
        selection_policy: str = "least_recent_success",
        _now_fn=None,
    ):
        if selection_policy != "least_recent_success":
            raise NotebookLMPoolStateError(f"unsupported selection_policy: {selection_policy}")
        self._accounts = tuple(accounts)
        self._state_path = Path(state_path).expanduser()
        self._cool_down_seconds = {**_DEFAULT_COOL_DOWN_SECONDS, **cool_down_seconds}
        self._selection_policy = selection_policy
        self._now_fn = _now_fn or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._config_path: Path | None = None
        self._state: dict[str, AccountRuntimeState] = {
            spec.account_id: AccountRuntimeState(account_id=spec.account_id) for spec in self._accounts
        }

    @classmethod
    def from_config(
        cls,
        config_path: Optional[Path] = None,
        *,
        state_path: Optional[Path] = None,
    ) -> "NotebookLMAccountPool":
        """Load + validate pool.json (path: explicit > NOETICBRAID_NOTEBOOKLM_POOL_CONFIG env > default).
        Same for state.json. If state.json missing, initialize zero-state and persist.
        """

        cfg_path = Path(
            config_path
            or os.environ.get("NOETICBRAID_NOTEBOOKLM_POOL_CONFIG")
            or _default_config_path()
        ).expanduser()
        st_path = Path(
            state_path
            or os.environ.get("NOETICBRAID_NOTEBOOKLM_POOL_STATE")
            or _default_state_path()
        ).expanduser()
        try:
            with cfg_path.open("r", encoding="utf-8") as handle:
                config_doc = json.load(handle)
            validate_pool_config(config_doc)
        except NotebookLMPoolStateError:
            raise
        except Exception as exc:
            raise NotebookLMPoolStateError(f"failed to load pool config {cfg_path}: {exc}") from exc

        accounts = tuple(
            AccountSpec(
                account_id=entry["account_id"],
                storage_state_path=Path(entry["storage_state_path"]).expanduser(),
                daily_quota=entry.get("daily_quota", 100),
                quota_reset_tz=entry.get("quota_reset_tz", "UTC"),
                label=entry.get("label"),
            )
            for entry in config_doc["accounts"]
        )
        pool = cls(
            accounts=accounts,
            state_path=st_path,
            cool_down_seconds=config_doc.get("cool_down_seconds", {}),
            selection_policy=config_doc.get("selection_policy", "least_recent_success"),
        )
        pool._config_path = cfg_path

        if st_path.exists():
            try:
                with st_path.open("r", encoding="utf-8") as handle:
                    state_doc = json.load(handle)
                validate_pool_state(state_doc)
                pool._state = pool._state_from_doc(state_doc)
            except NotebookLMPoolStateError:
                raise
            except Exception as exc:
                raise NotebookLMPoolStateError(f"failed to load pool state {st_path}: {exc}") from exc
        else:
            with pool._lock:
                pool._persist_state_atomic()
        return pool

    def pick(self, *, exclude: frozenset[str] = frozenset()) -> AccountSpec:
        """See §Selection algorithm. Raises NotebookLMAccountUnavailableError if none eligible."""

        with self._lock:
            now = _as_utc(self._now_fn())
            state_dirty = False

            for spec in self._accounts:
                rs = self._state[spec.account_id]
                if rs.quota_reset_at is None:
                    rs.quota_reset_at = _next_midnight(now, spec.quota_reset_tz)
                    state_dirty = True
                elif now >= rs.quota_reset_at:
                    rs.used_today = 0
                    rs.quota_reset_at = _next_midnight(now, spec.quota_reset_tz)
                    state_dirty = True

            for spec in self._accounts:
                rs = self._state[spec.account_id]
                if rs.cool_down_until is not None and now >= rs.cool_down_until:
                    rs.cool_down_until = None
                    state_dirty = True

            eligible = [
                spec
                for spec in self._accounts
                if spec.account_id not in exclude
                and self._state[spec.account_id].cool_down_until is None
                and self._state[spec.account_id].used_today < spec.daily_quota
            ]

            if not eligible:
                reason = self._compute_ineligibility_reason(exclude, now=now)
                if state_dirty:
                    self._persist_state_atomic()
                tried = tuple(spec.account_id for spec in self._accounts if spec.account_id not in exclude)
                raise NotebookLMAccountUnavailableError(tried=tried, reason=reason)

            sentinel_past = datetime.min.replace(tzinfo=timezone.utc)
            eligible.sort(
                key=lambda spec: (
                    self._state[spec.account_id].last_success_at or sentinel_past,
                    spec.account_id,
                )
            )
            picked = eligible[0]
            if state_dirty:
                self._persist_state_atomic()
            emit_runlog_event(
                "pool.pick",
                {"account_id": picked.account_id, "label": picked.label},
                account_id=picked.account_id,
            )
            return picked

    def mark_success(self, account_id: str) -> None:
        """state.used_today += 1; state.last_success_at = now; state.consecutive_failures = 0;
        clear cool_down_until and (last_429_at, last_captcha_at, last_login_required_at) IFF
        they are older than 7 days. Persist state.json atomically.
        NORMATIVE: emit_runlog_event("pool.mark_success",
            {"account_id": account_id, "used_today": new_value},
            account_id=account_id).
        """

        with self._lock:
            rs = self._require_state(account_id)
            now = _as_utc(self._now_fn())
            rs.used_today += 1
            rs.last_success_at = now
            rs.consecutive_failures = 0
            if rs.cool_down_until is not None and now - rs.cool_down_until > _ERROR_TTL:
                rs.cool_down_until = None
            if rs.last_429_at is not None and now - rs.last_429_at > _ERROR_TTL:
                rs.last_429_at = None
            if rs.last_captcha_at is not None and now - rs.last_captcha_at > _ERROR_TTL:
                rs.last_captcha_at = None
            if rs.last_login_required_at is not None and now - rs.last_login_required_at > _ERROR_TTL:
                rs.last_login_required_at = None
            self._persist_state_atomic()
            used_today = rs.used_today
        emit_runlog_event(
            "pool.mark_success",
            {"account_id": account_id, "used_today": used_today},
            account_id=account_id,
        )

    def mark_failure(self, account_id: str, error: BaseException) -> bool:
        """Apply mapping table from §File 4. Persist state.json atomically.

        Returns `cool_down_applied: bool` — True iff this call SET `cool_down_until`
        on the account (was None → now in the future). This return value is the
        AUTHORITATIVE signal for rotation decisions in `run_with_pool` and replaces
        any pre/post `_cool_down_status` snapshot (which has stale-read race under
        concurrency). Computed inside the same lock as state mutation.

        NORMATIVE: emit_runlog_event("pool.mark_failure",
            {"account_id": account_id, "error_class": type(error).__name__,
             "cool_down_applied": <returned bool>, "consecutive_failures": new_value},
            account_id=account_id).
        For NotebookNotFoundError / SourceNotFoundError (no-op cases), still emit
        pool.mark_failure with cool_down_applied=False so observability is consistent.
        """

        with self._lock:
            rs = self._require_state(account_id)
            now = _as_utc(self._now_fn())
            before_cool_down = rs.cool_down_until
            should_persist = True

            if isinstance(error, (notebooklm.NotebookNotFoundError, notebooklm.SourceNotFoundError)):
                cool_down_applied = False
                should_persist = False
            elif isinstance(error, notebooklm.AuthError):
                rs.last_login_required_at = now
                rs.cool_down_until = now + timedelta(seconds=self._cool_down_seconds["login_required"])
                cool_down_applied = before_cool_down is None and rs.cool_down_until > now
            elif isinstance(error, notebooklm.RateLimitError) or self._is_http_429(error):
                rs.last_429_at = now
                rs.cool_down_until = now + timedelta(seconds=self._cool_down_seconds["rate_limited"])
                cool_down_applied = before_cool_down is None and rs.cool_down_until > now
            elif isinstance(error, notebooklm.ServerError):
                rs.consecutive_failures += 1
                if rs.consecutive_failures >= 3:
                    rs.cool_down_until = now + timedelta(seconds=self._cool_down_seconds["server_error_streak"])
                cool_down_applied = before_cool_down is None and rs.cool_down_until is not None and rs.cool_down_until > now
            elif "captcha" in str(error).lower():
                rs.last_captcha_at = now
                rs.cool_down_until = now + timedelta(seconds=self._cool_down_seconds["captcha"])
                cool_down_applied = before_cool_down is None and rs.cool_down_until > now
            elif isinstance(error, notebooklm.NotebookLMError):
                rs.consecutive_failures += 1
                cool_down_applied = False
            else:
                rs.consecutive_failures += 1
                cool_down_applied = False

            consecutive_failures = rs.consecutive_failures
            if should_persist:
                self._persist_state_atomic()
        emit_runlog_event(
            "pool.mark_failure",
            {
                "account_id": account_id,
                "error_class": type(error).__name__,
                "cool_down_applied": cool_down_applied,
                "consecutive_failures": consecutive_failures,
            },
            account_id=account_id,
        )
        return cool_down_applied

    def status(self) -> dict[str, Any]:
        """Snapshot:
        {
          "config_path": str,
          "state_path":  str,
          "accounts": [
            {"account_id": "...", "label": "...", "daily_quota": N,
             "used_today": N, "quota_reset_at": iso8601 | null,
             "cool_down_until": iso8601 | null, "last_success_at": iso8601 | null,
             "is_eligible_now": bool, "ineligibility_reason": str | null},
            ...
          ]
        }
        """

        with self._lock:
            now = _as_utc(self._now_fn())
            accounts = []
            for spec in self._accounts:
                rs = self._state[spec.account_id]
                reason = self._account_ineligibility_reason(spec, rs, now)
                accounts.append(
                    {
                        "account_id": spec.account_id,
                        "label": spec.label,
                        "daily_quota": spec.daily_quota,
                        "used_today": rs.used_today,
                        "quota_reset_at": _iso_dt(rs.quota_reset_at),
                        "cool_down_until": _iso_dt(rs.cool_down_until),
                        "last_success_at": _iso_dt(rs.last_success_at),
                        "is_eligible_now": reason is None,
                        "ineligibility_reason": reason,
                    }
                )
            return {
                "config_path": str(self._config_path) if self._config_path is not None else "",
                "state_path": str(self._state_path),
                "accounts": accounts,
            }

    @property
    def account_count(self) -> int:
        """Number of accounts in config (read at object construction; immutable
        for the lifetime of this pool instance). Used by run_with_pool to
        compute default max_rotations.
        """

        return len(self._accounts)

    def _require_state(self, account_id: str) -> AccountRuntimeState:
        try:
            return self._state[account_id]
        except KeyError as exc:
            raise NotebookLMPoolStateError(f"unknown account_id: {account_id}") from exc

    def _state_from_doc(self, doc: dict[str, Any]) -> dict[str, AccountRuntimeState]:
        parsed: dict[str, AccountRuntimeState] = {
            spec.account_id: AccountRuntimeState(account_id=spec.account_id) for spec in self._accounts
        }
        for account_id, raw in doc["accounts"].items():
            parsed[account_id] = AccountRuntimeState(
                account_id=account_id,
                used_today=raw.get("used_today", 0),
                quota_reset_at=_parse_dt(raw.get("quota_reset_at")),
                last_429_at=_parse_dt(raw.get("last_429_at")),
                last_captcha_at=_parse_dt(raw.get("last_captcha_at")),
                last_login_required_at=_parse_dt(raw.get("last_login_required_at")),
                cool_down_until=_parse_dt(raw.get("cool_down_until")),
                last_success_at=_parse_dt(raw.get("last_success_at")),
                consecutive_failures=raw.get("consecutive_failures", 0),
            )
        return parsed

    def _state_doc(self) -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": _as_utc(self._now_fn()).isoformat(),
            "accounts": {
                account_id: {
                    "used_today": rs.used_today,
                    "quota_reset_at": _iso_dt(rs.quota_reset_at),
                    "last_429_at": _iso_dt(rs.last_429_at),
                    "last_captcha_at": _iso_dt(rs.last_captcha_at),
                    "last_login_required_at": _iso_dt(rs.last_login_required_at),
                    "cool_down_until": _iso_dt(rs.cool_down_until),
                    "last_success_at": _iso_dt(rs.last_success_at),
                    "consecutive_failures": rs.consecutive_failures,
                }
                for account_id, rs in self._state.items()
            },
        }

    def _persist_state_atomic(self) -> None:
        """1. Build JSON dict from current state.
           2. Validate against POOL_STATE_SCHEMA.
           3. Write to {state_path}.tmp.{pid}.{thread_id} in same directory.
           4. os.fsync() the tmp file fd before close.
           5. os.replace(tmp, state_path) — POSIX-atomic rename.
           6. On any exception: clean up tmp; raise NotebookLMPoolStateError.
           Caller already holds self._lock.
        """

        tmp_path: Path | None = None
        try:
            doc = self._state_doc()
            validate_pool_state(doc)
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._state_path.with_name(
                f"{self._state_path.name}.tmp.{os.getpid()}.{threading.get_ident()}"
            )
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(doc, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self._state_path)
        except NotebookLMPoolStateError:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
        except Exception as exc:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise NotebookLMPoolStateError(f"failed to persist pool state {self._state_path}: {exc}") from exc

    def _compute_ineligibility_reason(
        self,
        exclude: frozenset[str],
        *,
        now: datetime | None = None,
    ) -> str:
        now = _as_utc(now or self._now_fn())
        candidates = [account for account in self._accounts if account.account_id not in exclude]
        if not candidates:
            return "all_excluded"

        causes: set[str] = set()
        for spec in candidates:
            rs = self._state[spec.account_id]
            if rs.used_today >= spec.daily_quota:
                causes.add("quota")
            elif rs.cool_down_until is not None:
                if (
                    rs.last_429_at
                    and (now - rs.last_429_at).total_seconds() < self._cool_down_seconds["rate_limited"]
                ):
                    causes.add("rate_limit")
                elif (
                    rs.last_login_required_at
                    and (now - rs.last_login_required_at).total_seconds()
                    < self._cool_down_seconds["login_required"]
                ):
                    causes.add("login_required")
                elif (
                    rs.last_captcha_at
                    and (now - rs.last_captcha_at).total_seconds() < self._cool_down_seconds["captcha"]
                ):
                    causes.add("captcha")
                else:
                    causes.add("server_error_streak")

        if len(causes) == 0:
            return "pool_empty"
        if len(causes) == 1:
            cause = causes.pop()
            return {
                "quota": "all_quota_exhausted",
                "rate_limit": "all_rate_limited",
                "login_required": "all_login_required",
                "captcha": "all_captcha",
                "server_error_streak": "all_server_error_streak",
            }[cause]
        return "mixed"

    def _account_ineligibility_reason(
        self,
        spec: AccountSpec,
        rs: AccountRuntimeState,
        now: datetime,
    ) -> str | None:
        if rs.used_today >= spec.daily_quota:
            return "all_quota_exhausted"
        if rs.cool_down_until is not None and now < rs.cool_down_until:
            return self._cooldown_reason(rs, now)
        return None

    def _cooldown_reason(self, rs: AccountRuntimeState, now: datetime) -> str:
        if rs.last_429_at and (now - rs.last_429_at).total_seconds() < self._cool_down_seconds["rate_limited"]:
            return "all_rate_limited"
        if (
            rs.last_login_required_at
            and (now - rs.last_login_required_at).total_seconds() < self._cool_down_seconds["login_required"]
        ):
            return "all_login_required"
        if rs.last_captcha_at and (now - rs.last_captcha_at).total_seconds() < self._cool_down_seconds["captcha"]:
            return "all_captcha"
        return "all_server_error_streak"

    @staticmethod
    def _is_http_429(error: BaseException) -> bool:
        if not isinstance(error, httpx.HTTPStatusError):
            return False
        response = getattr(error, "response", None)
        return getattr(response, "status_code", None) == 429
