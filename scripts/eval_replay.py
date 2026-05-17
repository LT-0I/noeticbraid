#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D20 §7a deterministic ZERO-NETWORK structural regression harness.

This CLI is deliberately not the deferred SDD-D20 §7 tuning pass: it does not
capture or replay third-party hub traffic, does not score prompt/output quality,
and does not compare against fabricated quality labels. It replays fixture
scenarios through the fully local public orchestration path with the hub gate
forced off, then asserts structural contract invariants only.

The local model is reached only through the existing operator-env stdin stub
seam (``NOETICBRAID_PLATFORM_LOCAL_AI_BIN`` + args JSON); the scenario payload
remains untrusted input on stdin.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "packages" / "noeticbraid-backend"
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
FIXTURE_DIR = PACKAGE_ROOT / "tests" / "fixtures" / "eval_replay"
ACCOUNT = "eval_replay_account"
HUB_EXEC_ENV = "NOETICBRAID_PLATFORM_HUB_EXEC"

for import_root in (CORE_SRC_ROOT, SRC_ROOT):
    root_text = str(import_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

from noeticbraid_backend.platform.conversation import deliverable_view, model
from noeticbraid_backend.platform.elicitation.local_ai import LOCAL_AI_ARGS_ENV, LOCAL_AI_BIN_ENV
from noeticbraid_backend.platform.orchestrate.engine import run_orchestration
from noeticbraid_backend.platform.orchestrate import state
from noeticbraid_backend.platform.settings import PLATFORM_DATA_ROOT_ENV
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

FORBIDDEN_VIEW_KEYS = frozenset(
    {
        "conversation_id",
        "critique",
        "directive",
        "dispatch",
        "evidence_node_ids",
        "internal-reason",
        "internal_reason",
        "ledger",
        "orchestration",
        "reviewer",
        "rounds",
        "selector",
        "sha",
        "sha256",
        "verdict",
        "workflow",
    }
)


@dataclass(frozen=True, slots=True)
class Scenario:
    path: Path
    name: str
    requirements: list[dict[str, Any]]
    stub_mode: str
    expect: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InvariantResult:
    scenario: str
    invariant: str
    passed: bool
    expected: Any
    actual: Any


def main(argv: Sequence[str] | None = None) -> int:
    """Run all eval-replay fixtures and return nonzero on any invariant failure."""

    if argv:
        print(f"ERROR unexpected arguments: {' '.join(argv)}")
        return 2
    scenarios = _load_scenarios(FIXTURE_DIR)
    all_results: list[InvariantResult] = []
    for scenario in scenarios:
        all_results.extend(_run_scenario(scenario))
    _print_report(scenarios, all_results)
    return 0 if all(result.passed for result in all_results) else 1


def _load_scenarios(fixture_dir: Path) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(fixture_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"scenario must be an object: {path}")
        name = str(payload.get("name") or path.stem).strip()
        requirements = payload.get("requirements")
        expect = payload.get("expect")
        if not isinstance(requirements, list) or not all(isinstance(item, dict) for item in requirements):
            raise ValueError(f"scenario requirements must be objects: {path}")
        if not isinstance(expect, dict):
            raise ValueError(f"scenario expect must be an object: {path}")
        scenarios.append(
            Scenario(
                path=path,
                name=name,
                requirements=[dict(item) for item in requirements],
                stub_mode=str(payload.get("stub_mode") or "consensus"),
                expect=dict(expect),
            )
        )
    return scenarios


def _run_scenario(scenario: Scenario) -> list[InvariantResult]:
    try:
        with tempfile.TemporaryDirectory(prefix=f"eval_replay_{_safe_token(scenario.name)}_") as temp_text:
            temp_root = Path(temp_text)
            data_root = temp_root / "platform-data"
            stub_script = _write_local_task_stub(temp_root, mode=scenario.stub_mode)
            call_log = temp_root / "stub-calls.jsonl"
            with _scenario_env(data_root, stub_script):
                task_id = f"task_eval_replay_{_safe_token(scenario.name)}"
                _seed_confirmed_requirements(task_id, scenario.requirements)
                run_orchestration(ACCOUNT, task_id)
                calls = _load_stub_calls(call_log)
                return _evaluate_scenario(scenario, task_id, calls)
    except Exception as exc:  # keep later fixtures observable in one report
        return [
            InvariantResult(
                scenario=scenario.name,
                invariant="scenario.completed_without_exception",
                passed=False,
                expected="no exception",
                actual=f"{type(exc).__name__}: {exc}",
            )
        ]


def _seed_confirmed_requirements(task_id: str, requirements: list[dict[str, Any]]) -> None:
    model.write_requirements(
        ACCOUNT,
        task_id,
        {
            "task_id": task_id,
            "schema_version": model.REQUIREMENTS_SCHEMA_VERSION,
            "status": "confirmed",
            "requirements": requirements,
            "confirmed_at": model.now_ts(),
        },
    )


def _evaluate_scenario(
    scenario: Scenario,
    task_id: str,
    calls: list[str],
) -> list[InvariantResult]:
    expect = scenario.expect
    requirements_payload = model.load_requirements(ACCOUNT, task_id)
    run_state = state.load_state(ACCOUNT, task_id)
    deliverables = deliverable_view.per_task_deliverables(ACCOUNT, task_id)
    visible_conversation = model.serialize_visible_conversation(ACCOUNT, task_id)
    view_payload = {
        "conversation": visible_conversation,
        "per_task_deliverables": deliverables,
        "coarse_status": model.serialize_coarse_status(requirements_payload),
        "capability_notice": model.capability_notices(requirements_payload),
    }

    results: list[InvariantResult] = []
    _append_result(results, scenario, "run_status", expect.get("run_status"), None if run_state is None else run_state["status"])

    actual_states = {
        str(item.get("id") or ""): str(item.get("coarse_state") or "")
        for item in requirements_payload.get("requirements", [])
        if isinstance(item, dict)
    }
    expected_states = expect.get("per_requirement_coarse_state")
    if isinstance(expected_states, dict):
        for req_id, expected_state in sorted(expected_states.items()):
            _append_result(
                results,
                scenario,
                f"requirement:{req_id}.coarse_state",
                expected_state,
                actual_states.get(str(req_id)),
            )

    _evaluate_deliverables(scenario, expect, deliverables, results)

    if expect.get("all_rounds_hub_false") is True:
        rounds = [] if run_state is None else [row for row in run_state.get("rounds", []) if isinstance(row, dict)]
        actual = all(row.get("hub") is not True for row in rounds)
        _append_result(results, scenario, "all_rounds_hub_false", True, actual)

    if "round_count" in expect:
        rounds = [] if run_state is None else [row for row in run_state.get("rounds", []) if isinstance(row, dict)]
        _append_result(results, scenario, "round_count", expect["round_count"], len(rounds))

    if "stub_call_kinds" in expect:
        _append_result(results, scenario, "stub_call_kinds", expect["stub_call_kinds"], calls)

    if expect.get("no_engineering_keys") is True:
        forbidden = _find_forbidden_keys(view_payload)
        _append_result(results, scenario, "no_engineering_keys", [], forbidden)

    conversation_text = "\n".join(
        str(row.get("text") or "") for row in visible_conversation if isinstance(row, dict)
    )
    for index, needle in enumerate(expect.get("conversation_contains") or [], start=1):
        text = str(needle)
        _append_result(
            results,
            scenario,
            f"conversation_contains:{index}",
            text,
            text if text in conversation_text else conversation_text,
            passed=text in conversation_text,
        )
    for index, needle in enumerate(expect.get("conversation_not_contains") or [], start=1):
        text = str(needle)
        _append_result(
            results,
            scenario,
            f"conversation_not_contains:{index}",
            f"absent:{text}",
            "absent" if text not in conversation_text else text,
            passed=text not in conversation_text,
        )
    return results


def _evaluate_deliverables(
    scenario: Scenario,
    expect: dict[str, Any],
    deliverables: list[dict[str, Any]],
    results: list[InvariantResult],
) -> None:
    expected_rows = expect.get("per_task_deliverables")
    if not isinstance(expected_rows, list):
        return
    actual_by_req = {str(row.get("requirement_id") or ""): row for row in deliverables if isinstance(row, dict)}
    _append_result(results, scenario, "per_task_deliverables.count", len(expected_rows), len(deliverables))
    for expected in expected_rows:
        if not isinstance(expected, dict):
            continue
        req_id = str(expected.get("requirement_id") or "")
        actual = actual_by_req.get(req_id, {})
        _append_result(results, scenario, f"deliverable:{req_id}.status", expected.get("status"), actual.get("status"))
        expected_has_ref = bool(expected.get("has_download_ref"))
        actual_ref = actual.get("download_ref")
        actual_has_ref = isinstance(actual_ref, str) and bool(actual_ref)
        _append_result(
            results,
            scenario,
            f"deliverable:{req_id}.has_download_ref",
            expected_has_ref,
            actual_has_ref,
        )
        if expected_has_ref:
            _append_result(
                results,
                scenario,
                f"deliverable:{req_id}.download_ref_exists",
                True,
                _download_ref_exists(actual_ref),
            )
        if "blocked_reason_contains" in expected:
            expected_text = str(expected["blocked_reason_contains"])
            actual_reason = str(actual.get("blocked_reason") or "")
            _append_result(
                results,
                scenario,
                f"deliverable:{req_id}.blocked_reason_contains",
                expected_text,
                actual_reason,
                passed=expected_text in actual_reason,
            )


def _append_result(
    results: list[InvariantResult],
    scenario: Scenario,
    invariant: str,
    expected: Any,
    actual: Any,
    *,
    passed: bool | None = None,
) -> None:
    results.append(
        InvariantResult(
            scenario=scenario.name,
            invariant=invariant,
            passed=(expected == actual if passed is None else passed),
            expected=expected,
            actual=actual,
        )
    )


def _download_ref_exists(ref: object) -> bool:
    if not isinstance(ref, str) or not ref:
        return False
    ref_path = Path(ref)
    if ref_path.is_absolute() or any(part == ".." for part in ref_path.parts):
        return False
    # Inherit the single per-user path chokepoint instead of hand-building the
    # users/<account>/ layout, so this assertion can never validate a stale
    # path if the canonical layout changes. resolve_user_path reads the data
    # root from the scenario env active in this context.
    return resolve_user_path(ACCOUNT, ref).is_file()


def _find_forbidden_keys(value: Any, path: str = "$.") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            child_path = f"{path}{key_text}"
            if key_text in FORBIDDEN_VIEW_KEYS:
                found.append(child_path)
            found.extend(_find_forbidden_keys(item, f"{child_path}."))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_find_forbidden_keys(item, f"{path}[{index}]."))
    return sorted(found)


