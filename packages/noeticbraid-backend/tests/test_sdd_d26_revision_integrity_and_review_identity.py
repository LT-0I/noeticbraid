# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D26 revision integrity and review artifact identity tests (zero network)."""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.orchestrate import critique as critique_mod
from noeticbraid_backend.platform.orchestrate.critique import (
    CAP_MESSAGE,
    ConsolidatedDirective,
    ReviewerVerdict,
    _apply_directive,
    _call_reviewer,
    run_critique_loop,
)

ACCOUNT = "d26_user_01"
INITIAL_EVIDENCE = "round_1:fanout_req_slides"
TITLE_DIRECTIVE = "Remove the word 'Revised' from the title."


def _enable_hub(monkeypatch: Any, tmp_path: Path) -> Path:
    data_root = tmp_path / "platform-data"
    hub_root = tmp_path / "hub-root"
    hub_root.mkdir()
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("NOETICBRAID_PLATFORM_HUB_EXEC", "1")
    monkeypatch.setenv(critique_mod.compat.HUB_PATH_ENV, str(hub_root))
    monkeypatch.setenv(critique_mod.compat.AUTOMATION_ENV, "1")
    monkeypatch.setattr(critique_mod.compat, "digest_matches", lambda _path: ("ok", None))
    return data_root


def _verdict(*, issues: list[str], evidence: list[str], family: str = "web:claude", rationale: str = "checked") -> dict[str, Any]:
    return {
        "reviewer_family": family,
        "issues": issues,
        "rationale": rationale,
        "confidence": 0.8,
        "evidence_node_ids": evidence,
    }


def _issue_verdict_from_prompt(params: dict[str, Any], issue: str, *, family: str = "web:claude") -> dict[str, Any]:
    payload = json.loads(str(params["prompt"]))
    evidence = payload["evidence_node_ids"]
    return _verdict(issues=[issue], evidence=[evidence[0]], family=family)


def _clean_verdict(family: str = "web:claude") -> dict[str, Any]:
    return _verdict(issues=[], evidence=[], family=family)


def _slides_artifact() -> str:
    sections = [
        "# Revised NoeticBraid Launch Deck",
        "## Slide 1: Vision\nNoeticBraid turns scattered research intent into an auditable workflow.",
        "## Slide 2: User Problem\nTeams lose context when moving from prompt to implementation to review.",
        "## Slide 3: Product Promise\nEvery requirement, artifact, review, and revision remains evidence-linked.",
        "## Slide 4: Workflow\nCapture requirements, generate artifacts, cross-review, revise, and deliver.",
        "## Slide 5: Integrity\nThe system preserves already-reviewed content while applying surgical changes.",
        "## Slide 6: Roles\nGenerators produce artifacts and reviewers cite concrete evidence nodes.",
        "## Slide 7: Web AI\nHub execution remains gated, auditable, and confined to the dispatch chokepoint.",
        "## Slide 8: Honest Q4\nUnavailable or unusable model output reaches honest terminal states.",
        "## Slide 9: Observability\nPersisted artifacts name the server-owned requirement being reviewed.",
        "## Slide 10: Risks\nContent collapse, review misattribution, and over-broad edits are tested.",
        "## Slide 11: Rollout\nShip behind existing gates with no platform-frozen contract changes.",
        "## Slide 12: Close\nNoeticBraid makes AI-assisted delivery traceable without fabricating outcomes.",
    ]
    return "\n\n".join(sections)


