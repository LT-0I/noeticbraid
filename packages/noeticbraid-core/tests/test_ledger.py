"""RunLedger pytest (Stage 2 GPT-B)."""

from __future__ import annotations

import multiprocessing
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
