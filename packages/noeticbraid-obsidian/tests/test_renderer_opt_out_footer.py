from __future__ import annotations

from noeticbraid_obsidian.resources import resource_root


def _side_note_template() -> str:
    return (resource_root() / "templates" / "side_note.md").read_text(encoding="utf-8")


def test_side_note_footer_contains_opt_out_command_literal() -> None:
    assert "noeticbraid b1-opt-out --note-type=" in _side_note_template()


def test_side_note_footer_contains_pause_command_literal() -> None:
    text = _side_note_template()

    assert "noeticbraid b1-pause" in text
    assert "noeticbraid b1-rebut --note-id=<note_id> --note-type=" in text