@contextmanager
def _scenario_env(data_root: Path, stub_script: Path) -> Iterator[None]:
    updates = {
        PLATFORM_DATA_ROOT_ENV: str(data_root),
        LOCAL_AI_BIN_ENV: sys.executable,
        LOCAL_AI_ARGS_ENV: json.dumps([str(stub_script)]),
    }
    with _patched_env(updates=updates, deletes=(HUB_EXEC_ENV,)):
        yield


@contextmanager
def _patched_env(*, updates: dict[str, str], deletes: Sequence[str]) -> Iterator[None]:
    keys = set(updates) | set(deletes)
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in deletes:
            os.environ.pop(key, None)
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def _write_local_task_stub(tmp_root: Path, *, mode: str) -> Path:
    script = tmp_root / f"eval_replay_stub_{_safe_token(mode)}.py"
    call_log = tmp_root / "stub-calls.jsonl"
    script.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        f"mode = {mode!r}\n"
        f"call_log = Path({str(call_log)!r})\n"
        "envelope = json.loads(sys.stdin.read() or '{}')\n"
        "payload = envelope.get('payload') or {}\n"
        "kind = payload.get('kind') or 'elicitation'\n"
        "with call_log.open('a', encoding='utf-8') as handle:\n"
        "    handle.write(str(kind) + '\\n')\n"
        "if mode == 'local_failure' and kind == 'fanout':\n"
        # Synthetic secret-shaped token assembled at the stub's runtime so this
        # source file holds no contiguous credential-shaped literal (project
        # convention: synthetic secret fixtures are runtime-concatenated, never
        # committed as a contiguous api_key=... literal). The engine sanitizer
        # still redacts the emitted token to 'api_key=[redacted]', which is
        # what fixture 04 asserts.
        "    leak = 'api_' + 'key=' + 'fa' + 'ke'\n"
        "    print('local model failure ' + leak + ' /tmp/noeticbraid-eval-replay', file=sys.stderr)\n"
        "    sys.exit(7)\n"
        "if kind == 'fanout':\n"
        "    req = payload.get('inputs', {}).get('requirement', {})\n"
        "    print(json.dumps({'artifact': {'text': 'draft for ' + str(req.get('id', 'req'))}}, ensure_ascii=False))\n"
        "elif kind == 'critique_review':\n"
        "    evidence = payload.get('evidence_node_ids') or []\n"
        "    fam = payload.get('reviewer_family') or 'unknown'\n"
        "    issues = [] if mode == 'consensus' else ['missing cited detail']\n"
        "    print(json.dumps({'verdict': {'reviewer_family': fam, 'issues': issues, 'rationale': 'checked', 'confidence': 0.8, 'evidence_node_ids': evidence if issues else []}}, ensure_ascii=False))\n"
        "elif kind == 'apply_revision_directive':\n"
        "    artifact = payload.get('artifact') or {}\n"
        "    text = str(artifact.get('text', 'draft')) + ' revised'\n"
        "    score = min(1.0, 0.1 * (text.count('revised') + 1))\n"
        "    print(json.dumps({'artifact': {'text': text}, 'score': score}, ensure_ascii=False))\n"
        "else:\n"
        "    raw = envelope.get('raw_requirement') or 'Draft a document'\n"
        "    print(json.dumps({'requirements': [{'id': 'req_1', 'text': raw, 'modality': 'document'}], 'questions': [], 'ready_to_confirm': True}, ensure_ascii=False))\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _load_stub_calls(call_log: Path) -> list[str]:
    try:
        return [line for line in call_log.read_text(encoding="utf-8").splitlines() if line]
    except FileNotFoundError:
        return []


