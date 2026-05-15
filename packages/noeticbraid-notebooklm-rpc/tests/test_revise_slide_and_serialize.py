from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import notebooklm
import pytest
from notebooklm import Artifact, GenerationStatus

from noeticbraid.tools.notebooklm_rpc import (
    ARTIFACT_KIND_TO_TAG,
    ArtifactKind,
    NotebookLMArtifactLifecycleError,
    revise_slide_and_serialize,
)


pytestmark = pytest.mark.asyncio
AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
_UNSET = object()


def make_status(*, task_id: str = "t1", status: str = "pending", error: str | None = None) -> GenerationStatus:
    return GenerationStatus(task_id=task_id, status=status, error=error)


def make_artifact(*, artifact_id: str = "a1", title: str = "Deck") -> Artifact:
    return Artifact(id=artifact_id, title=title, _artifact_type=8, status="completed")


def load_source_record_schema() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    schema_path = (
        repo_root
        / "packages"
        / "noeticbraid-obsidian"
        / "src"
        / "noeticbraid_obsidian"
        / "schemas"
        / "source_record_note.schema.json"
    )
    if not schema_path.exists():
        pytest.fail("source_record_note.schema.json not reachable; obsidian package required for rls-1n")
    return json.loads(schema_path.read_text())


class FakeArtifactsAPI:
    def __init__(
        self,
        *,
        revise_outcome: GenerationStatus | BaseException | object = _UNSET,
        wait_outcome: GenerationStatus | BaseException | object = _UNSET,
        get_outcome: Artifact | None | BaseException | object = _UNSET,
    ) -> None:
        self.revise_outcome = make_status(status="pending") if revise_outcome is _UNSET else revise_outcome
        self.wait_outcome = make_status(status="completed") if wait_outcome is _UNSET else wait_outcome
        self.get_outcome = make_artifact() if get_outcome is _UNSET else get_outcome
        self.calls: list[dict[str, Any]] = []

    async def revise_slide(self, *args: Any, **kwargs: Any) -> GenerationStatus:
        self.calls.append({"method": "revise_slide", "args": args, "kwargs": kwargs})
        if isinstance(self.revise_outcome, BaseException):
            raise self.revise_outcome
        return self.revise_outcome

    async def wait_for_completion(self, *args: Any, **kwargs: Any) -> GenerationStatus:
        self.calls.append({"method": "wait_for_completion", "args": args, "kwargs": kwargs})
        if isinstance(self.wait_outcome, BaseException):
            raise self.wait_outcome
        return self.wait_outcome

    async def get(self, *args: Any, **kwargs: Any) -> Artifact | None:
        self.calls.append({"method": "get", "args": args, "kwargs": kwargs})
        if isinstance(self.get_outcome, BaseException):
            raise self.get_outcome
        return self.get_outcome


class FakeClient:
    def __init__(self, artifacts: FakeArtifactsAPI) -> None:
        self.artifacts = artifacts


async def invoke(
    client: FakeClient,
    *,
    artifact_id: str = "a1",
    title_override: str | None = None,
    local_path: Path | None = None,
    content_hash: str | None = None,
    retrieved_by_run_id: str | None = None,
) -> tuple[GenerationStatus, Artifact, dict[str, Any]]:
    return await revise_slide_and_serialize(
        client,
        "nb_1",
        artifact_id,
        2,
        "Make slide concise",
        captured_at=AWARE_UTC,
        timeout=12.5,
        title_override=title_override,
        local_path=local_path,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )


async def test_happy_returns_status_artifact_dict():
    revise_status = make_status(task_id="t1", status="pending")
    final_status = make_status(task_id="t1", status="completed")
    artifact = make_artifact(artifact_id="a1", title="Deck")
    artifacts = FakeArtifactsAPI(
        revise_outcome=revise_status,
        wait_outcome=final_status,
        get_outcome=artifact,
    )
    client = FakeClient(artifacts)

    final, returned_artifact, record = await invoke(client)

    assert final is final_status
    assert final.is_complete is True
    assert final.is_failed is False
    assert returned_artifact is artifact
    assert record["source_ref_id"] == "source_notebooklm_a1"
    assert record["title"] == "Deck"
    assert record["source_fingerprint"] == "notebooklm_artifact:a1"
    assert artifacts.calls == [
        {"method": "revise_slide", "args": ("nb_1", "a1", 2, "Make slide concise"), "kwargs": {}},
        {"method": "wait_for_completion", "args": ("nb_1", "t1"), "kwargs": {"timeout": 12.5}},
        {"method": "get", "args": ("nb_1", "a1"), "kwargs": {}},
    ]


async def test_empty_notebook_id_raises():
    artifacts = FakeArtifactsAPI()
    client = FakeClient(artifacts)

    with pytest.raises(NotebookLMArtifactLifecycleError) as excinfo:
        await revise_slide_and_serialize(
            client,
            "",
            "a1",
            2,
            "prompt",
            captured_at=AWARE_UTC,
        )

    assert excinfo.value.error_class == "empty_notebook_id"
    assert artifacts.calls == []


