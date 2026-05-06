# API Reference

## `push_sources(session, notebook_id, sources, *, timeout_s=60) -> list[str]`

Adds URL or pasted-text sources to a NotebookLM notebook through SP-C2. Source shapes are `{"url": "https://..."}` or `{"title": "Optional", "text": "..."}`. Returns deterministic local `source_...` references suitable for ledger linkage; these are not Google internal IDs.

## `pull_briefing(session, notebook_id, *, timeout_s=120) -> str`

Returns non-empty Briefing Doc text. It raises typed exceptions on login gates, selector failures, extraction problems, or timeout. It never returns `None`.

## `pull_faq(session, notebook_id, *, timeout_s=120) -> list[dict]`

Returns FAQ items as `[{"q": str, "a": str}]`. It first reads structured DOM output and then accepts common Q/A text patterns.

## `to_source_records(notebook_id, briefing_text, run_id) -> list[dict]`

Returns strict `SourceRecord 1.0.0` dictionaries using `source_type=ai_output`, `evidence_role=source_grounding`, `used_for_purpose=source_grounding`, and a SHA-256 content hash. Full generated text is not placed in the record because the frozen schema has `additionalProperties: false` and no body field.

## Errors

All errors derive from `NotebookLMBridgeError`: `NotebookLMInputError`, `NotebookLMSessionContractError`, `NotebookLMSelectorError`, `NotebookLMLoginRequiredError`, `NotebookLMTimeoutError`, `NotebookLMUnexpectedStateError`, `NotebookLMExtractionError`, and `NotebookLMSerializationError`.
