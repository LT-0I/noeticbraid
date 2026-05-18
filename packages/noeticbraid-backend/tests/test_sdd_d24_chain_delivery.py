# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D24 Web-AI chain delivery hardening tests (zero network)."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.capabilities import capability_for
from noeticbraid_backend.platform.orchestrate import critique as critique_mod
from noeticbraid_backend.platform.orchestrate import nodes as nodes_mod
from noeticbraid_backend.platform.orchestrate.critique import run_critique_loop
from noeticbraid_backend.platform.orchestrate.nodes import HubExecutionNode
from noeticbraid_backend.platform.orchestrate.web_modality_routes import resolve_web_modality
from noeticbraid_backend.platform import workspace_paths as workspace_paths_mod
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

ACCOUNT = "d24_user_01"
OTHER_ACCOUNT = "d24_user_02"


def _enable_hub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hub_root = tmp_path / "hub-root"
    hub_root.mkdir(exist_ok=True)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_HUB_EXEC", "1")
    monkeypatch.setenv(compat.HUB_PATH_ENV, str(hub_root))
    monkeypatch.setenv(compat.AUTOMATION_ENV, "1")
    monkeypatch.setattr(nodes_mod.compat, "digest_matches", lambda _path: ("ok", None))
    monkeypatch.setattr(critique_mod.compat, "digest_matches", lambda _path: ("ok", None))
    monkeypatch.setattr(nodes_mod, "check_chatgpt_consumer_health", lambda _path: {"ok": True})


def _verdict(*, issues: list[str], evidence: list[str]) -> dict[str, Any]:
    return {
        "reviewer_family": "web:claude",
        "issues": issues,
        "rationale": "checked by cross-model reviewer",
        "confidence": 0.8,
        "evidence_node_ids": evidence,
    }


def _set_node_times(monkeypatch: pytest.MonkeyPatch, *values: float) -> None:
    times = iter(values)
    last = values[-1]

    def fake_time() -> float:
        return next(times, last)

    monkeypatch.setattr(nodes_mod.time, "time", fake_time)


def _prepare_artifact_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, account: str, task_id: str) -> Path:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    art_dir = resolve_user_path(account, f"tasks/{task_id}/artifacts")
    art_dir.mkdir(parents=True, exist_ok=True)
    return art_dir


def _execute_blocked_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    task_id: str,
    on_dispatch: Any | None = None,
) -> Any:
    _enable_hub(monkeypatch, tmp_path)
    calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(params)))
        if on_dispatch is not None:
            on_dispatch()
        return {"outcome": "blocked", "reason": "artifact path governance violation"}

    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", dispatch)
    outcome = HubExecutionNode().execute(
        {"id": "fanout"},
        {
            "account": ACCOUNT,
            "task_id": task_id,
            "requirement": {"id": "req:image, bad", "text": "Generate a hero image", "modality": "image"},
        },
    )
    assert calls[0][0] == "webai_chatgpt_generate_image"
    return outcome


def test_d24_b_prefix_upload_without_files_is_rejected() -> None:
    assert compat.validate_request("webai_claude_upload_and_query", {"profile": "claude", "query": "x"}) == (
        None,
        "request rejected: invalid files",
    )


