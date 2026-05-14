from __future__ import annotations

from pathlib import Path

import notebooklm
import pytest

from noeticbraid.tools.notebooklm_rpc import (
    KIND_TO_DOWNLOAD_METHOD,
    ArtifactKind,
    generate_and_download_cinematic_video,
    generate_and_download_data_table,
    generate_and_download_flashcards,
    generate_and_download_infographic,
    generate_and_download_quiz,
    generate_and_download_report,
    generate_and_download_slide_deck,
    generate_and_download_study_guide,
    generate_and_download_video,
)


class FakeArtifacts:
    def __init__(self):
        self.calls = []
        self.counter = 0

    def __getattr__(self, name):
        if name.startswith("generate_"):
            async def generate(notebook_id, **kwargs):
                self.counter += 1
                self.calls.append(("generate", name, notebook_id, kwargs))
                assert all(value is not None for value in kwargs.values())
                return notebooklm.GenerationStatus(task_id=f"tk_{self.counter}", status="running")

            return generate

        if name.startswith("download_"):
            async def download(**kwargs):
                self.calls.append(("download", name, kwargs))
                path = Path(kwargs["output_path"])
                path.write_bytes(b"x")
                return str(path)

            return download

        raise AttributeError(name)

    async def wait_for_completion(self, notebook_id, task_id, *, timeout, poll_interval):
        self.calls.append(("wait", notebook_id, task_id, timeout, poll_interval))
        return notebooklm.GenerationStatus(task_id=task_id, status="completed")


class FakeClient:
    def __init__(self):
        self.artifacts = FakeArtifacts()


@pytest.mark.parametrize(
    ("kind", "helper", "generate_method"),
    [
        (ArtifactKind.VIDEO, generate_and_download_video, "generate_video"),
        (ArtifactKind.CINEMATIC_VIDEO, generate_and_download_cinematic_video, "generate_cinematic_video"),
        (ArtifactKind.REPORT, generate_and_download_report, "generate_report"),
        (ArtifactKind.STUDY_GUIDE, generate_and_download_study_guide, "generate_study_guide"),
        (ArtifactKind.QUIZ, generate_and_download_quiz, "generate_quiz"),
        (ArtifactKind.FLASHCARDS, generate_and_download_flashcards, "generate_flashcards"),
        (ArtifactKind.INFOGRAPHIC, generate_and_download_infographic, "generate_infographic"),
        (ArtifactKind.SLIDE_DECK, generate_and_download_slide_deck, "generate_slide_deck"),
        (ArtifactKind.DATA_TABLE, generate_and_download_data_table, "generate_data_table"),
    ],
)
async def test_generate_and_download_other_kind_happy_path(tmp_path, kind, helper, generate_method):
    client = FakeClient()
    output_path = tmp_path / f"{kind.value}.bin"

    status, path = await helper(client, "nb_1", output_path)

    assert isinstance(status, notebooklm.GenerationStatus)
    assert path == output_path
    assert client.artifacts.calls[0][0:2] == ("generate", generate_method)
    assert client.artifacts.calls[1][0] == "wait"
    assert client.artifacts.calls[2][0:2] == ("download", KIND_TO_DOWNLOAD_METHOD[kind])
    assert client.artifacts.calls[2][2]["artifact_id"] == status.task_id

    if kind is ArtifactKind.REPORT:
        assert "report_format" not in client.artifacts.calls[0][3]

        explicit_client = FakeClient()
        explicit = object()
        await helper(explicit_client, "nb_1", tmp_path / "report-explicit.bin", report_format=explicit)
        assert explicit_client.artifacts.calls[0][3]["report_format"] is explicit
