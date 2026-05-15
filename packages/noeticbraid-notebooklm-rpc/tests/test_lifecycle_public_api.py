from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

import noeticbraid.tools.notebooklm_rpc as rpc
from noeticbraid.tools.notebooklm_rpc import (
    NotebookLMLifecycleError,
    NotebookLMPoolError,
    notebook_to_source_record,
    share_notebook_with_user,
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

EXPECTED_ERROR_CLASSES = {
    "invalid_notebook_id",
    "title_empty",
    "naive_captured_at",
    "invalid_run_id",
    "invalid_content_hash",
    "invalid_email",
    "empty_notebook_id",
}


@dataclass
class Stub:
    id: str = "nb_1"
    title: str = "My NB"


def test_public_api_has_38_names():
    assert len(rpc.__all__) == 46
    assert set(rpc.__all__) == D5_01_NAMES | D5_02_NAMES | D5_03_NAMES | D5_04_NAMES


def test_d5_03_names_present():
    assert D5_03_NAMES <= set(rpc.__all__)


def test_d5_02_names_byte_equal_in_all():
    assert D5_02_NAMES < set(rpc.__all__)
    assert D5_01_NAMES < set(rpc.__all__)


def test_lifecycle_error_inherits_pool_error():
    assert issubclass(NotebookLMLifecycleError, NotebookLMPoolError)


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


def test_lifecycle_error_class_attribute_present():
    error = NotebookLMLifecycleError(error_class="invalid_email", detail="x")
    assert error.error_class == "invalid_email"
    assert error.detail == "x"


async def test_lifecycle_error_class_enum_set_exhaustive():
    for error_class in EXPECTED_ERROR_CLASSES:
        error = NotebookLMLifecycleError(error_class=error_class, detail="x")
        assert error.error_class == error_class
        assert error_class in (NotebookLMLifecycleError.__doc__ or "")

    observed = set()
    captured_at = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)

    probes = [
        lambda: notebook_to_source_record(Stub(id="bad-nb!"), captured_at=captured_at),
        lambda: notebook_to_source_record(Stub(title="   "), captured_at=captured_at),
        lambda: notebook_to_source_record(Stub(), captured_at=datetime(2026, 5, 14, 12, 0, 0)),
        lambda: notebook_to_source_record(Stub(), captured_at=captured_at, retrieved_by_run_id="42"),
        lambda: notebook_to_source_record(Stub(), captured_at=captured_at, content_hash="md5:abc"),
    ]
    for probe in probes:
        with pytest.raises(NotebookLMLifecycleError) as excinfo:
            probe()
        observed.add(excinfo.value.error_class)

    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        await share_notebook_with_user(object(), "nb_1", "not-email")
    observed.add(excinfo.value.error_class)

    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        await share_notebook_with_user(object(), "", "user@example.com")
    observed.add(excinfo.value.error_class)

    assert observed == EXPECTED_ERROR_CLASSES