def test_d24_b_textual_reviewer_uses_send_prompt_and_conforming_verdict_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    model.initialize_task_files(ACCOUNT, "task_text_review")
    route = resolve_web_modality("text")
    assert route.kind == "route"
    assert route.reviewer_op == "webai_claude_send_prompt"
    assert route.reviewer_vendor == "claude"
    assert route.generator_vendor == "chatgpt"
    assert route.reviewer_vendor != route.generator_vendor

    params = critique_mod._web_reviewer_params(  # noqa: SLF001
        route,
        ACCOUNT,
        "task_text_review",
        {"id": "req_text", "text": "Draft", "modality": "text"},
        {"text": "draft", "hub": True, "conversation_id": "conv_text"},
        ["round_1:fanout_req_text"],
        1,
        None,
    )
    assert isinstance(params, dict)
    assert set(params) == {"profile", "prompt"}
    assert "files" not in params
    assert "query" not in params
    argv, err = compat.validate_request("webai_claude_send_prompt", params)
    assert err is None
    assert argv is not None

    calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(op: str, sent_params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(sent_params)))
        assert op == "webai_claude_send_prompt"
        assert set(sent_params) == {"profile", "prompt"}
        return {"outcome": "ok", "payload": {"response_text": json.dumps(_verdict(issues=[], evidence=[]))}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)
    result = run_critique_loop(
        ACCOUNT,
        "task_text_review",
        {"id": "req_text", "text": "Draft", "modality": "text"},
        {"text": "draft", "hub": True, "conversation_id": "conv_text"},
        "round_1:fanout_req_text",
        reviewer_families=("web:claude",),
    )

    assert result.status == "delivered"
    assert result.terminated_by == "consensus"
    assert calls[0][0] == "webai_claude_send_prompt"


def test_d24_b_nonconforming_claude_response_still_honest_deferred(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    model.initialize_task_files(ACCOUNT, "task_bad_verdict")

    def dispatch(_op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        bad = {"reviewer_family": "web:claude", "issues": ["missing proof"], "evidence_node_ids": [], "confidence": 0.8}
        return {"outcome": "ok", "payload": {"response_text": json.dumps(bad)}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)
    result = run_critique_loop(
        ACCOUNT,
        "task_bad_verdict",
        {"id": "req_text", "text": "Draft", "modality": "text"},
        {"text": "draft", "hub": True, "conversation_id": "conv_text"},
        "round_1:fanout_req_text",
        reviewer_families=("web:claude",),
    )

    assert result.status == "deferred"
    assert "evidence_node_ids" in str(result.reason)


def test_d24_a_image_governance_block_recovers_exactly_one_fresh_governed_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task_id = "task_image_recover"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)

    def create_fresh() -> None:
        src = art_dir / "ChatGPT Image May 18, 2026, 01_40_19 AM.png"
        src.write_bytes(b"png")
        os.utime(src, (1001.0, 1001.0))

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, create_fresh)

    assert outcome.status == "succeeded"
    assert outcome.artifact is not None
    ref = str(outcome.artifact["path"])
    assert outcome.artifact == {"path": ref, "text": ref, "hub": True}
    assert re.fullmatch(rf"tasks/{task_id}/artifacts/web_image_reqimagebad_\d+\.png", ref)
    assert "," not in ref and " " not in ref and ":" not in ref
    dst = resolve_user_path(ACCOUNT, ref)
    assert dst.read_bytes() == b"png"
    files, err = compat._validate_upload_files("webai_claude_upload_and_query", [str(dst)])  # noqa: SLF001
    assert err is None
    assert files == [str(dst)]


