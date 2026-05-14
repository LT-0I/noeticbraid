from __future__ import annotations

from pathlib import Path

import notebooklm
import pytest

from noeticbraid.tools.notebooklm_rpc import NotebookLMSerializationError, wait_then_download


class FakeArtifacts:
    def __init__(self, *, final_status="completed"):
        self.final_status = final_status
        self.wait_calls = []
        self.download_calls = []

    async def wait_for_completion(self, notebook_id, task_id, *, timeout, poll_interval):
        self.wait_calls.append(
            {
                "notebook_id": notebook_id,
                "task_id": task_id,
                "timeout": timeout,
                "poll_interval": poll_interval,
            }
        )
        return notebooklm.GenerationStatus(task_id=task_id, status=self.final_status, error="boom")

    async def download_audio(self, **kwargs):
        self.download_calls.append(kwargs)
        path = Path(kwargs["output_path"])
        path.write_bytes(b"x")
        return str(path)


class FakeClient:
    def __init__(self, artifacts):
        self.artifacts = artifacts


async def test_happy_path(tmp_path):
    output_path = tmp_path / "audio.mp3"
    artifacts = FakeArtifacts()
    client = FakeClient(artifacts)

    path = await wait_then_download(
        client,
        notebook_id="nb_1",
        task_id="tk_1",
        download_method_name="download_audio",
        output_path=output_path,
        timeout=12.5,
        poll_interval=0.5,
    )

    assert path == output_path
    assert artifacts.wait_calls == [
        {"notebook_id": "nb_1", "task_id": "tk_1", "timeout": 12.5, "poll_interval": 0.5}
    ]
    assert artifacts.download_calls == [
        {"notebook_id": "nb_1", "output_path": str(output_path), "artifact_id": "tk_1"}
    ]
    assert output_path.read_bytes() == b"x"


async def test_wait_failed_raises_serialization_error(tmp_path):
    client = FakeClient(FakeArtifacts(final_status="failed"))

    with pytest.raises(NotebookLMSerializationError) as excinfo:
        await wait_then_download(
            client,
            notebook_id="nb_1",
            task_id="tk_1",
            download_method_name="download_audio",
            output_path=tmp_path / "audio.mp3",
        )

    assert excinfo.value.error_class == "wait_not_completed"


async def test_unknown_method_raises_value_error(tmp_path):
    client = FakeClient(FakeArtifacts())

    with pytest.raises(ValueError, match="download_xyz"):
        await wait_then_download(
            client,
            notebook_id="nb_1",
            task_id="tk_1",
            download_method_name="download_xyz",
            output_path=tmp_path / "audio.mp3",
        )


async def test_download_kwargs_extra_keys_passed(tmp_path):
    output_path = tmp_path / "audio.mp3"
    artifacts = FakeArtifacts()
    client = FakeClient(artifacts)

    await wait_then_download(
        client,
        notebook_id="nb_1",
        task_id="tk_1",
        download_method_name="download_audio",
        output_path=output_path,
        download_kwargs={"language": "en"},
    )

    assert artifacts.download_calls[0]["language"] == "en"


async def test_download_kwargs_forbidden_override_raises(tmp_path):
    client = FakeClient(FakeArtifacts())

    with pytest.raises(NotebookLMSerializationError) as excinfo:
        await wait_then_download(
            client,
            notebook_id="nb_1",
            task_id="tk_1",
            download_method_name="download_audio",
            output_path=tmp_path / "audio.mp3",
            download_kwargs={"notebook_id": "x"},
        )

    assert excinfo.value.error_class == "forbidden_download_kwarg_override"
