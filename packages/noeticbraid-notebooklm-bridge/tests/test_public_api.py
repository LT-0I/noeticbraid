from __future__ import annotations

import inspect

from noeticbraid.tools import notebooklm_bridge as nb


def test_public_api_signatures_match_blueprint() -> None:
    assert str(inspect.signature(nb.push_sources)) == "(session: 'BrowserSession', notebook_id: 'str', sources: 'list[dict]', *, timeout_s: 'int' = 60) -> 'list[str]'"
    assert str(inspect.signature(nb.pull_briefing)) == "(session: 'BrowserSession', notebook_id: 'str', *, timeout_s: 'int' = 120) -> 'str'"
    assert str(inspect.signature(nb.pull_faq)) == "(session: 'BrowserSession', notebook_id: 'str', *, timeout_s: 'int' = 120) -> 'list[dict]'"
    assert str(inspect.signature(nb.to_source_records)) == "(notebook_id: 'str', briefing_text: 'str', run_id: 'str') -> 'list[dict]'"


def test_errors_are_exported() -> None:
    assert issubclass(nb.NotebookLMLoginRequiredError, nb.NotebookLMBridgeError)
    assert issubclass(nb.NotebookLMSessionContractError, nb.NotebookLMBridgeError)