@pytest.mark.parametrize("case", ["none", "ambiguous", "stale", "foreign"])
def test_d24_a_image_recovery_negatives_honest_defer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
) -> None:
    task_id = f"task_image_{case}"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)
    if case == "ambiguous":
        for name in ("fresh1.png", "fresh2.png"):
            path = art_dir / name
            path.write_bytes(b"png")
            os.utime(path, (1001.0, 1001.0))
    elif case == "stale":
        path = art_dir / "stale.png"
        path.write_bytes(b"png")
        os.utime(path, (999.0, 999.0))
    elif case == "foreign":
        other_art_dir = resolve_user_path(OTHER_ACCOUNT, f"tasks/{task_id}/artifacts")
        other_art_dir.mkdir(parents=True, exist_ok=True)
        foreign = other_art_dir / "foreign.png"
        foreign.write_bytes(b"png")
        os.utime(foreign, (1001.0, 1001.0))
        other_task_dir = resolve_user_path(ACCOUNT, "tasks/other_task/artifacts")
        other_task_dir.mkdir(parents=True, exist_ok=True)
        other_task = other_task_dir / "other.png"
        other_task.write_bytes(b"png")
        os.utime(other_task, (1001.0, 1001.0))
    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_rejects_symlink_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task_id = "task_image_symlink"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)
    outside = resolve_user_path(ACCOUNT, "tasks/other_symlink_source/artifacts/foreign.png")
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_bytes(b"foreign")

    def create_symlink() -> None:
        os.symlink(outside, art_dir / "fresh_link.png")
        os.utime(art_dir / "fresh_link.png", (1001.0, 1001.0), follow_symlinks=False)

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, create_symlink)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_rejects_touched_stale_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task_id = "task_image_touched_stale"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)
    stale = art_dir / "stale.png"
    stale.write_bytes(b"stale")
    os.utime(stale, (999.0, 999.0))

    def touch_stale() -> None:
        os.utime(stale, (1001.0, 1001.0))

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, touch_stale)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_rejects_snapshot_miss(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task_id = "task_image_snapshot_miss"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)
    real_resolve_user_path = workspace_paths_mod.resolve_user_path
    calls = 0

    def flaky_resolve_user_path(account: str, rel: str | Path) -> Path:
        nonlocal calls
        if str(rel) == f"tasks/{task_id}/artifacts":
            calls += 1
            if calls == 1:
                raise RuntimeError("snapshot unavailable")
        return real_resolve_user_path(account, rel)

    def create_fresh() -> None:
        src = art_dir / "fresh.png"
        src.write_bytes(b"png")
        os.utime(src, (1001.0, 1001.0))

    monkeypatch.setattr(workspace_paths_mod, "resolve_user_path", flaky_resolve_user_path)
    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, create_fresh)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_rejects_two_new_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task_id = "task_image_two_new"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)

    def create_two_fresh() -> None:
        for name in ("fresh1.png", "fresh2.png"):
            path = art_dir / name
            path.write_bytes(b"png")
            os.utime(path, (1001.0, 1001.0))

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, create_two_fresh)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_rejects_symlinked_task_artifacts_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    task_id = "task_image_symlinked_dir"
    source_task = "task_image_symlinked_source"
    source_art_dir = resolve_user_path(ACCOUNT, f"tasks/{source_task}/artifacts")
    source_art_dir.mkdir(parents=True, exist_ok=True)
    task_dir = resolve_user_path(ACCOUNT, f"tasks/{task_id}")
    task_dir.mkdir(parents=True, exist_ok=True)
    os.symlink(source_art_dir, task_dir / "artifacts")

    def create_fresh_in_source() -> None:
        src = source_art_dir / "fresh.png"
        src.write_bytes(b"png")
        os.utime(src, (1001.0, 1001.0))

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, create_fresh_in_source)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_rejects_hardlink_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task_id = "task_image_hardlink_source"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)
    foreign_dir = resolve_user_path(ACCOUNT, "tasks/hardlink_foreign/artifacts")
    foreign_dir.mkdir(parents=True, exist_ok=True)
    foreign = foreign_dir / "foreign.png"
    foreign.write_bytes(b"foreign-stale")
    os.utime(foreign, (999.0, 999.0))

    def create_hardlink() -> None:
        os.link(foreign, art_dir / "fresh.png")
        os.utime(art_dir / "fresh.png", (1001.0, 1001.0))

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, create_hardlink)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_rejects_symlink_swap_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task_id = "task_image_symlink_swap"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)
    outside = resolve_user_path(ACCOUNT, "tasks/symlink_swap_outside/artifacts/foreign.png")
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_bytes(b"foreign")
    os.utime(outside, (1001.0, 1001.0))

    def create_symlink() -> None:
        os.symlink(outside, art_dir / "fresh.png")
        os.utime(art_dir / "fresh.png", (1001.0, 1001.0), follow_symlinks=False)

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, create_symlink)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_rejects_lexical_parent_symlink_suffix_preserving(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    task_id = "task_image_suffix_preserving_symlink"
    evil_art_dir = resolve_user_path(ACCOUNT, f"evil/tasks/{task_id}/artifacts")
    evil_art_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir = resolve_user_path(ACCOUNT, "tasks")
    tasks_dir.mkdir(parents=True, exist_ok=True)
    os.symlink(evil_art_dir.parent, tasks_dir / task_id)

    def create_fresh_in_alias_target() -> None:
        src = evil_art_dir / "fresh.png"
        src.write_bytes(b"png")
        os.utime(src, (1001.0, 1001.0))

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, create_fresh_in_alias_target)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_a_image_recovery_dotfile_snapshot_consistency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task_id = "task_image_dotfile_snapshot"
    art_dir = _prepare_artifact_dir(tmp_path, monkeypatch, ACCOUNT, task_id)
    dotfile = art_dir / ".png"
    dotfile.write_bytes(b"pre-existing-dotfile")
    os.utime(dotfile, (999.0, 999.0))

    def touch_dotfile() -> None:
        os.utime(dotfile, (1001.0, 1001.0))

    _set_node_times(monkeypatch, 1000.0, 1002.0)

    outcome = _execute_blocked_image(monkeypatch, tmp_path, task_id, touch_dotfile)

    assert outcome.status == "deferred"
    assert outcome.reason == "artifact path governance violation"
    assert outcome.evidence_node_ids == []
    assert outcome.artifact is None


