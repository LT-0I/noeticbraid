from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import notebooklm
import pytest
from notebooklm import Source, SourceStatus

from noeticbraid.tools.notebooklm_rpc import (
    NotebookLMSourceError,
    add_drive_and_serialize,
    add_file_and_serialize,
    add_text_and_serialize,
    add_url_and_serialize,
)


AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


class FakeSourcesAPI:
    def __init__(self, source: Source | BaseException | None = None) -> None:
        self.source = source or Source(
            id="src_1",
            title="X",
            url="",
            _type_code=3,
            created_at=AWARE_UTC,
            status=SourceStatus.READY,
        )
        self.calls: list[dict[str, Any]] = []

    async def _return_or_raise(self, method: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Source:
        self.calls.append({"method": method, "args": args, "kwargs": kwargs})
        if isinstance(self.source, BaseException):
            raise self.source
        return self.source

    async def add_file(self, *args: Any, **kwargs: Any) -> Source:
        return await self._return_or_raise("add_file", args, kwargs)

    async def add_url(self, *args: Any, **kwargs: Any) -> Source:
        return await self._return_or_raise("add_url", args, kwargs)

    async def add_drive(self, *args: Any, **kwargs: Any) -> Source:
        return await self._return_or_raise("add_drive", args, kwargs)

    async def add_text(self, *args: Any, **kwargs: Any) -> Source:
        return await self._return_or_raise("add_text", args, kwargs)


class FakeClient:
    def __init__(self, source: Source | BaseException | None = None) -> None:
        self.sources = FakeSourcesAPI(source)


HELPER_CASES = [
    (
        "file",
        add_file_and_serialize,
        ("nb_1", "source.pdf"),
        {"captured_at": AWARE_UTC},
        "add_file",
    ),
    (
        "url",
        add_url_and_serialize,
        ("nb_1", "https://example.com"),
        {"captured_at": AWARE_UTC},
        "add_url",
    ),
    (
        "drive",
        add_drive_and_serialize,
        ("nb_1", "drive_file_1", "Drive Title"),
        {"captured_at": AWARE_UTC},
        "add_drive",
    ),
    (
        "text",
        add_text_and_serialize,
        ("nb_1", "Text Title", "content"),
        {"captured_at": AWARE_UTC},
        "add_text",
    ),
]


def source_for_kind(kind: str, *, status: SourceStatus = SourceStatus.READY) -> Source:
    if kind == "url":
        return Source(
            id="src_1",
            title="Example",
            url="https://example.com",
            _type_code=5,
            created_at=AWARE_UTC,
            status=status,
        )
    if kind == "drive":
        return Source(
            id="src_1",
            title="Drive Title",
            url="",
            _type_code=1,
            created_at=AWARE_UTC,
            status=status,
        )
    if kind == "text":
        return Source(
            id="src_1",
            title="Text Title",
            url="",
            _type_code=4,
            created_at=AWARE_UTC,
            status=status,
        )
    return Source(
        id="src_1",
        title="X",
        url="",
        _type_code=3,
        created_at=AWARE_UTC,
        status=status,
    )


@pytest.mark.parametrize(("kind", "helper", "args", "kwargs", "method"), HELPER_CASES)
async def test_add_and_serialize_happy_returns_source_and_dict(kind, helper, args, kwargs, method):
    source = source_for_kind(kind)
    client = FakeClient(source)
    returned_source, record = await helper(client, *args, **kwargs)

    assert returned_source is source
    assert record["nb_type"] == "source_record"
    assert record["source_ref_id"] == "source_notebooklm_source_src_1"
    assert client.sources.calls[0]["method"] == method
    assert client.sources.calls[0]["kwargs"]["wait"] is True


async def test_add_file_omits_mime_type_when_none():
    client = FakeClient()
    await add_file_and_serialize(client, "nb_1", "source.pdf", captured_at=AWARE_UTC, mime_type=None)
    assert "mime_type" not in client.sources.calls[0]["kwargs"]


async def test_add_file_passes_mime_type_when_provided():
    client = FakeClient()
    await add_file_and_serialize(
        client,
        "nb_1",
        Path("source.pdf"),
        captured_at=AWARE_UTC,
        mime_type="application/pdf",
    )
    assert client.sources.calls[0]["kwargs"]["mime_type"] == "application/pdf"


async def test_not_ready_status_raises_source_not_ready():
    client = FakeClient(source_for_kind("file", status=SourceStatus.PROCESSING))
    with pytest.raises(NotebookLMSourceError) as excinfo:
        await add_file_and_serialize(client, "nb_1", "source.pdf", captured_at=AWARE_UTC)
    assert excinfo.value.error_class == "source_not_ready"


async def test_upstream_error_propagates():
    upstream_error = notebooklm.NotebookLMError("boom")
    client = FakeClient(upstream_error)
    with pytest.raises(notebooklm.NotebookLMError) as excinfo:
        await add_url_and_serialize(client, "nb_1", "https://example.com", captured_at=AWARE_UTC)
    assert excinfo.value is upstream_error


@pytest.mark.parametrize(("kind", "helper", "args", "kwargs", "method"), HELPER_CASES)
async def test_passes_wait_true_to_upstream(kind, helper, args, kwargs, method):
    client = FakeClient(source_for_kind(kind))
    await helper(client, *args, **kwargs)
    assert client.sources.calls[0]["method"] == method
    assert client.sources.calls[0]["kwargs"]["wait"] is True
