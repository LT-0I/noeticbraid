from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import notebooklm
import pytest
from notebooklm import AskResult, Note

from noeticbraid.tools.notebooklm_rpc import NotebookLMChatError, ask_and_save_as_note


pytestmark = pytest.mark.asyncio
AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


def make_ask_result(**overrides: Any) -> AskResult:
    params = {
        "answer": "A",
        "conversation_id": "conv_1",
        "turn_number": 1,
        "is_follow_up": False,
    }
    params.update(overrides)
    return AskResult(**params)


def make_note(**overrides: Any) -> Note:
    params = {
        "id": "n_1",
        "notebook_id": "nb_1",
        "title": "Saved",
        "content": "A",
        "created_at": AWARE_UTC,
    }
    params.update(overrides)
    return Note(**params)


class FakeChatAPI:
    def __init__(self, outcome: AskResult | BaseException | None = None) -> None:
        self.outcome = outcome if outcome is not None else make_ask_result()
        self.calls: list[dict[str, Any]] = []

    async def ask(self, *args: Any, **kwargs: Any) -> AskResult:
        self.calls.append({"method": "ask", "args": args, "kwargs": kwargs})
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeNotesAPI:
    def __init__(self, outcome: Note | BaseException | None = None) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def create(self, *args: Any, **kwargs: Any) -> Note:
        self.calls.append({"method": "create", "args": args, "kwargs": kwargs})
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        if self.outcome is not None:
            return self.outcome
        return make_note(notebook_id=args[0], title=kwargs["title"], content=kwargs["content"])


class FakeClient:
    def __init__(self, chat: FakeChatAPI | None = None, notes: FakeNotesAPI | None = None) -> None:
        self.chat = chat or FakeChatAPI()
        self.notes = notes or FakeNotesAPI()


async def test_ask_and_save_as_note_happy():
    ask_result = make_ask_result(answer="Answer")
    client = FakeClient(chat=FakeChatAPI(ask_result))
    returned_ask_result, note, record = await ask_and_save_as_note(
        client,
        "nb_1",
        question="What is X?",
        captured_at=AWARE_UTC,
        source_ids=["src_1"],
        conversation_id="conv_0",
    )

    assert returned_ask_result is ask_result
    assert note.content == "Answer"
    assert record["source_ref_id"] == "source_notebooklm_note_n_1"
    assert client.chat.calls == [
        {
            "method": "ask",
            "args": ("nb_1", "What is X?"),
            "kwargs": {"source_ids": ["src_1"], "conversation_id": "conv_0"},
        }
    ]
    assert client.notes.calls[0]["kwargs"]["content"] == "Answer"


async def test_ask_and_save_uses_save_as_title_override():
    client = FakeClient()
    await ask_and_save_as_note(
        client,
        "nb_1",
        question="What is X?",
        captured_at=AWARE_UTC,
        save_as_title="Topic X",
    )
    assert client.notes.calls[0]["kwargs"]["title"] == "Topic X"


async def test_ask_and_save_default_title_from_question():
    client = FakeClient()
    await ask_and_save_as_note(client, "nb_1", question="What is X?", captured_at=AWARE_UTC)
    assert client.notes.calls[0]["kwargs"]["title"] == "Chat: What is X?"


async def test_ask_and_save_long_question_title_truncated_80_slice():
    client = FakeClient()
    await ask_and_save_as_note(client, "nb_1", question="x" * 200, captured_at=AWARE_UTC)
    title = client.notes.calls[0]["kwargs"]["title"]
    assert title == "Chat: " + "x" * 80
    assert len(title) == 86


async def test_ask_and_save_empty_notebook_id_raises():
    client = FakeClient()
    with pytest.raises(NotebookLMChatError) as excinfo:
        await ask_and_save_as_note(client, "", question="Q", captured_at=AWARE_UTC)
    assert excinfo.value.error_class == "empty_notebook_id"
    assert client.chat.calls == []
    assert client.notes.calls == []


async def test_ask_and_save_empty_question_raises():
    client = FakeClient()
    with pytest.raises(NotebookLMChatError) as excinfo:
        await ask_and_save_as_note(client, "nb_1", question="", captured_at=AWARE_UTC)
    assert excinfo.value.error_class == "empty_question"
    assert client.chat.calls == []
    assert client.notes.calls == []


async def test_ask_and_save_empty_answer_raises():
    client = FakeClient(chat=FakeChatAPI(make_ask_result(answer="")))
    with pytest.raises(NotebookLMChatError) as excinfo:
        await ask_and_save_as_note(client, "nb_1", question="Q", captured_at=AWARE_UTC)
    assert excinfo.value.error_class == "empty_ask_answer"
    assert client.notes.calls == []


async def test_ask_and_save_upstream_chat_error_propagates():
    upstream_error = notebooklm.ChatError("boom")
    client = FakeClient(chat=FakeChatAPI(upstream_error))
    with pytest.raises(notebooklm.ChatError) as excinfo:
        await ask_and_save_as_note(client, "nb_1", question="Q", captured_at=AWARE_UTC)
    assert excinfo.value is upstream_error
    assert client.notes.calls == []


async def test_ask_and_save_upstream_notes_error_propagates():
    upstream_error = notebooklm.NotebookLMError("boom")
    client = FakeClient(notes=FakeNotesAPI(upstream_error))
    with pytest.raises(notebooklm.NotebookLMError) as excinfo:
        await ask_and_save_as_note(client, "nb_1", question="Q", captured_at=AWARE_UTC)
    assert excinfo.value is upstream_error
    assert len(client.chat.calls) == 1
