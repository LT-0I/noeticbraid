from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import notebooklm
import pytest
from notebooklm import Note

from noeticbraid.tools.notebooklm_rpc import (
    NotebookLMNoteError,
    create_note_and_serialize,
    update_note_and_serialize,
)


pytestmark = pytest.mark.asyncio
AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
_UNSET = object()


def make_note(**overrides: Any) -> Note:
    params = {
        "id": "n_1",
        "notebook_id": "nb_1",
        "title": "X",
        "content": "...",
        "created_at": AWARE_UTC,
    }
    params.update(overrides)
    return Note(**params)


class FakeNotesAPI:
    def __init__(
        self,
        *,
        create_outcome: Note | BaseException | None = None,
        update_outcome: BaseException | None = None,
        get_outcome: Note | None | BaseException | object = _UNSET,
    ) -> None:
        self.create_outcome = create_outcome
        self.update_outcome = update_outcome
        self.get_outcome = make_note(title="Fresh") if get_outcome is _UNSET else get_outcome
        self.calls: list[dict[str, Any]] = []

    async def create(self, *args: Any, **kwargs: Any) -> Note:
        self.calls.append({"method": "create", "args": args, "kwargs": kwargs})
        if isinstance(self.create_outcome, BaseException):
            raise self.create_outcome
        if self.create_outcome is not None:
            return self.create_outcome
        return make_note(notebook_id=args[0], title=kwargs["title"], content=kwargs["content"])

    async def update(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append({"method": "update", "args": args, "kwargs": kwargs})
        if isinstance(self.update_outcome, BaseException):
            raise self.update_outcome
        return None

    async def get(self, *args: Any, **kwargs: Any) -> Note | None:
        self.calls.append({"method": "get", "args": args, "kwargs": kwargs})
        if isinstance(self.get_outcome, BaseException):
            raise self.get_outcome
        return self.get_outcome


class FakeClient:
    def __init__(self, notes: FakeNotesAPI) -> None:
        self.notes = notes


async def test_create_note_and_serialize_happy():
    note = make_note(title="Created")
    client = FakeClient(FakeNotesAPI(create_outcome=note))
    returned_note, record = await create_note_and_serialize(
        client,
        "nb_1",
        title="Created",
        content="Body",
        captured_at=AWARE_UTC,
    )

    assert returned_note is note
    assert record["source_ref_id"] == "source_notebooklm_note_n_1"
    assert record["title"] == "Created"
    assert client.notes.calls == [
        {"method": "create", "args": ("nb_1",), "kwargs": {"title": "Created", "content": "Body"}}
    ]


async def test_create_note_and_serialize_empty_notebook_id_raises():
    client = FakeClient(FakeNotesAPI())
    with pytest.raises(NotebookLMNoteError) as excinfo:
        await create_note_and_serialize(client, "", title="T", content="C", captured_at=AWARE_UTC)
    assert excinfo.value.error_class == "empty_notebook_id"
    assert client.notes.calls == []


async def test_create_note_upstream_error_propagates():
    upstream_error = notebooklm.NotebookLMError("boom")
    client = FakeClient(FakeNotesAPI(create_outcome=upstream_error))
    with pytest.raises(notebooklm.NotebookLMError) as excinfo:
        await create_note_and_serialize(client, "nb_1", title="T", content="C", captured_at=AWARE_UTC)
    assert excinfo.value is upstream_error


async def test_update_note_and_serialize_happy():
    refreshed = make_note(id="n_2", title="Refreshed", content="Updated")
    client = FakeClient(FakeNotesAPI(get_outcome=refreshed))
    returned_note, record = await update_note_and_serialize(
        client,
        "nb_1",
        "n_2",
        content="Updated",
        title="Refreshed",
        captured_at=AWARE_UTC,
    )

    assert returned_note is refreshed
    assert record["source_ref_id"] == "source_notebooklm_note_n_2"
    assert record["title"] == "Refreshed"
    assert client.notes.calls == [
        {
            "method": "update",
            "args": ("nb_1", "n_2"),
            "kwargs": {"content": "Updated", "title": "Refreshed"},
        },
        {"method": "get", "args": ("nb_1", "n_2"), "kwargs": {}},
    ]


async def test_update_note_empty_notebook_id_raises():
    client = FakeClient(FakeNotesAPI())
    with pytest.raises(NotebookLMNoteError) as excinfo:
        await update_note_and_serialize(
            client,
            "",
            "n_1",
            content="C",
            title="T",
            captured_at=AWARE_UTC,
        )
    assert excinfo.value.error_class == "empty_notebook_id"
    assert client.notes.calls == []


async def test_update_note_empty_note_id_raises():
    client = FakeClient(FakeNotesAPI())
    with pytest.raises(NotebookLMNoteError) as excinfo:
        await update_note_and_serialize(
            client,
            "nb_1",
            "",
            content="C",
            title="T",
            captured_at=AWARE_UTC,
        )
    assert excinfo.value.error_class == "empty_note_id"
    assert client.notes.calls == []


async def test_update_note_not_found_after_update_raises():
    client = FakeClient(FakeNotesAPI(get_outcome=None))
    with pytest.raises(NotebookLMNoteError) as excinfo:
        await update_note_and_serialize(
            client,
            "nb_1",
            "n_404",
            content="C",
            title="T",
            captured_at=AWARE_UTC,
        )
    assert excinfo.value.error_class == "note_not_found"
    assert client.notes.calls == [
        {"method": "update", "args": ("nb_1", "n_404"), "kwargs": {"content": "C", "title": "T"}},
        {"method": "get", "args": ("nb_1", "n_404"), "kwargs": {}},
    ]


async def test_update_note_upstream_error_propagates():
    upstream_error = notebooklm.NotebookLMError("boom")
    client = FakeClient(FakeNotesAPI(update_outcome=upstream_error))
    with pytest.raises(notebooklm.NotebookLMError) as excinfo:
        await update_note_and_serialize(
            client,
            "nb_1",
            "n_1",
            content="C",
            title="T",
            captured_at=AWARE_UTC,
        )
    assert excinfo.value is upstream_error
    assert len(client.notes.calls) == 1
