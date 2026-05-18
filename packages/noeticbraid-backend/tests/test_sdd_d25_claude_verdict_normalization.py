# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402,SLF001
"""SDD-D25 Claude web-reviewer verdict extraction/normalization tests (zero network)."""

from __future__ import annotations

import hashlib
import inspect
import json
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
from noeticbraid_backend.platform.orchestrate import critique as critique_mod
from noeticbraid_backend.platform.orchestrate.critique import (
    ReviewerVerdict,
    _call_reviewer,
    _extract_web_verdict_payload,
    _normalize_web_verdict_dict,
    reconcile_verdicts,
    run_critique_loop,
)

ACCOUNT = "d25_user_01"
PROVIDED_EVIDENCE = "round_1:fanout_req_text"
REVISION_EVIDENCE = "round_1:revision_1_req_text"
OTHER_EVIDENCE = "round_1:other_node"
INVENTED_EVIDENCE = "invented:web-only-node"


def _enable_hub(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    data_root = tmp_path / "platform-data"
    hub_root = tmp_path / "hub-root"
    hub_root.mkdir(exist_ok=True)
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("NOETICBRAID_PLATFORM_HUB_EXEC", "1")
    monkeypatch.setenv(compat.HUB_PATH_ENV, str(hub_root))
    monkeypatch.setenv(compat.AUTOMATION_ENV, "1")
    monkeypatch.setattr(critique_mod.compat, "digest_matches", lambda _path: ("ok", None))
    return data_root


def _strict_verdict(*, issues: list[str] | None = None, evidence: list[str] | None = None) -> dict[str, Any]:
    return {
        "reviewer_family": "web:claude",
        "issues": list(issues or []),
        "rationale": "checked against the launch announcement requirement",
        "confidence": 0.83,
        "evidence_node_ids": list(evidence or []),
    }


def _issue(
    *,
    issue_type: Any = "factual_gap",
    description: Any = "missing the cited launch date",
    evidence: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": issue_type,
        "severity": "high",
        "description": description,
        "evidence_node_ids": list(evidence or []),
    }


def _richer_verdict(*, issues: list[dict[str, Any]], reviewer_family: str = "web:claude") -> dict[str, Any]:
    return {"reviewer_family": reviewer_family, "issues": issues}


def _call_with_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    response_text: str,
    *,
    task_id: str,
) -> ReviewerVerdict | critique_mod.CritiqueResult:
    _enable_hub(monkeypatch, tmp_path)
    model.initialize_task_files(ACCOUNT, task_id)

    def dispatch(op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        assert op == "webai_claude_send_prompt"
        return {"outcome": "ok", "status": "ok", "payload": {"response_text": response_text}}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)
    return _call_reviewer(
        "web:claude",
        account=ACCOUNT,
        task_id=task_id,
        requirement={"id": "req_text", "text": "Draft launch announcement", "modality": "text"},
        artifact={"text": "draft", "hub": True, "conversation_id": "conv_text"},
        evidence_node_ids=[PROVIDED_EVIDENCE],
        round_no=1,
        prior_directive=None,
        timeout=1,
    )


def _run_loop_with_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    response_text: str,
    *,
    task_id: str,
) -> tuple[critique_mod.CritiqueResult, Path]:
    data_root = _enable_hub(monkeypatch, tmp_path)
    model.initialize_task_files(ACCOUNT, task_id)
    monkeypatch.setattr(
        critique_mod.hub_adapter,
        "dispatch",
        lambda *_args, **_kwargs: {"outcome": "ok", "status": "ok", "payload": {"response_text": response_text}},
    )
    result = run_critique_loop(
        ACCOUNT,
        task_id,
        {"id": "req_text", "text": "Draft launch announcement", "modality": "text"},
        {"text": "draft", "hub": True, "conversation_id": "conv_text"},
        PROVIDED_EVIDENCE,
        reviewer_families=("web:claude",),
    )
    return result, data_root


def _artifact_paths(data_root: Path, task_id: str, pattern: str) -> list[Path]:
    task_root = data_root / "users" / ACCOUNT / "tasks" / task_id
    return sorted(task_root.rglob(pattern)) if task_root.exists() else []


def _review_artifacts(data_root: Path, task_id: str) -> list[Path]:
    return _artifact_paths(data_root, task_id, "review_*.json")


def _directive_artifacts(data_root: Path, task_id: str) -> list[Path]:
    return _artifact_paths(data_root, task_id, "directive_*.json")