async def test_empty_artifact_id_raises():
    artifacts = FakeArtifactsAPI()
    client = FakeClient(artifacts)

    with pytest.raises(NotebookLMArtifactLifecycleError) as excinfo:
        await revise_slide_and_serialize(
            client,
            "nb_1",
            "",
            2,
            "prompt",
            captured_at=AWARE_UTC,
        )

    assert excinfo.value.error_class == "empty_artifact_id"
    assert artifacts.calls == []


async def test_revision_failed_raises():
    artifacts = FakeArtifactsAPI(wait_outcome=make_status(task_id="t1", status="failed", error="boom"))
    client = FakeClient(artifacts)

    with pytest.raises(NotebookLMArtifactLifecycleError) as excinfo:
        await invoke(client)

    assert excinfo.value.error_class == "revision_failed"
    assert excinfo.value.detail == "boom"
    assert "boom" in str(excinfo.value)
    assert [call["method"] for call in artifacts.calls] == ["revise_slide", "wait_for_completion"]


async def test_artifact_none_after_revision_raises():
    artifacts = FakeArtifactsAPI(get_outcome=None)
    client = FakeClient(artifacts)

    with pytest.raises(NotebookLMArtifactLifecycleError) as excinfo:
        await invoke(client)

    assert excinfo.value.error_class == "artifact_not_found_after_revision"
    assert [call["method"] for call in artifacts.calls] == ["revise_slide", "wait_for_completion", "get"]


async def test_title_override_wins():
    client = FakeClient(FakeArtifactsAPI(get_outcome=make_artifact(title="Deck")))

    _, _, record = await invoke(client, title_override="Custom")

    assert record["title"] == "Custom"


async def test_title_fallback_to_artifact_title():
    client = FakeClient(FakeArtifactsAPI(get_outcome=make_artifact(title="Deck Title")))

    _, _, record = await invoke(client, title_override=None)

    assert record["title"] == "Deck Title"


async def test_optional_local_path_passthrough(tmp_path: Path):
    local_path = tmp_path / "slides.pdf"
    local_path.touch()
    client = FakeClient(FakeArtifactsAPI())

    _, _, record = await invoke(client, local_path=local_path)

    assert record["local_path"] == str(local_path)


async def test_optional_content_hash_passthrough():
    content_hash = "sha256:" + "c" * 64
    client = FakeClient(FakeArtifactsAPI())

    _, _, record = await invoke(client, content_hash=content_hash)

    assert record["content_hash"] == content_hash


async def test_optional_retrieved_by_run_id_passthrough():
    client = FakeClient(FakeArtifactsAPI())

    _, _, record = await invoke(client, retrieved_by_run_id="run_x")

    assert record["retrieved_by_run_id"] == "run_x"


async def test_upstream_revise_slide_error_propagates():
    upstream_error = notebooklm.ValidationError("bad slide_index")
    artifacts = FakeArtifactsAPI(revise_outcome=upstream_error)
    client = FakeClient(artifacts)

    with pytest.raises(notebooklm.ValidationError) as excinfo:
        await revise_slide_and_serialize(
            client,
            "nb_1",
            "a1",
            -1,
            "prompt",
            captured_at=AWARE_UTC,
        )

    assert excinfo.value is upstream_error
    assert [call["method"] for call in artifacts.calls] == ["revise_slide"]


async def test_upstream_wait_timeout_propagates():
    upstream_error = TimeoutError("late")
    artifacts = FakeArtifactsAPI(wait_outcome=upstream_error)
    client = FakeClient(artifacts)

    with pytest.raises(TimeoutError) as excinfo:
        await invoke(client)

    assert excinfo.value is upstream_error
    assert [call["method"] for call in artifacts.calls] == ["revise_slide", "wait_for_completion"]


async def test_kind_is_always_slide_deck():
    client = FakeClient(FakeArtifactsAPI())

    _, _, record = await invoke(client)

    assert ARTIFACT_KIND_TO_TAG[ArtifactKind.SLIDE_DECK] in record["tags"]
    assert "noeticbraid/notebooklm/slide-deck" in record["tags"]


async def test_output_validates_against_frozen_schema(tmp_path: Path):
    schema = load_source_record_schema()
    validator = jsonschema.Draft7Validator(schema)
    client = FakeClient(FakeArtifactsAPI())

    _, _, minimal = await invoke(client)
    local_path = tmp_path / "slides.pdf"
    local_path.touch()
    _, _, maximal = await invoke(
        client,
        title_override="Custom",
        local_path=local_path,
        content_hash="sha256:" + "c" * 64,
        retrieved_by_run_id="run_x",
    )

    for record in (minimal, maximal):
        errors = sorted(validator.iter_errors(record), key=lambda error: error.path)
        assert errors == []
