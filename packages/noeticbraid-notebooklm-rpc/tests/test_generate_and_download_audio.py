from __future__ import annotations

from pathlib import Path

import notebooklm

from noeticbraid.tools.notebooklm_rpc import generate_and_download_audio


class FakeArtifacts:
    def __init__(self):
        self.calls = []
        self.status = notebooklm.GenerationStatus(task_id="tk_a", status="running")

    async def generate_audio(self, notebook_id, **kwargs):
        self.calls.append(("generate_audio", notebook_id, kwargs))
        assert all(value is not None for value in kwargs.values())
        return self.status

    async def wait_for_completion(self, notebook_id, task_id, *, timeout, poll_interval):
        self.calls.append(("wait_for_completion", notebook_id, task_id, timeout, poll_interval))
        return notebooklm.GenerationStatus(task_id=task_id, status="completed")

    async def download_audio(self, **kwargs):
        self.calls.append(("download_audio", kwargs))
        path = Path(kwargs["output_path"])
        path.write_bytes(b"x")
        return str(path)

    async def download_video(self, **kwargs):
        raise AssertionError("download_video must not be called for audio")

    async def download_report(self, **kwargs):
        raise AssertionError("download_report must not be called for audio")


class FakeClient:
    def __init__(self):
        self.artifacts = FakeArtifacts()


async def test_happy_three_step(tmp_path):
    output_path = tmp_path / "audio.mp3"
    client = FakeClient()

    status, path = await generate_and_download_audio(client, "nb_1", output_path)

    assert status is client.artifacts.status
    assert path == output_path
    assert [call[0] for call in client.artifacts.calls] == [
        "generate_audio",
        "wait_for_completion",
        "download_audio",
    ]


async def test_uses_correct_download_method(tmp_path):
    client = FakeClient()
    await generate_and_download_audio(client, "nb_1", tmp_path / "audio.mp3")

    assert any(call[0] == "download_audio" for call in client.artifacts.calls)


async def test_passes_task_id_as_artifact_id(tmp_path):
    client = FakeClient()
    await generate_and_download_audio(client, "nb_1", tmp_path / "audio.mp3")

    download_call = [call for call in client.artifacts.calls if call[0] == "download_audio"][0]
    assert download_call[1]["artifact_id"] == "tk_a"


async def test_idempotency_warning_in_docstring():
    assert "idempot" in generate_and_download_audio.__doc__.lower()
