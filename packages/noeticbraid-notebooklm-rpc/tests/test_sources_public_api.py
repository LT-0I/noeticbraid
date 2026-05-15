from __future__ import annotations

import importlib

import noeticbraid.tools.notebooklm_rpc as rpc
from noeticbraid.tools.notebooklm_rpc import NotebookLMSourceError, NotebookLMPoolError


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

EXPECTED_SOURCE_ERROR_CLASSES = {
    "invalid_source_id",
    "title_empty",
    "naive_captured_at",
    "local_path_missing",
    "invalid_content_hash",
    "invalid_run_id",
    "source_not_ready",
}


def test_public_api_has_46_names():
    assert len(rpc.__all__) == 46
    assert set(rpc.__all__) == D5_01_NAMES | D5_02_NAMES | D5_03_NAMES | D5_04_NAMES


def test_d5_04_names_present():
    assert D5_04_NAMES <= set(rpc.__all__)


def test_d5_01_d5_02_d5_03_names_byte_equal():
    assert D5_01_NAMES | D5_02_NAMES | D5_03_NAMES < set(rpc.__all__)


def test_source_error_inherits_pool_error():
    assert issubclass(NotebookLMSourceError, NotebookLMPoolError)


def test_error_class_attribute_present():
    error = NotebookLMSourceError(error_class="source_not_ready", detail="x")
    assert error.error_class == "source_not_ready"


def test_error_class_enum_set_exhaustive():
    for error_class in EXPECTED_SOURCE_ERROR_CLASSES:
        error = NotebookLMSourceError(error_class=error_class, detail="x")
        assert error.error_class == error_class
        assert error_class in (NotebookLMSourceError.__doc__ or "")


def test_d5_04_public_names_subset_of_module():
    module = importlib.import_module("noeticbraid.tools.notebooklm_rpc._sources")
    for name in D5_04_NAMES:
        assert hasattr(module, name)
