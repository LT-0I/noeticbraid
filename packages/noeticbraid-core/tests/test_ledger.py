"""RunLedger pytest (Stage 2 GPT-B, tightened for Phase 1.2 Stage 2.1)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from filelock import ReadWriteLock
import pytest

import noeticbraid_core.ledger.run_ledger as run_ledger_module
from noeticbraid_core.ledger import RunLedger
from noeticbraid_core.schemas import RunRecord


def make_record(
    run_id: str = "run_001",
    task_id: str = "task_001",
    event_type: str = "task_created",
    created_at: datetime | None = None,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        task_id=task_id,
        event_type=event_type,
        created_at=created_at or datetime.now(timezone.utc),
        actor="system",
        status="recorded",
    )


class TestRunLedgerAppendRoundTrip:
    def test_append_and_iter_all_roundtrip(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        rec = make_record()

        ledger.append(rec)

        records = list(ledger.iter_all())
        assert len(records) == 1
        assert records[0].run_id == "run_001"
        assert records[0].task_id == "task_001"

    def test_path_under_state_ledger(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        assert ledger.path == tmp_path / "state" / "ledger" / "run_ledger.jsonl"


def _worker_append(args: tuple[str, str]) -> None:
    """Spawned in subprocess: append 100 records under a unique prefix."""

    root_str, prefix = args
    ledger = RunLedger(root=Path(root_str))
    for i in range(100):
        ledger.append(
            make_record(
                run_id=f"run_{prefix}_{i:03d}",
                task_id=f"task_{prefix}_{i:03d}",
            )
        )


APPEND_WORKER_CODE = """
from datetime import datetime, timezone
from pathlib import Path
import sys

from noeticbraid_core.ledger import RunLedger
from noeticbraid_core.schemas import RunRecord

root = Path(sys.argv[1])
prefix = sys.argv[2]
ledger = RunLedger(root=root)
for i in range(100):
    ledger.append(
        RunRecord(
            run_id=f"run_{prefix}_{i:03d}",
            task_id=f"task_{prefix}_{i:03d}",
            event_type="task_created",
            created_at=datetime.now(timezone.utc),
            actor="system",
            status="recorded",
        )
    )
"""


READER_WORKER_CODE = """
import json
from pathlib import Path
import sys

from noeticbraid_core.ledger import RunLedger

root = Path(sys.argv[1])
started_path = Path(sys.argv[2])
result_path = Path(sys.argv[3])

started_path.write_text("started", encoding="utf-8")
try:
    ledger = RunLedger(root=root)
    payload = ["ok", [record.run_id for record in ledger.iter_all()]]
except Exception as exc:
    payload = ["error", repr(exc)]
