from __future__ import annotations

import noeticbraid.tools.notebooklm_rpc as rpc
from noeticbraid.tools.notebooklm_rpc import (
    NotebookLMChatError,
    NotebookLMNoteError,
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

NOTE_ERROR_CLASSES = {
    "invalid_note_id",
    "empty_notebook_id",
    "empty_note_id",
    "note_not_found",
    "title_empty",
    "naive_captured_at",
    "local_path_missing",
    "invalid_content_hash",
    "invalid_run_id",
}

CHAT_ERROR_CLASSES = {
    "empty_notebook_id",
    "empty_question",
    "empty_ask_answer",
}


def test_public_api_has_53_names():
    assert len(rpc.__all__) == 53
    assert set(rpc.__all__) == D5_01_NAMES | D5_02_NAMES | D5_03_NAMES | D5_04_NAMES | D5_05_NAMES


def test_d5_05_names_present():
    assert D5_05_NAMES <= set(rpc.__all__)


def test_d5_01_02_03_04_names_byte_equal():
    assert D5_01_NAMES | D5_02_NAMES | D5_03_NAMES | D5_04_NAMES < set(rpc.__all__)


def test_note_error_inherits_pool_error():
    assert issubclass(NotebookLMNoteError, NotebookLMPoolError)


def test_chat_error_inherits_pool_error():
    assert issubclass(NotebookLMChatError, NotebookLMPoolError)


def test_note_error_class_enum_exhaustive():
    for error_class in NOTE_ERROR_CLASSES:
        error = NotebookLMNoteError(error_class=error_class)
        assert error.error_class == error_class
        assert error_class in (NotebookLMNoteError.__doc__ or "")


def test_chat_error_class_enum_exhaustive():
    for error_class in CHAT_ERROR_CLASSES:
        error = NotebookLMChatError(error_class=error_class)
        assert error.error_class == error_class
        assert error_class in (NotebookLMChatError.__doc__ or "")


def test_d5_05_public_names_importable_from_modules():
    from noeticbraid.tools.notebooklm_rpc._chat import ask_and_save_as_note
    from noeticbraid.tools.notebooklm_rpc._errors import NotebookLMChatError, NotebookLMNoteError
    from noeticbraid.tools.notebooklm_rpc._notes import (
        NOTE_TAG,
        create_note_and_serialize,
        note_to_source_record,
        update_note_and_serialize,
    )

    assert NOTE_TAG == rpc.NOTE_TAG
    assert note_to_source_record is rpc.note_to_source_record
    assert create_note_and_serialize is rpc.create_note_and_serialize
    assert update_note_and_serialize is rpc.update_note_and_serialize
    assert ask_and_save_as_note is rpc.ask_and_save_as_note
    assert NotebookLMNoteError is rpc.NotebookLMNoteError
    assert NotebookLMChatError is rpc.NotebookLMChatError
