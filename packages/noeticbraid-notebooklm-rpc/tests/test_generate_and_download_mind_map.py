from __future__ import annotations

from pathlib import Path

import pytest

from noeticbraid.tools.notebooklm_rpc import (
    NotebookLMSerializationError,
    generate_and_download_mind_map,
)


class FakeArtifacts:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def generate_mind_map(self, notebook_id, **kwargs):
        self.calls.append(("generate_mind_map", notebook_id, kwargs))
        assert all(value is not None for value in kwargs.values())
        return self.result

    async def download_mind_map(self, notebook_id, output_path, *, artifact_id):
        self.calls.append(("download_mind_map", notebook_id, output_path, artifact_id))
        path = Path(output_path)
        path.write_bytes(b"x")
        return str(path)

    async def wait_for_completion(self, *args, **kwargs):
        raise AssertionError("mind_map must not call wait_for_completion")


class FakeClient:
    def __init__(self, result):
        self.artifacts = FakeArtifacts(result)


async def test_happy_dict_path(tmp_path):
    output_path = tmp_path / "mind-map.json"
    client = FakeClient({"mind_map": {"root": "x"}, "note_id": "nt_42"})

    note_id, path = await generate_and_download_mind_map(client, "nb_1", output_path)

    assert note_id == "nt_42"
    assert path == output_path
    assert [call[0] for call in client.artifacts.calls] == ["generate_mind_map", "download_mind_map"]


async def test_passes_note_id_as_artifact_id(tmp_path):
    client = FakeClient({"mind_map": {"root": "x"}, "note_id": "nt_42"})

    await generate_and_download_mind_map(client, "nb_1", tmp_path / "mind-map.json")

    assert client.artifacts.calls[1][3] == "nt_42"


async def test_non_dict_return_raises_shape_mismatch(tmp_path):
    client = FakeClient(42)

    with pytest.raises(NotebookLMSerializationError) as excinfo:
        await generate_and_download_mind_map(client, "nb_1", tmp_path / "mind-map.json")

    assert excinfo.value.error_class == "upstream_mind_map_shape_mismatch"


async def test_missing_note_id_key_raises_shape_mismatch(tmp_path):
    client = FakeClient({"mind_map": {}})

    with pytest.raises(NotebookLMSerializationError) as excinfo:
        await generate_and_download_mind_map(client, "nb_1", tmp_path / "mind-map.json")

    assert excinfo.value.error_class == "upstream_mind_map_shape_mismatch"


async def test_null_note_id_raises_no_note_id(tmp_path):
    client = FakeClient({"mind_map": {}, "note_id": None})

    with pytest.raises(NotebookLMSerializationError) as excinfo:
        await generate_and_download_mind_map(client, "nb_1", tmp_path / "mind-map.json")

    assert excinfo.value.error_class == "mind_map_no_note_id"


async def test_empty_note_id_raises_no_note_id(tmp_path):
    client = FakeClient({"mind_map": {}, "note_id": ""})

    with pytest.raises(NotebookLMSerializationError) as excinfo:
        await generate_and_download_mind_map(client, "nb_1", tmp_path / "mind-map.json")

    assert excinfo.value.error_class == "mind_map_no_note_id"
