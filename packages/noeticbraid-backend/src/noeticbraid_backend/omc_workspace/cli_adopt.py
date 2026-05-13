# SPDX-License-Identifier: Apache-2.0
"""CLI entrypoint for explicit OMC candidate adoption."""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from noeticbraid_core.schemas import CandidateLesson

from . import adoption
from .project_store import OMCProjectStore

WORKSPACE_ROOT_ENV = "NOETICBRAID_WORKSPACE_ROOT"
_CANDIDATE_ID_RE = re.compile(r"^(memory|note)_[A-Za-z0-9_]+$")
_ALREADY_ADOPTED_STATUSES = {"adopted", "confirmed"}


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add adopt-candidate arguments to an existing argparse parser."""

    parser.add_argument("candidate_id", help="OMC candidate id to adopt, e.g. memory_omc_ingest_debate_loop")
    parser.add_argument("--yes", action="store_true", help="Skip the interactive adoption confirmation prompt")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=f"Workspace root; defaults to ${WORKSPACE_ROOT_ENV} or the current directory",
    )
    return parser


def build_parser(prog: str = "noeticbraid omc adopt-candidate") -> argparse.ArgumentParser:
    """Build the standalone parser for this subcommand."""

    parser = argparse.ArgumentParser(prog=prog, description="Explicitly adopt an OMC candidate lesson")
    return add_arguments(parser)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI adopt-candidate command and return its process exit code."""

    parser = build_parser()
    try:
        args = parser.parse_args(_normalize_argv(argv))
    except SystemExit as exc:
        return _system_exit_code(exc)
    return _run(args)


def _run(args: argparse.Namespace, *, stdin: io.TextIOBase | None = None) -> int:
    """Adopt the requested candidate through the authoritative adoption function."""

    candidate_id = str(args.candidate_id)
    if not _CANDIDATE_ID_RE.fullmatch(candidate_id):
        print(f"invalid candidate_id format: {candidate_id}", file=sys.stderr)
        return 4

    project_root = _resolve_project_root(args)
    store = OMCProjectStore(_state_dir_for_project(project_root))
    row = store.find_candidate(candidate_id)
    if row is None:
        print(f"candidate not found: {candidate_id}", file=sys.stderr)
        return 1

    try:
        candidate = validate_candidate_record(row)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 4

    if candidate.get("status") in _ALREADY_ADOPTED_STATUSES:
        print(f"candidate already confirmed: {candidate_id}", file=sys.stderr)
        return 3

    if not bool(getattr(args, "yes", False)):
        input_stream = stdin if stdin is not None else sys.stdin
        if not input_stream.isatty():
            print("non-interactive shell requires --yes", file=sys.stderr)
            return 2
        print(f"Adopt candidate {candidate_id} (status: candidate → confirmed)? [y/N]: ", end="", file=sys.stderr, flush=True)
        if input_stream.readline().strip().casefold() not in {"y", "yes"}:
            return 2

    try:
        adopted = adoption.adopt_candidate(candidate, project_root=project_root, actor="cli-user")
        store.adopt_candidate(adopted["candidate"])
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 4

    print(_resolved_artifact_path(project_root, str(adopted["adoption_artifact_ref"])))
    return 0


def validate_candidate_record(row: dict[str, Any]) -> dict[str, Any]:
    """Validate a persisted candidate row and return its canonical JSON form."""

    return CandidateLesson.model_validate(row).model_dump(mode="json")


def _normalize_argv(argv: list[str] | None) -> list[str] | None:
    """Accept either direct subcommand args or the dispatcher-shaped argv used in tests."""

    if argv is None:
        return None
    items = list(argv)
    if len(items) >= 2 and items[0] == "omc" and items[1] == "adopt-candidate":
        return items[2:]
    if items and items[0] == "adopt-candidate":
        return items[1:]
    return items


def _resolve_project_root(args: argparse.Namespace) -> Path:
    configured = getattr(args, "project_root", None) or os.environ.get(WORKSPACE_ROOT_ENV) or Path.cwd()
    return Path(configured).expanduser().resolve()


def _state_dir_for_project(project_root: Path) -> Path:
    return project_root / "state"


def _resolved_artifact_path(project_root: Path, artifact_ref: str) -> str:
    artifact_path = Path(artifact_ref)
    if not artifact_path.is_absolute():
        artifact_path = project_root / artifact_path
    return str(artifact_path.resolve())


def _system_exit_code(exc: SystemExit) -> int:
    code = exc.code
    if isinstance(code, int):
        return code
    return 2


__all__ = ["add_arguments", "build_parser", "main"]
