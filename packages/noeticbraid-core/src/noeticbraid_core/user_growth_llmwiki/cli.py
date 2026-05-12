"""On-demand CLI for SDD-D1-02 b-1 detector."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from noeticbraid_core.schemas.side_note_opt_out import (
    THROTTLE_REBUT_THRESHOLD,
    THROTTLE_ROLLING_WINDOW_DAYS,
    RebutRecord,
    SideNoteOptOutNoteType,
    SideNoteOptOutState,
)

from .b1_detector import run_b1_detector_with_report
from .opt_out_store import load_opt_out_state, save_opt_out_state
from .tracked_project import approve, cleanup_expired_candidates, unconfirm

NOTE_TYPE_CHOICES = ("fact", "hypothesis", "action_suggestion")


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

    opt_out_cmd = sub.add_parser("b1-opt-out", help="Disable future b-1 SideNotes of one note type")
    opt_out_cmd.add_argument("--note-type", required=True, choices=NOTE_TYPE_CHOICES)
    opt_out_cmd.set_defaults(func=_cmd_b1_opt_out)

    rebut_cmd = sub.add_parser("b1-rebut", help="Record a user rebuttal for one SideNote")
    rebut_cmd.add_argument("--note-id", required=True, type=_non_empty_note_id)
    rebut_cmd.add_argument("--note-type", required=True, choices=NOTE_TYPE_CHOICES)
    rebut_cmd.set_defaults(func=_cmd_b1_rebut)

    accept_cmd = sub.add_parser("b1-accept", help="Accept a SideNote and reset that note type's rebut counter")
    accept_cmd.add_argument("--note-id", required=True, type=_non_empty_note_id)
    accept_cmd.add_argument("--note-type", required=True, choices=NOTE_TYPE_CHOICES)
    accept_cmd.set_defaults(func=_cmd_b1_accept)

    inaccurate_cmd = sub.add_parser(
        "b1-mark-inaccurate",
        help="Mark a SideNote inaccurate without counting it as a rebuttal",
    )
    inaccurate_cmd.add_argument("--note-id", required=True, type=_non_empty_note_id)
    inaccurate_cmd.add_argument("--note-type", required=True, choices=NOTE_TYPE_CHOICES)
    inaccurate_cmd.set_defaults(func=_cmd_b1_mark_inaccurate)

    pause_cmd = sub.add_parser("b1-pause", help="Pause b-1 SideNote generation")
    pause_cmd.set_defaults(func=_cmd_b1_pause)

    resume_cmd = sub.add_parser(
        "b1-resume",
        help="Resume b-1 SideNote generation; throttle settings are not cleared",
        description="Resume b-1 SideNote generation. This clears paused only and does NOT clear throttled_note_types.",
    )
    resume_cmd.set_defaults(func=_cmd_b1_resume)

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
    if report.paused:
        print("b1 detector paused by SideNote opt-out state")
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


def _cmd_b1_opt_out(args: argparse.Namespace) -> int:
    note_type: SideNoteOptOutNoteType = args.note_type
    state = load_opt_out_state()
    disabled = list(dict.fromkeys([*state.disabled_note_types, note_type]))
    updated = _touch(state, disabled_note_types=disabled)
    save_opt_out_state(updated)
    print(f"disabled SideNote note_type: {note_type}")
    return 0


def _cmd_b1_rebut(args: argparse.Namespace) -> int:
    note_type: SideNoteOptOutNoteType = args.note_type
    note_id = str(args.note_id)
    now = _now_utc()
    state = load_opt_out_state()
    history = _recent_rebuts(state, now)
    if not any(record.note_id == note_id and record.note_type == note_type for record in history):
        history.append(RebutRecord(note_id=note_id, note_type=note_type, timestamp=now))
    throttled = list(dict.fromkeys(state.throttled_note_types))
    count = _distinct_rebut_count(history, note_type, now)
    if count >= THROTTLE_REBUT_THRESHOLD and note_type not in throttled:
        throttled.append(note_type)
    updated = _touch(state, rebut_history=history, throttled_note_types=throttled)
    save_opt_out_state(updated)
    print(f"recorded rebut: {note_id} ({note_type}); rolling_rebut_count={count}")
    if note_type in updated.throttled_note_types:
        print(f"throttled SideNote note_type: {note_type}")
    return 0


def _cmd_b1_accept(args: argparse.Namespace) -> int:
    note_type: SideNoteOptOutNoteType = args.note_type
    state = load_opt_out_state()
    history = [record for record in state.rebut_history if record.note_type != note_type]
    throttled = [item for item in state.throttled_note_types if item != note_type]
    updated = _touch(state, rebut_history=history, throttled_note_types=throttled)
    save_opt_out_state(updated)
    print(f"accepted SideNote: {args.note_id} ({note_type}); reset rebut counter for {note_type}")
    return 0


def _cmd_b1_mark_inaccurate(args: argparse.Namespace) -> int:
    print(f"marked inaccurate without counting as rebut: {args.note_id} ({args.note_type})")
    return 0


def _cmd_b1_pause(args: argparse.Namespace) -> int:
    state = load_opt_out_state()
    save_opt_out_state(_touch(state, paused=True))
    print("b1 SideNote generation paused")
    return 0


def _cmd_b1_resume(args: argparse.Namespace) -> int:
    state = load_opt_out_state()
    save_opt_out_state(_touch(state, paused=False))
    print("b1 SideNote generation resumed; throttled_note_types were not cleared")
    return 0


def _non_empty_note_id(value: str) -> str:
    note_id = str(value).strip()
    if not note_id:
        raise argparse.ArgumentTypeError("note_id must be non-empty")
    return note_id


def _touch(state: SideNoteOptOutState, **updates: object) -> SideNoteOptOutState:
    return state.model_copy(update={**updates, "last_updated": _now_utc()})


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _recent_rebuts(state: SideNoteOptOutState, now: datetime) -> list[RebutRecord]:
    start = now - timedelta(days=THROTTLE_ROLLING_WINDOW_DAYS)
    return [record for record in state.rebut_history if start <= record.timestamp <= now]


def _distinct_rebut_count(
    records: list[RebutRecord], note_type: SideNoteOptOutNoteType, now: datetime
) -> int:
    start = now - timedelta(days=THROTTLE_ROLLING_WINDOW_DAYS)
    return len(
        {
            record.note_id
            for record in records
            if record.note_type == note_type and start <= record.timestamp <= now
        }
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