def test_d26_revision_prompt_includes_context_instruction_and_trims_artifact_only(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _enable_hub(monkeypatch, tmp_path)
    model.initialize_task_files(ACCOUNT, "task_prompt")
    calls: list[tuple[str, dict[str, Any]]] = []
    requirement = {"id": "req_slides", "text": "Create a launch deck", "modality": "slides"}
    directive = ConsolidatedDirective(TITLE_DIRECTIVE, "mechanical", [INITIAL_EVIDENCE], ["reviewer:web:claude"])
    artifact = {"text": _slides_artifact(), "hub": True, "conversation_id": "conv_slides"}

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(params)))
        return {"outcome": "ok", "payload": {"response_text": "complete revised deck"}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)

    result = _apply_directive(ACCOUNT, "task_prompt", requirement, artifact, directive, timeout=1)

    assert result["ok"] is True
    assert calls[0][0] == "webai_chatgpt_send_prompt"
    prompt = calls[0][1]["prompt"]
    assert requirement["id"] in prompt
    assert requirement["text"] in prompt
    assert requirement["modality"] in prompt
    assert directive.directive_text in prompt
    assert artifact["text"] in prompt
    assert "Apply ONLY the change(s) the directive requires" in prompt
    assert "Preserve ALL other content that already passed review verbatim" in prompt
    assert "Return the COMPLETE revised artifact in full" in prompt
    assert "never a summary, change-note, diff, or acknowledgement" in prompt

    calls.clear()
    monkeypatch.setattr(critique_mod.compat, "PROMPT_MAX_CHARS", 1200)
    long_artifact = {**artifact, "text": artifact["text"] + "\n\n" + ("long retained body " * 1000)}

    truncated = _apply_directive(ACCOUNT, "task_prompt", requirement, long_artifact, directive, timeout=1)

    assert truncated["ok"] is True
    truncated_prompt = calls[0][1]["prompt"]
    assert len(truncated_prompt) <= 1200
    assert directive.directive_text in truncated_prompt
    assert requirement["id"] in truncated_prompt
    assert "Apply ONLY the change(s) the directive requires" in truncated_prompt


def test_d26_file_route_revision_prompt_remains_legacy_directive_only(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _enable_hub(monkeypatch, tmp_path)
    task_id = "task_file_revision_prompt"
    model.initialize_task_files(ACCOUNT, task_id)
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(critique_mod.compat, "PROMPT_MAX_CHARS", 64)
    directive = ConsolidatedDirective(
        "Replace the hero image with a brighter sunrise composition while preserving aspect ratio.",
        "mechanical",
        [INITIAL_EVIDENCE],
        ["reviewer:web:claude"],
    )

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        calls.append((op, dict(params)))
        return {
            "outcome": "ok",
            "payload": {"path": f"tasks/{task_id}/artifacts/revised.png", "response_text": ""},
        }

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)

    result = _apply_directive(
        ACCOUNT,
        task_id,
        {"id": "req_image", "text": "Generate a hero image", "modality": "image"},
        {"text": _slides_artifact(), "hub": True, "conversation_id": "conv_image"},
        directive,
        timeout=1,
    )

    expected_prompt = directive.directive_text[: critique_mod.compat.PROMPT_MAX_CHARS]
    assert result["ok"] is True
    assert calls[0][0] == "webai_chatgpt_generate_image"
    assert calls[0][1]["prompt"] == expected_prompt
    assert calls[0][1]["prompt"].encode("utf-8") == expected_prompt.encode("utf-8")
    assert _slides_artifact() not in calls[0][1]["prompt"]


