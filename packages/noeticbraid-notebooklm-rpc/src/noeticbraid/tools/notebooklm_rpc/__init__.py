"""NoeticBraid NotebookLM RPC wrapper + multi-account pool + artifacts serializer + notebook lifecycle + sources lifecycle.

Pins notebooklm-py==0.4.1 (MIT). See SDD-D5-01, SDD-D5-02, SDD-D5-03, SDD-D5-04.
"""

from __future__ import annotations

# Direct upstream re-export (identity-equal to upstream classes)
from notebooklm import NotebookLMClient, AuthTokens

# NoeticBraid additions
from ._pool import (
    NotebookLMAccountPool, AccountSpec, AccountRuntimeState,
    INELIGIBILITY_REASONS,
)
from ._client import account_op, run_with_pool
from ._errors import (
    NotebookLMPoolError,
    NotebookLMQuotaExceededError,
    NotebookLMAccountUnavailableError,
    NotebookLMPoolStateError,
    NotebookLMSerializationError,
    NotebookLMLifecycleError,
    NotebookLMSourceError,
)
from ._runlog import emit_runlog_event, PoolEventNDJSONSchema
from ._config_schema import POOL_CONFIG_SCHEMA, POOL_STATE_SCHEMA

# D5-02 artifacts surface
from ._artifacts import (
    artifact_to_source_record,
    ArtifactKind,
    ARTIFACT_KIND_TO_TAG,
    KIND_TO_DOWNLOAD_METHOD,
    wait_then_download,
    generate_and_download_audio,
    generate_and_download_video,
    generate_and_download_cinematic_video,
    generate_and_download_report,
    generate_and_download_study_guide,
    generate_and_download_quiz,
    generate_and_download_flashcards,
    generate_and_download_infographic,
    generate_and_download_slide_deck,
    generate_and_download_data_table,
    generate_and_download_mind_map,
)

# D5-03 notebook lifecycle + sharing surface
from ._lifecycle import (
    NOTEBOOK_TAG,
    notebook_to_source_record,
    share_notebook_with_user,
    set_notebook_public_with_view_level,
)

# D5-04 sources surface
from ._sources import (
    SOURCE_TYPE_TO_TAG,
    SOURCE_TYPE_TO_RECORD_TYPE,
    source_to_source_record,
    add_file_and_serialize,
    add_url_and_serialize,
    add_drive_and_serialize,
    add_text_and_serialize,
)

__all__ = [
    # Upstream re-exports (2)
    "NotebookLMClient",
    "AuthTokens",
    # Pool (4)
    "NotebookLMAccountPool",
    "AccountSpec",
    "AccountRuntimeState",
    "INELIGIBILITY_REASONS",
    # Caller-facing helpers (2)
    "account_op",
    "run_with_pool",
    # Errors (4)
    "NotebookLMPoolError",
    "NotebookLMQuotaExceededError",
    "NotebookLMAccountUnavailableError",
    "NotebookLMPoolStateError",
    # Observability (2)
    "emit_runlog_event",
    "PoolEventNDJSONSchema",
    # Schemas (2)
    "POOL_CONFIG_SCHEMA",
    "POOL_STATE_SCHEMA",
    # D5-02 Error (1)
    "NotebookLMSerializationError",
    # D5-02 Serializer (1)
    "artifact_to_source_record",
    # D5-02 Artifact taxonomy (3)
    "ArtifactKind",
    "ARTIFACT_KIND_TO_TAG",
    "KIND_TO_DOWNLOAD_METHOD",
    # D5-02 Generic helper (1)
    "wait_then_download",
    # D5-02 Composite generators (11 — 10 via wait_then_download + 1 special mind_map)
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
    # D5-03 Error (1)
    "NotebookLMLifecycleError",
    # D5-03 Notebook lifecycle + sharing surface (4)
    "NOTEBOOK_TAG",
    "notebook_to_source_record",
    "share_notebook_with_user",
    "set_notebook_public_with_view_level",
    # D5-04 Error (1)
    "NotebookLMSourceError",
    # D5-04 sources surface (7)
    "SOURCE_TYPE_TO_TAG",
    "SOURCE_TYPE_TO_RECORD_TYPE",
    "source_to_source_record",
    "add_file_and_serialize",
    "add_url_and_serialize",
    "add_drive_and_serialize",
    "add_text_and_serialize",
]
assert len(__all__) == 46  # spec-locked: 16 (D5-01) + 17 (D5-02) + 5 (D5-03) + 8 (D5-04)
