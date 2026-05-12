from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from noeticbraid_core.user_growth_llmwiki import progress_detector

WINDOW_START = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _patch(monkeypatch, *, mtime: bool, done: bool, response: bool) -> None:
    monkeypatch.setattr(progress_detector, "mtime_unchanged", lambda project_ref, window_start, vault_path: mtime)
    monkeypatch.setattr(progress_detector, "no_new_done", lambda project_ref, window_start, vault_path: done)
    monkeypatch.setattr(progress_detector, "no_new_response", lambda project_ref, window_start: response)


def test_progress_detector_combinator(monkeypatch, tmp_path: Path) -> None:
    _patch(monkeypatch, mtime=True, done=False, response=True)

    checks = progress_detector.progress_checks("Project Alpha", WINDOW_START, tmp_path)

    assert checks.to_record() == {
        "mtime_unchanged": True,
        "no_new_done": False,
        "no_new_response": True,
    }
    assert checks.is_stagnant is False


def test_all_three_true_triggers(monkeypatch, tmp_path: Path) -> None:
    _patch(monkeypatch, mtime=True, done=True, response=True)

    assert progress_detector.is_stagnant("Project Alpha", WINDOW_START, tmp_path) is True


def test_only_mtime_unchanged_not_trigger(monkeypatch, tmp_path: Path) -> None:
    _patch(monkeypatch, mtime=True, done=False, response=False)

    assert progress_detector.is_stagnant("Project Alpha", WINDOW_START, tmp_path) is False


def test_only_done_missing_not_trigger(monkeypatch, tmp_path: Path) -> None:
    _patch(monkeypatch, mtime=False, done=True, response=False)

    assert progress_detector.is_stagnant("Project Alpha", WINDOW_START, tmp_path) is False


def test_only_no_response_not_trigger(monkeypatch, tmp_path: Path) -> None:
    _patch(monkeypatch, mtime=False, done=False, response=True)

    assert progress_detector.is_stagnant("Project Alpha", WINDOW_START, tmp_path) is False


def test_any_false_progress_signal_blocks_detector_candidate(monkeypatch, tmp_path: Path) -> None:
    for mtime, done, response in [(False, True, True), (True, False, True), (True, True, False)]:
        _patch(monkeypatch, mtime=mtime, done=done, response=response)
        assert progress_detector.is_stagnant("Project Alpha", WINDOW_START, tmp_path) is False