def test_d26_title_fix_preserves_sections_when_generator_honors_complete_artifact_prompt(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    _enable_hub(monkeypatch, tmp_path)
    task_id = "task_preserve_sections"
    model.initialize_task_files(ACCOUNT, task_id)
    original = _slides_artifact()
    revised = original.replace("# Revised NoeticBraid Launch Deck", "# NoeticBraid Launch Deck")
    reviewer_calls = 0
    generator_prompts: list[str] = []

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal reviewer_calls
        if op == "webai_claude_send_prompt":
            reviewer_calls += 1
            verdict = _issue_verdict_from_prompt(params, TITLE_DIRECTIVE) if reviewer_calls == 1 else _clean_verdict()
            return {"outcome": "ok", "payload": {"response_text": json.dumps(verdict)}}
        assert op == "webai_chatgpt_send_prompt"
        generator_prompts.append(str(params["prompt"]))
        return {"outcome": "ok", "payload": {"response_text": revised}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)

    result = run_critique_loop(
        ACCOUNT,
        task_id,
        {"id": "req_slides", "text": "Create a launch deck", "modality": "slides"},
        {"text": original, "hub": True, "conversation_id": "conv_slides"},
        INITIAL_EVIDENCE,
        reviewer_families=("web:claude",),
    )

    assert result.status == "delivered"
    assert result.terminated_by == "consensus"
    assert "# Revised NoeticBraid Launch Deck" not in result.artifact["text"]
    assert "## Slide 1: Vision" in result.artifact["text"]
    assert "## Slide 8: Honest Q4" in result.artifact["text"]
    assert "## Slide 12: Close" in result.artifact["text"]
    assert TITLE_DIRECTIVE in generator_prompts[0]
    assert original in generator_prompts[0]


def test_d26_non_collapsed_small_delta_still_uses_marginal_exit(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    task_id = "task_non_collapsed_marginal"
    model.initialize_task_files(ACCOUNT, task_id)
    original = _slides_artifact()
    revised_rounds = [
        original.replace("# Revised NoeticBraid Launch Deck", "# NoeticBraid Launch Deck"),
        original.replace("# Revised NoeticBraid Launch Deck", "# NoeticBraid Launch Deck\nSurgical polish applied."),
    ]
    revision_scores = [0.10, 0.12]
    reviewer_calls = 0
    revision_calls = 0

    def local_task(payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
        nonlocal reviewer_calls, revision_calls
        assert timeout > 0
        if payload["kind"] == "critique_review":
            reviewer_calls += 1
            evidence = payload["evidence_node_ids"]
            verdict = _verdict(issues=["title still needs surgical polish"], evidence=evidence, family=payload["reviewer_family"])
            return {"ok": True, "verdict": verdict}
        assert payload["kind"] == "apply_revision_directive"
        text = revised_rounds[revision_calls]
        score = revision_scores[revision_calls]
        revision_calls += 1
        return {"ok": True, "artifact": {"text": text}, "score": score}

    monkeypatch.setattr(critique_mod, "run_local_task", local_task)

    result = run_critique_loop(
        ACCOUNT,
        task_id,
        {"id": "req_slides", "text": "Create a launch deck", "modality": "slides"},
        {"text": original},
        INITIAL_EVIDENCE,
        reviewer_families=("codex", "gemini"),
    )

    assert result.status == "delivered"
    assert result.terminated_by == "marginal"
    assert reviewer_calls == 4
    assert revision_calls == 2
    assert result.artifact["text"] == revised_rounds[-1]
    assert "## Slide 12: Close" in result.artifact["text"]


def test_d26_collapsed_change_note_is_not_counted_as_improvement_or_fabricated_preservation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    data_root = _enable_hub(monkeypatch, tmp_path)
    task_id = "task_collapsed_note"
    model.initialize_task_files(ACCOUNT, task_id)
    original = _slides_artifact()
    collapsed_outputs: list[str] = []
    reviewer_calls = 0
    generator_calls = 0

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal reviewer_calls, generator_calls
        if op == "webai_claude_send_prompt":
            reviewer_calls += 1
            verdict = _issue_verdict_from_prompt(params, TITLE_DIRECTIVE)
            return {"outcome": "ok", "payload": {"response_text": json.dumps(verdict)}}
        assert op == "webai_chatgpt_send_prompt"
        generator_calls += 1
        collapsed = f"NoeticBraid Launch Deck\nTitle corrected: removed 'Revised'.\nrevision attempt {generator_calls}"
        collapsed_outputs.append(collapsed)
        return {"outcome": "ok", "payload": {"response_text": collapsed}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)

    result = run_critique_loop(
        ACCOUNT,
        task_id,
        {"id": "req_slides", "text": "Create a launch deck", "modality": "slides"},
        {"text": original, "hub": True, "conversation_id": "conv_slides"},
        INITIAL_EVIDENCE,
        reviewer_families=("web:claude",),
    )

    assert result.status == "capped"
    assert result.terminated_by == "MAX_ROUNDS"
    assert result.status != "delivered"
    assert result.terminated_by != "marginal"
    assert reviewer_calls == 3
    assert generator_calls == 2
    assert result.artifact["text"] == collapsed_outputs[-1]
    assert "## Slide 12: Close" not in result.artifact["text"]
    assert original not in result.artifact["text"]
    orchestration_root = data_root / "users" / ACCOUNT / "tasks" / task_id / "orchestration"
    for round_no, collapsed in enumerate(collapsed_outputs, start=1):
        payload = json.loads(
            (orchestration_root / f"round_{round_no}" / f"revision_{round_no}_req_slides.json").read_text(encoding="utf-8")
        )
        assert payload["artifact"]["text"] == collapsed
    assert not (orchestration_root / "round_3" / "revision_3_req_slides.json").exists()
    assert not (orchestration_root / "final").exists()


def test_d26_review_artifacts_are_keyed_by_requirement_id_not_model_family(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    data_root = _enable_hub(monkeypatch, tmp_path)
    task_id = "task_review_identity"
    model.initialize_task_files(ACCOUNT, task_id)

    def dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        assert op == "webai_claude_send_prompt"
        payload = json.loads(str(params["prompt"]))
        req_id = payload["requirement"]["id"]
        verdict = _verdict(issues=[], evidence=[], family="text", rationale=f"reviewed {req_id}")
        return {"outcome": "ok", "payload": {"response_text": json.dumps(verdict)}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)
    for req_id in ("req_text", "req_poster"):
        result = _call_reviewer(
            "web:claude",
            account=ACCOUNT,
            task_id=task_id,
            requirement={"id": req_id, "text": f"Draft {req_id}", "modality": "text"},
            artifact={"text": f"artifact for {req_id}", "hub": True, "conversation_id": f"conv_{req_id}"},
            evidence_node_ids=[f"round_1:fanout_{req_id}"],
            round_no=1,
            prior_directive=None,
            timeout=1,
        )
        assert isinstance(result, ReviewerVerdict)
        assert result.reviewer_family == "text"

    round_root = data_root / "users" / ACCOUNT / "tasks" / task_id / "orchestration" / "round_1"
    req_text_payload = json.loads((round_root / "review_req_text_1.json").read_text(encoding="utf-8"))
    req_poster_payload = json.loads((round_root / "review_req_poster_1.json").read_text(encoding="utf-8"))
    assert not (round_root / "review_text_1.json").exists()
    assert req_text_payload["verdict"]["reviewer_family"] == "text"
    assert req_poster_payload["verdict"]["reviewer_family"] == "text"
    assert req_text_payload["verdict"]["rationale"] == "reviewed req_text"
    assert req_poster_payload["verdict"]["rationale"] == "reviewed req_poster"


def test_d26_reviewer_verdict_contract_source_hashes_unchanged() -> None:
    assert hashlib.sha256(inspect.getsource(ReviewerVerdict.from_json_dict).encode()).hexdigest() == (
        "7c1e3f74abae224f414055d039e6248b7d753766bdb9ba2b921ea20d79fc0256"
    )
    assert hashlib.sha256(inspect.getsource(ReviewerVerdict.to_json_dict).encode()).hexdigest() == (
        "c649c3f7009628d88567cbb57660611e2e2dd99c1b23c9609f2ccda30f3ec300"
    )


def test_d26_existing_honest_defer_cap_and_failed_paths_remain_reachable(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.delenv("NOETICBRAID_PLATFORM_HUB_EXEC", raising=False)
    model.initialize_task_files(ACCOUNT, "task_defer")
    calls: list[object] = []
    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", lambda *_args, **_kwargs: calls.append((_args, _kwargs)) or {})

    deferred = run_critique_loop(
        ACCOUNT,
        "task_defer",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft", "hub": True, "conversation_id": "conv_doc"},
        "round_1:fanout_req_doc",
        reviewer_families=("web:claude",),
    )

    assert deferred.status == "deferred"
    assert deferred.terminated_by == "deferred"
    assert deferred.reason == "web execution unavailable"
    assert calls == []

    _enable_hub(monkeypatch, tmp_path)
    model.initialize_task_files(ACCOUNT, "task_cap_missing_conversation")

    def issue_dispatch(_op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        verdict = _issue_verdict_from_prompt(params, "missing cited detail")
        return {"outcome": "ok", "payload": {"response_text": json.dumps(verdict)}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", issue_dispatch)
    capped = run_critique_loop(
        ACCOUNT,
        "task_cap_missing_conversation",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft", "hub": True},
        "round_1:fanout_req_doc",
        reviewer_families=("web:claude",),
    )

    assert capped.status == "capped"
    assert capped.terminated_by == "MAX_ROUNDS"
    assert capped.reason == CAP_MESSAGE

    model.initialize_task_files(ACCOUNT, "task_failed_local")

    def local_task(payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
        assert timeout > 0
        if payload["kind"] == "critique_review":
            evidence = payload["evidence_node_ids"]
            verdict = _verdict(issues=["missing cited detail"], evidence=evidence, family=payload["reviewer_family"])
            return {"ok": True, "verdict": verdict}
        return {"ok": False, "error": "local model unavailable"}

    monkeypatch.setattr(critique_mod, "run_local_task", local_task)
    failed = run_critique_loop(
        ACCOUNT,
        "task_failed_local",
        {"id": "req_doc", "text": "Draft", "modality": "document"},
        {"text": "draft"},
        "round_1:fanout_req_doc",
    )

    assert failed.status == "failed"
    assert failed.terminated_by == "failed"
    assert failed.reason == "local model unavailable"
