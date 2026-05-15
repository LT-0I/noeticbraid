from __future__ import annotations

import noeticbraid.tools.notebooklm_rpc as rpc
from noeticbraid.tools.notebooklm_rpc import (
    NotebookLMArtifactLifecycleError,
    NotebookLMPoolError,
)


D5_01_NAMES = {
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

D5_02_NAMES = {
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

D5_03_NAMES = {
    "NotebookLMLifecycleError",
    "NOTEBOOK_TAG",
    "notebook_to_source_record",
    "share_notebook_with_user",
    "set_notebook_public_with_view_level",
}

D5_04_NAMES = {
    "NotebookLMSourceError",
    "SOURCE_TYPE_TO_TAG",
    "SOURCE_TYPE_TO_RECORD_TYPE",
    "source_to_source_record",
    "add_file_and_serialize",
    "add_url_and_serialize",
    "add_drive_and_serialize",
    "add_text_and_serialize",
}

D5_05_NAMES = {
    "NotebookLMNoteError",
    "NotebookLMChatError",
    "NOTE_TAG",
    "note_to_source_record",
    "create_note_and_serialize",
    "update_note_and_serialize",
    "ask_and_save_as_note",
}

D5_06_NAMES = {
    "NotebookLMArtifactLifecycleError",
    "revise_slide_and_serialize",
}

D5_01_TO_05_NAMES = D5_01_NAMES | D5_02_NAMES | D5_03_NAMES | D5_04_NAMES | D5_05_NAMES

ARTIFACT_LIFECYCLE_ERROR_CLASSES = {
    "empty_notebook_id",
    "empty_artifact_id",
    "revision_failed",
    "artifact_not_found_after_revision",
}


def test_public_api_has_55_names():
    assert len(rpc.__all__) == 55
    assert set(rpc.__all__) == D5_01_TO_05_NAMES | D5_06_NAMES


def test_d5_06_names_present():
    assert D5_06_NAMES <= set(rpc.__all__)


def test_d5_01_to_05_names_byte_equal():
    assert D5_01_TO_05_NAMES < set(rpc.__all__)


def test_error_inherits_pool_error():
    assert issubclass(NotebookLMArtifactLifecycleError, NotebookLMPoolError)


def test_error_class_enum_exhaustive():
    for error_class in ARTIFACT_LIFECYCLE_ERROR_CLASSES:
        error = NotebookLMArtifactLifecycleError(error_class=error_class)
        assert error.error_class == error_class
        assert error_class in (NotebookLMArtifactLifecycleError.__doc__ or "")


def test_d5_06_public_names_importable_from_modules():
    from noeticbraid.tools.notebooklm_rpc._artifact_lifecycle import revise_slide_and_serialize
    from noeticbraid.tools.notebooklm_rpc._errors import NotebookLMArtifactLifecycleError

    assert revise_slide_and_serialize is rpc.revise_slide_and_serialize
    assert NotebookLMArtifactLifecycleError is rpc.NotebookLMArtifactLifecycleError
