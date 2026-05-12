"""On-demand CLI for SDD-D1-02 b-1 detector."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .b1_detector import run_b1_detector_with_report
from .tracked_project import approve, cleanup_expired_candidates, unconfirm


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="noeticbraid", description="NoeticBraid user-growth LLMwiki utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    detect = sub.add_parser("b1-detect", help="Run b-1 detector against a vault path")
    detect.add_argument("vault_path", type=Path)
    detect.set_defaults(func=_cmd_b1_detect)

    approve_cmd = sub.add_parser("b1-approve", help="Promote a tracked_project candidate to confirmed")
    approve_cmd.add_argument("project_ref")
    approve_cmd.set_defaults(func=_cmd_b1_approve)

    unconfirm_cmd = sub.add_parser("b1-unconfirm", help="Demote a confirmed tracked_project back to candidate")
    unconfirm_cmd.add_argument("project_ref")
    unconfirm_cmd.set_defaults(func=_cmd_b1_unconfirm)

    cleanup_cmd = sub.add_parser("b1-gate-cleanup", help="Mark expired tracked_project candidates")
    cleanup_cmd.set_defaults(func=_cmd_b1_gate_cleanup)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


def _cmd_b1_detect(args: argparse.Namespace) -> int:
    cleanup_expired_candidates()
    report = run_b1_detector_with_report(args.vault_path)
    print(f"b1 candidates: {report.candidate_count}")
    print(f"queue: {report.queue_path}")
    if report.discovered_candidates:
        print("tracked_project candidates discovered: " + ", ".join(report.discovered_candidates))
    if report.skip_reasons:
        print("skips:")
        for project_ref, reason in sorted(report.skip_reasons.items()):
            print(f"- {project_ref}: {reason}")
    return 0


def _cmd_b1_approve(args: argparse.Namespace) -> int:
    approve(args.project_ref)
    print(f"confirmed: {args.project_ref}")
    return 0


def _cmd_b1_unconfirm(args: argparse.Namespace) -> int:
    unconfirm(args.project_ref)
    print(f"candidate: {args.project_ref}")
    return 0


def _cmd_b1_gate_cleanup(args: argparse.Namespace) -> int:
    expired = cleanup_expired_candidates()
    print(f"expired tracked_project candidates: {len(expired)}")
    for item in expired:
        print(f"- {item.project_ref}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
