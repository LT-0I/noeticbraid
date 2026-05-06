# Reference Research

SP-H v2 was shaped by four reference projects. The package borrows architectural lessons, not source code.

## PleasePrompto/notebooklm-mcp

The MCP server shows a mature tool taxonomy around asking questions, adding URL/text sources, sessions, library metadata, citation extraction, provenance envelopes, and health/auth tools. SP-H adopts the separation between source ingestion, generated artifacts, session identity, provenance, and operator health. SP-H rejects the server shape, MCP transports, Patchright dependency, stealth/fingerprint features, multi-account profiles, stored browser state, auth setup, and cleanup tools because those belong outside SP-H.

## PleasePrompto/notebooklm-skill

The skill demonstrates local developer ergonomics, operator-first docs, authentication troubleshooting, a notebook library, and a simple script-based interface for agents. SP-H adopts documentation depth, local-first safety guidance, and clear manual-action instructions. SP-H rejects isolated venv/bootstrap management, Chrome install, persistent auth files, cookies, browser_state storage, and human-like automation claims.

## MODSetter/SurfSense

SurfSense frames NotebookLM-like workflows as source governance, grounded answers, privacy, connectors, reports, podcasts, and team collaboration. SP-H adopts the privacy-first and source-management framing: every generated output must be attributable and safe to pass downstream. SP-H rejects the broader platform: no RAG stack, vector DB, connector hub, FastAPI service, Docker deployment, desktop app, browser extension, team collaboration, or alternative LLM runtime.

## teng-lin/notebooklm-py

The Python API/CLI shows clean source/artifact taxonomy, broad generated artifact coverage, typed APIs, CLI examples, tests, and agent packaging. SP-H adopts small Python modules, explicit public API functions, fake-session tests, and artifact/source vocabulary. SP-H rejects undocumented Google internal RPC/API calls, cookie helpers, browser login helpers, CLI command surface, and broad download/generation coverage.

## Final SP-H decisions

- Library package, not MCP server or CLI.
- Current SP-C2 dependency injection, not browser ownership.
- UI automation path only through user-authorized visible NotebookLM session.
- Strict frozen `SourceRecord` and `RunRecord` shapes.
- Scoped selectors as the hot-update boundary.
- No runtime dependencies beyond the Python standard library.
