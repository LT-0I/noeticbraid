# SP-H NotebookLM Bridge v2 Design

Date: 2026-05-06

## Goal

Build a NoeticBraid SP-H NotebookLM Bridge package from the existing zip while preserving the original SP-H blueprint/review documents and aligning the implementation with the main NoeticBraid frozen contracts and current SP-C2 runtime boundary.

## Scope

SP-H is a small Python library under `noeticbraid/tools/notebooklm_bridge/`. It accepts source URL/text dictionaries, drives a caller-supplied SP-C2-like browser session, pulls generated NotebookLM Briefing Doc/FAQ text, emits contract-compatible records/events, and documents how to maintain selectors and integrate with SP-A/SP-G/SP-B/SP-C2. It does not own browser lifecycle, auth, Chrome profiles, cookies, NotebookLM internal RPCs, MCP server runtime, decision algorithms, or RAG infrastructure.

## Architecture

The package keeps four boundaries separate:

1. Public API (`__init__.py`) exposes stable blueprint functions: `push_sources`, `pull_briefing`, `pull_faq`, `to_source_records`.
2. Browser boundary (`_protocols.py`, `_browser_ops.py`) consumes the current C2-style session: `navigate(url)`, `eval(expression)`, `click(x, y)`, `type_text(text)`. Selector targets are resolved by DOM scripts into coordinates inside SP-H without requiring SP-C2 to support selector strings.
3. Contract boundary (`_serializer.py`, `_runlog.py`) emits strict shapes compatible with `SourceRecord 1.0.0` and `RunRecord 1.0.0` from `phase1_2_openapi.yaml` without modifying frozen contracts.
4. Selector boundary (`_selectors.py`, `selectors.json`) uses a scope/key JSON shape compatible with C2 SelectorStore (`notebooklm.add_source_button`, etc.) and supports reloading from explicit paths for future hot updates.

## Reference-project influence

- `PleasePrompto/notebooklm-mcp`: adopt source ingestion, provenance/citation awareness, browser-session separation, and tool taxonomy; reject MCP server ownership, Patchright, stealth, persistent profile/auth handling.
- `PleasePrompto/notebooklm-skill`: adopt local package ergonomics, operator docs, and troubleshooting patterns; reject venv/bootstrap, cookie/browser-state management, and human-like evasion claims.
- `MODSetter/SurfSense`: adopt source-governance, privacy-first, grounded-output framing; reject RAG platform, connector hub, vector database, desktop app, and team collaboration scope.
- `teng-lin/notebooklm-py`: adopt Python API modularity, source/artifact taxonomy, tests, and docs; reject undocumented Google RPC/API as production path and broad artifact download coverage.

## Data flow

`push_sources` validates notebook ID and sources, navigates to NotebookLM, checks login gate, opens Add Source, selects URL/text source mode, types content, submits, waits for readiness, and returns deterministic `source_...` references. `pull_briefing` and `pull_faq` navigate, check login gate, trigger/read generated content, and return typed text/list outputs. `to_source_records` converts generated text into one strict SourceRecord dictionary using `source_type=ai_output`, `evidence_role=source_grounding`, and `used_for_purpose=source_grounding`.

## Error handling

All public failures use typed exceptions. Login/MFA/CAPTCHA/terms gates raise `NotebookLMLoginRequiredError` with manual-action instructions. Missing session methods raise `NotebookLMSessionContractError`. Missing selectors raise `NotebookLMSelectorError`. Timeouts raise `NotebookLMTimeoutError`. DOM extraction failures raise `NotebookLMExtractionError`. No error path suggests bypassing Google controls.

## Testing

Tests must run without Google or NotebookLM access. Fake C2 sessions implement the current C2 protocol, record calls, and simulate DOM/eval results. Tests cover public imports, source validation, C2 compatibility, selector loading, browser operation sequencing, SourceRecord strict shape, RunRecord strict shape, redaction, and README/docs presence. Verification also runs compileall and a red-line scan.
