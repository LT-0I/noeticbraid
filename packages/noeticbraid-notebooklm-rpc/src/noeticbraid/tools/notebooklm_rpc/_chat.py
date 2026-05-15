from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import notebooklm
from notebooklm import AskResult, Note

from ._errors import NotebookLMChatError
from ._notes import note_to_source_record


async def ask_and_save_as_note(
    client: notebooklm.NotebookLMClient,
    notebook_id: str,
    *,
    question: str,
    captured_at: datetime,
    source_ids: Optional[list[str]] = None,
    conversation_id: Optional[str] = None,
    save_as_title: Optional[str] = None,
    title_override: Optional[str] = None,
    local_path: Optional[Path] = None,
    content_hash: Optional[str] = None,
    retrieved_by_run_id: Optional[str] = None,
) -> tuple[AskResult, Note, dict[str, Any]]:
    """Composite: chat.ask + notes.create(content=answer) + serialize -> 3-tuple."""
    if not notebook_id:
        raise NotebookLMChatError(
            error_class="empty_notebook_id",
            detail="notebook_id must not be empty",
        )
    if not question:
        raise NotebookLMChatError(
            error_class="empty_question",
            detail="question must not be empty",
        )

    ask_result = await client.chat.ask(
        notebook_id,
        question,
        source_ids=source_ids,
        conversation_id=conversation_id,
    )
    if not ask_result.answer:
        raise NotebookLMChatError(
            error_class="empty_ask_answer",
            detail="ask_result.answer must not be empty",
        )

    effective_title = save_as_title or f"Chat: {question[:80]}"
    note = await client.notes.create(notebook_id, title=effective_title, content=ask_result.answer)
    record = note_to_source_record(
        note,
        captured_at=captured_at,
        title_override=title_override,
        local_path=local_path,
        content_hash=content_hash,
        retrieved_by_run_id=retrieved_by_run_id,
    )
    return ask_result, note, record
