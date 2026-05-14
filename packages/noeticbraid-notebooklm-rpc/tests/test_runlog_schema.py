from __future__ import annotations

import json

import pytest

from noeticbraid.tools.notebooklm_rpc import PoolEventNDJSONSchema, emit_runlog_event


def test_emit_writes_valid_ndjson_line(tmp_path, fixed_now):
    path = tmp_path / "runlog.ndjson"

    emit_runlog_event("pool.pick", {"account_id": "acct-a"}, account_id="acct-a", runlog_path=path, _now_fn=lambda: fixed_now)
    event = json.loads(path.read_text(encoding="utf-8"))

    assert set(event) == set(PoolEventNDJSONSchema["required_fields"])
    assert event["kind"] == "pool.pick"
    assert event["account_id"] == "acct-a"
    assert event["payload"] == {"account_id": "acct-a"}


def test_invalid_kind_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        emit_runlog_event("pool.not-real", {}, runlog_path=tmp_path / "runlog.ndjson")


def test_io_error_swallowed_to_stderr(tmp_path, capsys):
    emit_runlog_event("pool.pick", {}, runlog_path=tmp_path)

    captured = capsys.readouterr()
    assert "warning: failed to write NotebookLM pool runlog" in captured.err