def _assert_deferred_without_artifacts(
    result: critique_mod.CritiqueResult | ReviewerVerdict,
    data_root: Path,
    task_id: str,
    *,
    expected_reason: str | None = None,
) -> None:
    assert isinstance(result, critique_mod.CritiqueResult)
    assert result.status == "deferred"
    assert result.terminated_by == "deferred"
    assert result.rounds == []
    assert result.decision_class == "mechanical"
    assert result.low_confidence is False
    if expected_reason is not None:
        assert result.reason == expected_reason
    assert _review_artifacts(data_root, task_id) == []
    assert _directive_artifacts(data_root, task_id) == []


def _nonconforming_reason(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, response_text: str, *, task_id: str) -> str:
    result = _call_with_response(monkeypatch, tmp_path, response_text, task_id=task_id)
    assert isinstance(result, critique_mod.CritiqueResult)
    assert result.status == "deferred"
    assert result.reason is not None
    return result.reason


def test_d25_empirical_glued_json_extracts_and_run_loop_reaches_consensus(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    verdict = _strict_verdict()
    empirical = (
        "Evaluated artifact against launch announcement requirement"
        "Evaluated artifact against launch announcement requirement"
        f"json{json.dumps(verdict, sort_keys=True)}"
    )
    assert _extract_web_verdict_payload({"payload": {"response_text": empirical}}) == verdict

    result, _data_root = _run_loop_with_response(monkeypatch, tmp_path, empirical, task_id="task_empirical_consensus")

    assert result.status == "delivered"
    assert result.terminated_by == "consensus"


@pytest.mark.parametrize(
    ("response_text", "expected"),
    [
        ("plain prose without json", None),
        ("prefix {\"reviewer_family\": \"web:claude\"", None),
        ("```json\n" + json.dumps(_strict_verdict()) + "\n```", _strict_verdict()),
        (json.dumps(_strict_verdict()), _strict_verdict()),
    ],
)
def test_d25_extraction_negatives_fences_and_pure_json(response_text: str, expected: dict[str, Any] | None) -> None:
    result = {"payload": {"response_text": response_text}}
    parsed = _extract_web_verdict_payload(result)
    if expected is None:
        assert parsed == result["payload"]
    else:
        assert parsed == expected


def test_d25_richer_schema_normalizes_per_issue_and_reconciles_to_real_directive() -> None:
    normalized = _normalize_web_verdict_dict(
        _richer_verdict(
            issues=[
                _issue(evidence=[PROVIDED_EVIDENCE, OTHER_EVIDENCE, PROVIDED_EVIDENCE]),
                _issue(issue_type="scope", description="", evidence=[PROVIDED_EVIDENCE]),
                _issue(issue_type="drop", description="invented only", evidence=[INVENTED_EVIDENCE]),
            ],
            reviewer_family="",
        ),
        [PROVIDED_EVIDENCE],
        "web:claude",
    )

    assert normalized == {
        "reviewer_family": "web:claude",
        "issues": ["factual_gap: missing the cited launch date", "scope"],
        "rationale": "",
        "confidence": 0.0,
        "evidence_node_ids": [PROVIDED_EVIDENCE],
    }
    verdict = ReviewerVerdict.from_json_dict(normalized)
    directive = reconcile_verdicts([verdict])
    assert directive.directive_text.startswith("Address these evidence-cited issues:")
    assert "invented only" not in directive.directive_text
    assert directive.evidence_node_ids == [PROVIDED_EVIDENCE]


def test_d25_two_verdict_shaped_objects_honest_defer_no_guessing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    baseline_reason = _nonconforming_reason(
        monkeypatch,
        tmp_path,
        "plain prose without json",
        task_id="task_two_candidates_baseline",
    )
    example = _strict_verdict(issues=["EXAMPLE only"], evidence=[PROVIDED_EVIDENCE])
    real = _strict_verdict(issues=["REAL issue"], evidence=[PROVIDED_EVIDENCE])
    response_text = f"```json\n{json.dumps(example)}\n```\nUse this instead:\n{json.dumps(real)}"

    result, data_root = _run_loop_with_response(monkeypatch, tmp_path, response_text, task_id="task_two_candidates")

    _assert_deferred_without_artifacts(result, data_root, "task_two_candidates", expected_reason=baseline_reason)


def test_d25_richer_schema_nonprovided_evidence_honest_defers_without_review_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    baseline_response = json.dumps(_richer_verdict(issues=[_issue(evidence=[])]))
    baseline_reason = _nonconforming_reason(
        monkeypatch,
        tmp_path,
        baseline_response,
        task_id="task_richer_nonprovided_baseline",
    )
    response_text = json.dumps(_richer_verdict(issues=[_issue(evidence=[OTHER_EVIDENCE, INVENTED_EVIDENCE])]))

    result, data_root = _run_loop_with_response(monkeypatch, tmp_path, response_text, task_id="task_richer_nonprovided")

    _assert_deferred_without_artifacts(result, data_root, "task_richer_nonprovided", expected_reason=baseline_reason)


def test_d25_mixed_richer_issues_drop_only_unsupported_issue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    response_text = json.dumps(
        _richer_verdict(
            issues=[
                _issue(issue_type="kept", description="A own evidence is provided", evidence=[PROVIDED_EVIDENCE]),
                _issue(issue_type="dropped", description="B cites invented evidence", evidence=[INVENTED_EVIDENCE]),
            ]
        )
    )

    result = _call_with_response(monkeypatch, tmp_path, response_text, task_id="task_mixed_richer")

    assert isinstance(result, ReviewerVerdict)
    assert result.issues == ["kept: A own evidence is provided"]
    assert result.evidence_node_ids == [PROVIDED_EVIDENCE]
    directive = reconcile_verdicts([result])
    assert "A own evidence is provided" in directive.directive_text
    assert "B cites invented evidence" not in directive.directive_text
    assert set(directive.evidence_node_ids).issubset({PROVIDED_EVIDENCE})


@pytest.mark.parametrize(
    "bad_issue",
    [
        _issue(issue_type=123, description={"text": "not a string"}, evidence=[PROVIDED_EVIDENCE]),
        {"severity": "high", "evidence_node_ids": [PROVIDED_EVIDENCE]},
    ],
)
def test_d25_richer_issue_dicts_with_unmappable_text_do_not_fabricate_clean_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bad_issue: dict[str, Any],
) -> None:
    baseline_reason = _nonconforming_reason(
        monkeypatch,
        tmp_path,
        json.dumps(_richer_verdict(issues=[{"severity": "high"}])) ,
        task_id=f"task_unmappable_baseline_{len(str(bad_issue))}",
    )
    response_text = json.dumps(_richer_verdict(issues=[bad_issue]))

    result, data_root = _run_loop_with_response(
        monkeypatch,
        tmp_path,
        response_text,
        task_id=f"task_unmappable_{len(str(bad_issue))}",
    )

    _assert_deferred_without_artifacts(result, data_root, f"task_unmappable_{len(str(bad_issue))}", expected_reason=baseline_reason)


