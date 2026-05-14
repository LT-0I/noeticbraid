from __future__ import annotations

import sys

import notebooklm

import noeticbraid.tools.notebooklm_rpc as rpc


def test_public_api_exactly_matches_spec():
    assert set(rpc.__all__) == {
        "NotebookLMClient",
        "AuthTokens",
        "NotebookLMAccountPool",
        "AccountSpec",
        "AccountRuntimeState",
        "INELIGIBILITY_REASONS",
        "account_op",
        "run_with_pool",
        "NotebookLMPoolError",
        "NotebookLMQuotaExceededError",
        "NotebookLMAccountUnavailableError",
        "NotebookLMPoolStateError",
        "emit_runlog_event",
        "PoolEventNDJSONSchema",
        "POOL_CONFIG_SCHEMA",
        "POOL_STATE_SCHEMA",
    }
    assert len(rpc.__all__) == 16


def test_no_playwright_imported():
    assert "playwright" not in sys.modules


def test_upstream_identity_equal():
    assert rpc.NotebookLMClient is notebooklm.NotebookLMClient
    assert rpc.AuthTokens is notebooklm.AuthTokens


def test_no_PooledNotebookLMClient():
    assert not hasattr(rpc, "PooledNotebookLMClient")
