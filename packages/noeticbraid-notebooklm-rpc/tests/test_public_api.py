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
        "NotebookLMLifecycleError",
        "NOTEBOOK_TAG",
        "notebook_to_source_record",
        "share_notebook_with_user",
        "set_notebook_public_with_view_level",
        "NotebookLMSourceError",
        "SOURCE_TYPE_TO_TAG",
        "SOURCE_TYPE_TO_RECORD_TYPE",
        "source_to_source_record",
        "add_file_and_serialize",
        "add_url_and_serialize",
        "add_drive_and_serialize",
        "add_text_and_serialize",
        "NotebookLMNoteError",
        "NotebookLMChatError",
        "NOTE_TAG",
        "note_to_source_record",
        "create_note_and_serialize",
        "update_note_and_serialize",
        "ask_and_save_as_note",
        "NotebookLMArtifactLifecycleError",
        "revise_slide_and_serialize",
    }
    assert len(rpc.__all__) == 55


def test_no_playwright_imported():
    assert "playwright" not in sys.modules


def test_upstream_identity_equal():
    assert rpc.NotebookLMClient is notebooklm.NotebookLMClient
    assert rpc.AuthTokens is notebooklm.AuthTokens


def test_no_PooledNotebookLMClient():
    assert not hasattr(rpc, "PooledNotebookLMClient")
