from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from noeticbraid.tools.notebooklm_rpc import AccountSpec, NotebookLMAccountPool

FIXED_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


class MutableClock:
    def __init__(self, now: datetime = FIXED_NOW):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class FakeNotebooksAPI:
    def __init__(self, owner: "FakeNotebookLMClient") -> None:
        self.owner = owner

    async def list(self) -> list[str]:
        return [f"notebook:{self.owner.path}"]


class FakeNotebookLMClient:
    def __init__(
        self,
        *,
        path: Path | str,
        timeout: float = 30.0,
        aenter_error: BaseException | None = None,
        aexit_error: BaseException | None = None,
    ) -> None:
        self.path = path
        self.timeout = timeout
        self.aenter_error = aenter_error
        self.aexit_error = aexit_error
        self.entered = 0
        self.exited = 0
        self.exit_args: tuple[Any, Any, Any] | None = None
        self.notebooks = FakeNotebooksAPI(self)

    async def __aenter__(self) -> "FakeNotebookLMClient":
        self.entered += 1
        if self.aenter_error is not None:
            raise self.aenter_error
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.exited += 1
        self.exit_args = (exc_type, exc, tb)
        if self.aexit_error is not None:
            raise self.aexit_error
        return False


@dataclass
class FromStorageController:
    monkeypatch: pytest.MonkeyPatch
    outcomes: list[Any]

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.clients: list[FakeNotebookLMClient] = []

    def install(self) -> "FromStorageController":
        import notebooklm

        async def fake_from_storage(*, path=None, timeout=30.0, **kwargs):
            self.calls.append({"path": path, "timeout": timeout, "kwargs": kwargs})
            if self.outcomes:
                outcome = self.outcomes.pop(0)
            else:
                outcome = FakeNotebookLMClient(path=path, timeout=timeout)
            if isinstance(outcome, BaseException):
                raise outcome
            if callable(outcome):
                outcome = outcome(path=path, timeout=timeout)
            self.clients.append(outcome)
            return outcome

        self.monkeypatch.setattr(notebooklm.NotebookLMClient, "from_storage", fake_from_storage)
        return self


@pytest.fixture
def fixed_now() -> datetime:
    return FIXED_NOW


@pytest.fixture
def fake_clock(fixed_now: datetime) -> MutableClock:
    return MutableClock(fixed_now)


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_runlog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "runlog.ndjson"
    monkeypatch.setenv("NOETICBRAID_NOTEBOOKLM_RUNLOG_PATH", str(path))
    return path


@pytest.fixture
def patch_from_storage(monkeypatch: pytest.MonkeyPatch):
    def factory(*outcomes: Any) -> FromStorageController:
        return FromStorageController(monkeypatch, list(outcomes)).install()

    return factory


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_fixture(fixtures_dir: Path, name: str) -> Any:
    return read_json(fixtures_dir / name)


def copy_fixture(fixtures_dir: Path, tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    target.write_text((fixtures_dir / name).read_text(encoding="utf-8"), encoding="utf-8")
    return target


def pool_from_config_doc(
    config_doc: dict[str, Any],
    tmp_path: Path,
    fake_clock: MutableClock,
    *,
    state_doc: dict[str, Any] | None = None,
) -> NotebookLMAccountPool:
    accounts = tuple(
        AccountSpec(
            account_id=entry["account_id"],
            storage_state_path=Path(entry["storage_state_path"]),
            daily_quota=entry.get("daily_quota", 100),
            quota_reset_tz=entry.get("quota_reset_tz", "UTC"),
            label=entry.get("label"),
        )
        for entry in config_doc["accounts"]
    )
    pool = NotebookLMAccountPool(
        accounts=accounts,
        state_path=tmp_path / "pool-state.json",
        cool_down_seconds=config_doc.get("cool_down_seconds", {}),
        selection_policy=config_doc.get("selection_policy", "least_recent_success"),
        _now_fn=fake_clock,
    )
    if state_doc is not None:
        pool._state = pool._state_from_doc(state_doc)  # test helper for spec fixtures
        with pool._lock:
            pool._persist_state_atomic()
    return pool


def read_runlog(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