def test_d25_strict_verdict_mixed_provided_and_invented_evidence_honest_defers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = _enable_hub(monkeypatch, tmp_path)
    task_id = "task_strict_mixed_evidence"
    result = _call_with_response(
        monkeypatch,
        tmp_path,
        json.dumps(_strict_verdict(issues=["missing proof"], evidence=[PROVIDED_EVIDENCE, INVENTED_EVIDENCE])),
        task_id=task_id,
    )

    _assert_deferred_without_artifacts(result, data_root, task_id, expected_reason="web reviewer evidence not provided")


def test_d25_embedded_json_string_braces_and_backticks_are_not_misextracted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_inside_string = json.dumps(_strict_verdict(issues=["FAKE embedded"], evidence=[PROVIDED_EVIDENCE]))
    wrapper = json.dumps({"message": fake_inside_string, "note": "literal braces { stay } in a string"})
    real = _strict_verdict(issues=["REAL issue with ```ticks``` and {braces}"], evidence=[PROVIDED_EVIDENCE])
    real["rationale"] = "strings may contain ``` fences ``` and {braces}"
    response_text = f"{wrapper}\n{json.dumps(real)}"

    result = _call_with_response(monkeypatch, tmp_path, response_text, task_id="task_embedded_json_string")

    assert isinstance(result, ReviewerVerdict)
    assert result.issues == ["REAL issue with ```ticks``` and {braces}"]
    assert "FAKE embedded" not in result.issues


def test_d25_bare_fence_bom_and_crlf_single_verdict_parses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    verdict = _strict_verdict(issues=["single fenced issue"], evidence=[PROVIDED_EVIDENCE])
    response_text = "```\r\n\ufeff" + json.dumps(verdict) + "\r\n```"

    result = _call_with_response(monkeypatch, tmp_path, response_text, task_id="task_bare_fence_bom_crlf")

    assert isinstance(result, ReviewerVerdict)
    assert result.issues == ["single fenced issue"]
    assert result.evidence_node_ids == [PROVIDED_EVIDENCE]


