"""Command-line interface for the SP-B multimodel alliance runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .constants import FIXTURE_FILES
from .loop import run_debate_loop
from .router import route
from .schema_loader import load_json
from .validator import ValidationError, validate_all, validate_fixture


def _dump(payload: Any, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))


def _read_json_file(path_text: str) -> Any:
    path = Path(path_text)
    if not path.is_file():
        raise FileNotFoundError(f"JSON file not found: {path}")
    return load_json(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="multimodel_alliance", description="SP-B Multimodel Alliance Runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate-fixtures", help="Validate packaged schemas and fixtures")

    route_parser = sub.add_parser("route", help="Generate a ModelRoute JSON record from a task card")
    route_parser.add_argument("task_card", help="Path to task card JSON")
    route_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    fixture_parser = sub.add_parser("run-fixture", help="Validate a fixture wrapper JSON file")
    fixture_parser.add_argument("fixture", help="Path to fixture JSON")
    fixture_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    loop_parser = sub.add_parser("debate-loop", help="Run the manual SDD-D2-01 debate loop over a task card")
    loop_parser.add_argument("task_card", help="Path to task card JSON")
    loop_parser.add_argument("--mock-invocations", action="store_true", help="Use packaged mock provider artifacts (default safe path)")
    loop_parser.add_argument("--manual-invocation-artifact", action="append", default=[], help="Path to a manual provider artifact JSON file; may be repeated")
    loop_parser.add_argument("--provider-mode", action="store_true", help="Explicitly opt into live provider CLI execution")
    loop_parser.add_argument("--state-root", required=True, help="State root for candidate and ledger JSONL outputs")
    loop_parser.add_argument("--artifact-root", required=True, help="Artifact root for route/debate/convergence/markdown outputs")
    loop_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-fixtures":
            validate_all()
            print(f"PASS: validated {len(FIXTURE_FILES)} multimodel alliance fixtures")
            return 0
        if args.command == "route":
            task_card = _read_json_file(args.task_card)
            if not isinstance(task_card, dict):
                raise ValueError("task-card JSON must be an object")
            _dump(route(task_card), args.pretty)
            return 0
        if args.command == "run-fixture":
            fixture = _read_json_file(args.fixture)
            if not isinstance(fixture, dict):
                raise ValueError("fixture JSON must be an object")
            validate_fixture(fixture, str(args.fixture))
            _dump({"fixture_id": fixture.get("fixture_id"), "status": "valid"}, args.pretty)
            return 0
        if args.command == "debate-loop":
            result = run_debate_loop(
                args.task_card,
                state_root=args.state_root,
                artifact_root=args.artifact_root,
                mock_invocations=args.mock_invocations or (not args.manual_invocation_artifact and not args.provider_mode),
                manual_invocation_artifacts=args.manual_invocation_artifact or None,
                provider_mode=args.provider_mode,
            )
            public_result = {key: value for key, value in result.items() if key not in {"route", "debate", "convergence", "candidate", "invocation_plan"}}
            _dump(public_result, args.pretty)
            return 0
    except (OSError, ValueError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