result_path.write_text(json.dumps(payload), encoding="utf-8")
"""


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else os.pathsep.join([src_path, existing])
    return env


def _wait_for_path(path: Path, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.05)
    return path.exists()


class TestRunLedgerConcurrency:
    def test_4_processes_400_records_no_corruption(self, tmp_path: Path) -> None:
        prefixes = ["a", "b", "c", "d"]
        processes = [
            subprocess.Popen(
                [sys.executable, "-c", APPEND_WORKER_CODE, str(tmp_path), prefix],
                env=_subprocess_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for prefix in prefixes
        ]
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, f"stdout={stdout!r} stderr={stderr!r}"

        ledger = RunLedger(root=tmp_path)
        records = list(ledger.iter_all())
        assert len(records) == 400
        assert len({record.run_id for record in records}) == 400

    def test_reader_shared_lock_does_not_expose_partial_jsonl_line(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        ledger.append(make_record(run_id="run_before_lock", task_id="task_before_lock"))
        locked_record_json = make_record(
            run_id="run_after_lock",
            task_id="task_after_lock",
        ).model_dump_json()
        split_at = len(locked_record_json) // 2

        started_path = tmp_path / "reader.started"
        result_path = tmp_path / "reader.result.json"
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                READER_WORKER_CODE,
                str(tmp_path),
                str(started_path),
                str(result_path),
            ],
            env=_subprocess_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        early_result = None
        lock = ReadWriteLock(
            ledger.path.parent / run_ledger_module.LOCK_FILE_NAME,
            timeout=60,
        )
        with lock.write_lock():
            with open(ledger.path, "a", encoding="utf-8") as fh:
                fh.write(locked_record_json[:split_at])
                fh.flush()
                os.fsync(fh.fileno())

                assert _wait_for_path(started_path, timeout_seconds=5)
                early_result = result_path.read_text(encoding="utf-8") if result_path.exists() else None

                fh.write(locked_record_json[split_at:])
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())

        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - protects the test runner on lock regressions
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)

        assert early_result is None, f"reader returned before writer lock release: {early_result!r}"
        assert process.returncode == 0, f"stdout={stdout!r} stderr={stderr!r}"
        status, payload = json.loads(result_path.read_text(encoding="utf-8"))
        assert status == "ok"
        assert payload == ["run_before_lock", "run_after_lock"]


class TestRunLedgerCorruptedLine:
    def test_corrupted_line_skipped(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        ledger.append(make_record(run_id="run_good_001"))
        with open(ledger.path, "a", encoding="utf-8") as fh:
            fh.write("{this is not valid json\n")
        ledger.append(make_record(run_id="run_good_002"))

        records = list(ledger.iter_all())

        assert [record.run_id for record in records] == ["run_good_001", "run_good_002"]


class TestRunLedgerReplayDeterministic:
    def test_iter_all_repeatable(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        for i in range(10):
            ledger.append(make_record(run_id=f"run_{i:03d}"))

        first = [record.run_id for record in ledger.iter_all()]
        second = [record.run_id for record in ledger.iter_all()]

        assert first == second
        assert first == [f"run_{i:03d}" for i in range(10)]

    def test_multiple_appended_records_replay_in_write_order(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        expected = ["run_alpha", "run_bravo", "run_charlie"]
        for run_id in expected:
            ledger.append(make_record(run_id=run_id, task_id=f"task_{run_id[4:]}"))

        assert [record.run_id for record in ledger.iter_all()] == expected


class TestRunLedgerIterSince:
    def test_iter_since_filters_by_created_at(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        base = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            ledger.append(
                make_record(
                    run_id=f"run_{i:03d}",
                    created_at=base + timedelta(minutes=i),
                )
            )
        cutoff = base + timedelta(minutes=2)

        results = list(ledger.iter_since(cutoff))

        assert [record.run_id for record in results] == ["run_002", "run_003", "run_004"]

    def test_iter_since_naive_treated_as_utc(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        base = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        ledger.append(make_record(run_id="run_after", created_at=base))
        cutoff_naive = datetime(2026, 4, 28, 11, 59, 0)

        results = list(ledger.iter_since(cutoff_naive))

        assert [record.run_id for record in results] == ["run_after"]


class TestRunLedgerFindByRunId:
    def test_find_existing(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        ledger.append(make_record(run_id="run_alpha"))
        ledger.append(make_record(run_id="run_bravo"))

        result = ledger.find_by_run_id("run_bravo")

        assert result is not None
        assert result.run_id == "run_bravo"

    def test_find_missing(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        ledger.append(make_record(run_id="run_alpha"))
        assert ledger.find_by_run_id("run_zulu") is None

    def test_find_by_run_id_not_found_empty_ledger(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        assert ledger.find_by_run_id("run_never_written") is None


class TestRunLedgerEmpty:
    def test_iter_all_empty_missing_file(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        assert list(ledger.iter_all()) == []

    def test_iter_all_empty_zero_byte_file(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        ledger.path.touch()
        assert list(ledger.iter_all()) == []


class TestRunLedgerReaderHandleLifetime:
    def test_below_threshold_snapshot_releases_handle_before_yielding(self, tmp_path: Path) -> None:
        ledger = RunLedger(root=tmp_path)
        ledger.append(make_record(run_id="run_alpha"))
        ledger.append(make_record(run_id="run_bravo"))

        iterator = ledger.iter_all()
        first = next(iterator)
        renamed = ledger.path.with_name("run_ledger.renamed.jsonl")
        ledger.path.rename(renamed)
        renamed.unlink()

        assert first.run_id == "run_alpha"
        assert [record.run_id for record in iterator] == ["run_bravo"]
        assert not ledger.path.exists()
        assert not renamed.exists()

    def test_iter_all_docstring_documents_fifty_mib_streaming_threshold(self) -> None:
        doc = RunLedger.iter_all.__doc__ or ""
        assert "50 MiB" in doc
        assert "shared read lock" in doc
        assert "file handle remains open" in doc

    def test_at_or_above_threshold_stream_path_uses_filelock_read_lock(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        ledger = RunLedger(root=tmp_path)
        ledger.append(make_record(run_id="run_streamed"))
        lock_calls: list[Path] = []
        original_read_lock = run_ledger_module.ReadWriteLock.read_lock

        def recording_read_lock(self, *args, **kwargs):
            lock_calls.append(Path(self.lock_file))
            return original_read_lock(self, *args, **kwargs)

        monkeypatch.setattr(run_ledger_module, "SMALL_LEDGER_SNAPSHOT_MAX_BYTES", 1)
        monkeypatch.setattr(run_ledger_module.ReadWriteLock, "read_lock", recording_read_lock)

        records = list(ledger.iter_all())

        assert [record.run_id for record in records] == ["run_streamed"]
        assert ledger.path.parent / run_ledger_module.LOCK_FILE_NAME in lock_calls
