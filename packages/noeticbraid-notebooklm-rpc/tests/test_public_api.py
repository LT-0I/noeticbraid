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
        "NotebookLMSerializationError",
        "artifact_to_source_record",
        "ArtifactKind",
        "ARTIFACT_KIND_TO_TAG",
        "KIND_TO_DOWNLOAD_METHOD",
        "wait_then_download",
        "generate_and_download_audio",
        "generate_and_download_video",
        "generate_and_download_cinematic_video",
        "generate_and_download_report",
        "generate_and_download_study_guide",
        "generate_and_download_quiz",
        "generate_and_download_flashcards",
        "generate_and_download_infographic",
        "generate_and_download_slide_deck",
        "generate_and_download_data_table",
        "generate_and_download_mind_map",
    }
    assert len(rpc.__all__) == 33


def test_no_playwright_imported():
    assert "playwright" not in sys.modules


def test_upstream_identity_equal():
    assert rpc.NotebookLMClient is notebooklm.NotebookLMClient
    assert rpc.AuthTokens is notebooklm.AuthTokens


def test_no_PooledNotebookLMClient():
    assert not hasattr(rpc, "PooledNotebookLMClient")