def test_d24_b_image_reviewer_upload_branch_validates_and_completes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_hub(monkeypatch, tmp_path)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    task_id = "task_image_review"
    model.initialize_task_files(ACCOUNT, task_id)
    ref = f"tasks/{task_id}/artifacts/hero.png"
    resolved = resolve_user_path(ACCOUNT, ref)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(b"png")
    requirement = {"id": "req_image", "text": "Review hero image", "modality": "image"}
    artifact = {"path": ref, "text": ref, "hub": True}
    calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(op: str, sent_params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(sent_params)))
        assert op == "webai_claude_upload_and_query"
        assert sent_params["files"] == [str(resolved)]
        argv, err = compat.validate_request("webai_claude_upload_and_query", sent_params)
        assert err is None
        assert argv is not None
        return {"outcome": "ok", "payload": {"response_text": json.dumps(_verdict(issues=[], evidence=[]))}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)

    result = run_critique_loop(
        ACCOUNT,
        task_id,
        requirement,
        artifact,
        "round_1:fanout_req_image",
        reviewer_families=("web:claude",),
    )

    assert result.status == "delivered"
    assert result.terminated_by == "consensus"
    assert calls[0][0] == "webai_claude_upload_and_query"


def test_d24_gate_off_unchanged_and_file_reviewer_branch_remains_confined(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[object] = []
    monkeypatch.delenv("NOETICBRAID_PLATFORM_HUB_EXEC", raising=False)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setattr(nodes_mod.hub_adapter, "dispatch", lambda *_args, **_kwargs: calls.append((_args, _kwargs)) or {})

    outcome = HubExecutionNode().execute({"id": "fanout"}, {"account": ACCOUNT, "task_id": "task_gate_off"})

    assert outcome.status == "deferred"
    assert outcome.reason == capability_for("web_ai").blocked_reason
    assert outcome.evidence_node_ids == []
    assert calls == []

    task_id = "task_file_review"
    ref = f"tasks/{task_id}/artifacts/hero.png"
    resolved = resolve_user_path(ACCOUNT, ref)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(b"png")
    route = resolve_web_modality("image")
    assert route.kind == "route"
    params = critique_mod._web_reviewer_params(  # noqa: SLF001
        route,
        ACCOUNT,
        task_id,
        {"id": "req_image", "text": "Generate", "modality": "image"},
        {"path": ref, "text": ref, "hub": True},
        ["round_1:fanout_req_image"],
        1,
        None,
    )
    assert isinstance(params, dict)
    assert params["files"] == [str(resolved)]
    assert set(params) == {"profile", "query", "files"}
