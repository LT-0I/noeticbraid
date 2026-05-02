"""RunLedger pytest (Stage 2 GPT-B, tightened for Phase 1.2 Stage 2.1)."""

from __future__ import annotations

import multiprocessing
import os
import queue
from datetime import datetime, timedelta, timezone
from pathlib import Path

import portalocker
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


def _reader_collect_run_ids(root_str: str, started_queue, result_queue) -> None:
    """Spawned in subprocess: collect ledger run IDs after signalling readiness."""

    started_queue.put("started")
    try:
        ledger = RunLedger(root=Path(root_str))
        result_queue.put(("ok", [record.run_id for record in ledger.iter_all()]))
    except Exception as exc:  # pragma: no cover - defensive child-process reporting
        result_queue.put(("error", repr(exc)))


class TestRunLedgerConcurrency:
    def test_4_processes_400_records_no_corruption(self, tmp_path: Path) -> None:
        prefixes = ["a", "b", "c", "d"]
        args = [(str(tmp_path), prefix) for prefix in prefixes]

        with multiprocessing.Pool(processes=4) as pool:
            pool.map(_worker_append, args)

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

        started_queue = multiprocessing.Queue()
        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_reader_collect_run_ids,
            args=(str(tmp_path), started_queue, result_queue),
        )

        early_result = None
        with open(ledger.path, "a", encoding="utf-8") as fh:
            portalocker.lock(fh, portalocker.LOCK_EX)
            try:
                fh.write(locked_record_json[:split_at])
                fh.flush()
                os.fsync(fh.fileno())

                process.start()
                assert started_queue.get(timeout=5) == "started"
                try:
                    early_result = result_queue.get(timeout=0.5)
                except queue.Empty:
                    early_result = None

                fh.write(locked_record_json[split_at:])
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                portalocker.unlock(fh)

        process.join(timeout=5)
        if process.is_alive():  # pragma: no cover - protects the test runner on lock regressions
            process.terminate()
            process.join(timeout=5)

        assert early_result is None, f"reader returned before writer lock release: {early_result!r}"
        assert not process.is_alive()
        status, payload = result_queue.get(timeout=1)
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
        assert "LOCK_SH" in doc
        assert "file handle remains open" in doc

    def test_at_or_above_threshold_stream_path_uses_shared_lock(self, tmp_path: Path, monkeypatch) -> None:
        ledger = RunLedger(root=tmp_path)
        ledger.append(make_record(run_id="run_streamed"))
        lock_calls: list[int] = []
        original_lock = run_ledger_module.portalocker.lock

        def recording_lock(fh, flags):
            lock_calls.append(flags)
            return original_lock(fh, flags)

        monkeypatch.setattr(run_ledger_module, "SMALL_LEDGER_SNAPSHOT_MAX_BYTES", 1)
        monkeypatch.setattr(run_ledger_module.portalocker, "lock", recording_lock)

        records = list(ledger.iter_all())

        assert [record.run_id for record in records] == ["run_streamed"]
        assert run_ledger_module.portalocker.LOCK_SH in lock_calls
