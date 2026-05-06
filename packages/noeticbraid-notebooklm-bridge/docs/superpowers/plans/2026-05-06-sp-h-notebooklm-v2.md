# SP-H NotebookLM Bridge v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a contract-aligned SP-H NotebookLM Bridge v2 package from the existing zip while preserving the original archive.

**Architecture:** Public API delegates to a C2-compatible UI operation layer, selector store, strict SourceRecord serializer, and strict RunRecord event adapter. Runtime dependencies remain standard-library only.

**Tech Stack:** Python 3.10+, pytest, setuptools, NoeticBraid frozen OpenAPI YAML used only for verification.

---

### Task 1: Contract and C2 failing tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_contract_alignment.py`
- Create: `tests/test_browser_ops_c2_session.py`

- [ ] Write tests that assert `to_source_records()` returns only frozen SourceRecord properties and includes all required fields.
- [ ] Write tests that a current C2-shaped fake session (`navigate`, `eval`, `click(x,y)`, `type_text(text)`) works with `push_sources()`.
- [ ] Run targeted tests and confirm they fail against the old zip implementation because it emits local SourceRecord shape and expects `wait_for/evaluate`.

### Task 2: Core modules

**Files:**
- Create/modify: `noeticbraid/tools/notebooklm_bridge/__init__.py`
- Create/modify: `_errors.py`, `_protocols.py`, `_types.py`, `_selectors.py`, `_browser_ops.py`, `_serializer.py`, `_runlog.py`, `selectors.json`, `py.typed`

- [ ] Implement current C2-compatible protocol.
- [ ] Implement scoped selector store and DOM scripts that resolve selectors to coordinates/text through `session.eval`.
- [ ] Implement `push_sources`, `pull_briefing`, `pull_faq` using `click(x,y)` and `type_text(text)` only.
- [ ] Implement strict SourceRecord serializer.
- [ ] Implement strict RunRecord event adapter using existing event enum values.

### Task 3: Docs and package metadata

**Files:**
- Create/modify: `pyproject.toml`, `README.md`
- Create: `docs/REFERENCE_RESEARCH.md`, `docs/ARCHITECTURE.md`, `docs/API_REFERENCE.md`, `docs/C2_BROWSERSESSION_CONTRACT.md`, `docs/SELECTOR_MAINTENANCE.md`, `docs/RUNRECORD_INTEGRATION.md`, `docs/SECURITY_AND_COMPLIANCE.md`, `docs/TROUBLESHOOTING.md`, `docs/ROADMAP.md`, `docs/VERIFICATION.md`

- [ ] Document reference-project influence and rejected ideas.
- [ ] Document C2 boundary, selector maintenance, strict contract output, and safety red lines.
- [ ] Keep original `BLUEPRINT.md` and `REVIEW.md` intact.

### Task 4: Verification and packaging

**Files:**
- Create: `noeticbraid-sp-h-notebooklm-bridge-v2.zip`

- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m compileall noeticbraid`.
- [ ] Run strict SourceRecord/RunRecord verification script against main repo `phase1_2_openapi.yaml`.
- [ ] Run red-line scan for forbidden runtime dependencies.
- [ ] Package v2 zip without overwriting `noeticbraid-sp-h-notebooklm-bridge.zip`.
