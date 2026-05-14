from __future__ import annotations

import notebooklm

import noeticbraid.tools.notebooklm_rpc as rpc


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


def test_public_api_has_38_names():
    assert len(rpc.__all__) == 38
    assert set(rpc.__all__) == D5_01_NAMES | D5_02_NAMES | D5_03_NAMES


def test_d5_01_names_byte_equal_in_all():
    assert D5_01_NAMES < set(rpc.__all__)
    for name in D5_01_NAMES:
        assert hasattr(rpc, name)


def test_upstream_identity_preserved():
    assert rpc.NotebookLMClient is notebooklm.NotebookLMClient
    assert rpc.AuthTokens is notebooklm.AuthTokens


def test_no_unexpected_module_attribute_leak():
    standard_module_attrs = {"annotations"}
    leaked = {
        name
        for name in rpc.__dict__
        if not name.startswith("_")
        and name not in set(rpc.__all__)
        and name not in standard_module_attrs
    }
    assert leaked == set()


def test_d5_01_pool_tests_collected_alongside_d5_02():
    assert callable(rpc.account_op)
    assert callable(rpc.run_with_pool)
    assert rpc.POOL_CONFIG_SCHEMA["type"] == "object"
    assert rpc.POOL_STATE_SCHEMA["type"] == "object"
    assert len(rpc.__all__) == 38
