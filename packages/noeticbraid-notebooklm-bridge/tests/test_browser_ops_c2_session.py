from __future__ import annotations

import pytest

from noeticbraid.tools.notebooklm_bridge import (
    NotebookLMLoginRequiredError,
    pull_briefing,
    pull_faq,
    push_sources,
)


def test_push_sources_accepts_current_c2_session_shape(fake_c2_session) -> None:
    refs = push_sources(
        fake_c2_session,
        "notebook_abc",
        [
            {"url": "https://example.com/paper"},
            {"title": "Reflection", "text": "Evidence text."},
        ],
        timeout_s=30,
    )

    assert len(refs) == 2
    assert all(ref.startswith("source_") for ref in refs)
    assert "navigate" in fake_c2_session.call_names
    assert "eval" in fake_c2_session.call_names
    assert "click" in fake_c2_session.call_names
    assert "type_text" in fake_c2_session.call_names
    assert "evaluate" not in fake_c2_session.call_names
    assert "wait_for" not in fake_c2_session.call_names
    typed_values = [args[0] for name, args in fake_c2_session.calls if name == "type_text"]
    assert "https://example.com/paper" in typed_values
    assert "Evidence text." in typed_values


def test_pull_briefing_and_faq_use_current_c2_eval(fake_c2_session) -> None:
    briefing = pull_briefing(fake_c2_session, "notebook_abc", timeout_s=30)
    faq = pull_faq(fake_c2_session, "notebook_abc", timeout_s=30)

    assert "Synthesized grounded answer" in briefing
    assert faq == [{"q": "What is SP-H?", "a": "The NotebookLM bridge."}]
    assert "eval" in fake_c2_session.call_names


def test_login_required_is_manual_gate(fake_c2_session) -> None:
    fake_c2_session.login_required = True

    with pytest.raises(NotebookLMLoginRequiredError, match="manual"):
        push_sources(fake_c2_session, "notebook_abc", [{"url": "https://example.com"}])


def test_selector_errors_are_not_wrapped(monkeypatch, fake_c2_session) -> None:
    from noeticbraid.tools.notebooklm_bridge import NotebookLMSelectorError
    import noeticbraid.tools.notebooklm_bridge._browser_ops as ops

    def raise_selector_error():
        raise NotebookLMSelectorError("bad selector config")

    monkeypatch.setattr(ops, "_load_selectors", raise_selector_error)
    with pytest.raises(NotebookLMSelectorError, match="bad selector config"):
        push_sources(fake_c2_session, "notebook_abc", [{"url": "https://example.com"}])


def test_wrapped_errors_redact_sensitive_strings(monkeypatch, fake_c2_session) -> None:
    import noeticbraid.tools.notebooklm_bridge._browser_ops as ops
    from noeticbraid.tools.notebooklm_bridge import NotebookLMUnexpectedStateError

    def boom(*args, **kwargs):
        raise RuntimeError("Authorization: Bearer secret-token")

    monkeypatch.setattr(ops, "_open_notebook", boom)
    with pytest.raises(NotebookLMUnexpectedStateError) as excinfo:
        push_sources(fake_c2_session, "notebook_abc", [{"url": "https://example.com"}])
    assert "secret-token" not in str(excinfo.value)
    assert "[REDACTED]" in str(excinfo.value)


def test_extract_text_text_candidate_does_not_return_body_text() -> None:
    from noeticbraid.tools.notebooklm_bridge._browser_ops import _script_extract_text

    script = _script_extract_text(["text=Briefing"], marker="briefing_content")
    assert "return bodyText();" not in script
