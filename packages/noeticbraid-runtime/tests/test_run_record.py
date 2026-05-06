from __future__ import annotations

import pytest

from noeticbraid_runtime.run_record import runtime_artifact_refs, runtime_event_payload


def test_runtime_artifact_refs_are_frozen_runrecord_compatible() -> None:
    refs = runtime_artifact_refs(tab_id="tab-1.2", cdp_port=9222, process_pid=12345)

    assert refs == ["artifact_c2_tab_tab_1_2", "artifact_c2_cdp_port_9222", "artifact_c2_process_pid_12345"]


def test_runtime_event_payload_uses_existing_runrecord_enum_and_artifact_refs_only() -> None:
    payload = runtime_event_payload(
        run_id="run_c2_smoke",
        task_id="task_c2_smoke",
        artifact_refs=["artifact_c2_tab_tab_1"],
    )

    assert payload["event_type"] == "artifact_created"
    assert payload["actor"] == "system"
    assert payload["artifact_refs"] == ["artifact_c2_tab_tab_1"]
    assert "tab_id" not in payload
    assert "process_pid" not in payload


def test_runtime_event_payload_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError, match="frozen RunRecord enum"):
        runtime_event_payload(
            run_id="run_x",
            task_id="task_x",
            artifact_refs=[],
            event_type="browser_launched",  # type: ignore[arg-type]
        )