def _safe_token(value: str) -> str:
    token = "".join(char if char.isalnum() else "_" for char in value.strip().lower())
    token = "_".join(part for part in token.split("_") if part)
    return token[:80] or "scenario"


def _print_report(scenarios: list[Scenario], results: list[InvariantResult]) -> None:
    print("EVAL-REPLAY ZERO-NETWORK STRUCTURAL HARNESS")
    print(f"SCENARIOS={len(scenarios)}")
    by_scenario: dict[str, list[InvariantResult]] = {scenario.name: [] for scenario in scenarios}
    for result in results:
        by_scenario.setdefault(result.scenario, []).append(result)
    for scenario in scenarios:
        scenario_results = by_scenario.get(scenario.name, [])
        failed = sum(1 for result in scenario_results if not result.passed)
        print(f"SCENARIO {scenario.name} invariants={len(scenario_results)} failed={failed}")
        for result in scenario_results:
            status_text = "PASS" if result.passed else "FAIL"
            print(
                f"  {status_text} {result.invariant} "
                f"expected={_format_value(result.expected)} actual={_format_value(result.actual)}"
            )
    total_failed = sum(1 for result in results if not result.passed)
    print(f"SUMMARY scenarios={len(scenarios)} invariants={len(results)} failed={total_failed}")


def _format_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


if __name__ == "__main__":
    sys.exit(main())