def test_d25_genuine_single_richer_verdict_completes_with_real_directive_and_reviews(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = _enable_hub(monkeypatch, tmp_path)
    task_id = "task_positive_richer_completes"
    model.initialize_task_files(ACCOUNT, task_id)
    reviewer_calls = 0

    def dispatch(op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        nonlocal reviewer_calls
        if op == "webai_claude_send_prompt":
            reviewer_calls += 1
            if reviewer_calls == 1:
                return {
                    "outcome": "ok",
                    "payload": {
                        "response_text": json.dumps(
                            _richer_verdict(
                                issues=[
                                    _issue(
                                        issue_type="kept",
                                        description="fully provided richer issue",
                                        evidence=[PROVIDED_EVIDENCE],
                                    )
                                ]
                            )
                        )
                    },
                }
            assert reviewer_calls == 2
            return {"outcome": "ok", "payload": {"response_text": json.dumps(_strict_verdict())}}
        assert op == "webai_chatgpt_send_prompt"
        return {"outcome": "ok", "payload": {"response_text": "revised draft"}, "score": 0.5}

    monkeypatch.setattr(critique_mod.hub_adapter, "dispatch", dispatch)

    result = run_critique_loop(
        ACCOUNT,
        task_id,
        {"id": "req_text", "text": "Draft launch announcement", "modality": "text"},
        {"text": "draft", "hub": True, "conversation_id": "conv_text"},
        PROVIDED_EVIDENCE,
        reviewer_families=("web:claude",),
    )

    assert result.status == "delivered"
    assert result.terminated_by == "consensus"
    assert reviewer_calls == 2
    assert len(_review_artifacts(data_root, task_id)) == 2
    directives = _directive_artifacts(data_root, task_id)
    assert len(directives) == 1
    directive_payload = json.loads(directives[0].read_text(encoding="utf-8"))["directive"]
    assert "fully provided richer issue" in directive_payload["directive_text"]
    assert directive_payload["evidence_node_ids"] == [PROVIDED_EVIDENCE]
    assert result.evidence_node_ids == [REVISION_EVIDENCE]


def test_d25_normalizer_passthroughs_and_never_raises() -> None:
    string_issues = _strict_verdict(issues=["already strict"], evidence=[PROVIDED_EVIDENCE])
    no_issues = {"reviewer_family": "web:claude"}
    odd_inputs: list[Any] = [
        None,
        "text",
        7,
        [],
        {"issues": "not-a-list"},
        {"issues": ["already strict"]},
        {"issues": [object()]},
        {"issues": [{"type": object(), "evidence_node_ids": object()}]},
    ]

    assert _normalize_web_verdict_dict(string_issues, [PROVIDED_EVIDENCE], "web:claude") is string_issues
    assert _normalize_web_verdict_dict(no_issues, [PROVIDED_EVIDENCE], "web:claude") is no_issues
    for value in odd_inputs:
        _normalize_web_verdict_dict(value, [PROVIDED_EVIDENCE], "web:claude")


def test_d25_strict_verdict_subset_passes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    passed = _call_with_response(
        monkeypatch,
        tmp_path,
        json.dumps(_strict_verdict(issues=["missing proof"], evidence=[PROVIDED_EVIDENCE])),
        task_id="task_strict_subset",
    )
    assert isinstance(passed, ReviewerVerdict)
    assert passed.evidence_node_ids == [PROVIDED_EVIDENCE]


@pytest.mark.parametrize("response_text", ["gibberish", ""])
def test_d25_gibberish_and_empty_still_honest_defer_without_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    response_text: str,
) -> None:
    data_root = _enable_hub(monkeypatch, tmp_path)
    task_id = f"task_bad_{response_text or 'empty'}"
    result = _call_with_response(monkeypatch, tmp_path, response_text, task_id=task_id)

    _assert_deferred_without_artifacts(result, data_root, task_id)


def test_d25_blocked_dispatch_still_honest_defer_without_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = _enable_hub(monkeypatch, tmp_path)
    task_id = "task_dispatch_blocked"
    model.initialize_task_files(ACCOUNT, task_id)
    monkeypatch.setattr(
        critique_mod.hub_adapter,
        "dispatch",
        lambda *_args, **_kwargs: {"outcome": "blocked", "reason": "consumer unavailable"},
    )

    result = _call_reviewer(
        "web:claude",
        account=ACCOUNT,
        task_id=task_id,
        requirement={"id": "req_text", "text": "Draft", "modality": "text"},
        artifact={"text": "draft", "hub": True, "conversation_id": "conv_text"},
        evidence_node_ids=[PROVIDED_EVIDENCE],
        round_no=1,
        prior_directive=None,
        timeout=1,
    )

    _assert_deferred_without_artifacts(result, data_root, task_id)
    assert isinstance(result, critique_mod.CritiqueResult)
    assert "consumer unavailable" in str(result.reason)


def test_d25_reviewer_verdict_contract_source_hashes_unchanged() -> None:
    assert hashlib.sha256(inspect.getsource(ReviewerVerdict.from_json_dict).encode()).hexdigest() == (
        "7c1e3f74abae224f414055d039e6248b7d753766bdb9ba2b921ea20d79fc0256"
    )
    assert hashlib.sha256(inspect.getsource(ReviewerVerdict.to_json_dict).encode()).hexdigest() == (
        "c649c3f7009628d88567cbb57660611e2e2dd99c1b23c9609f2ccda30f3ec300"
    )
