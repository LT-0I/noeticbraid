# NoeticBraid

**Tagline:** Make AI sharper. Make the user clearer.  
**中文:** 让 AI 越用越准，让人越用越清醒。

This repository is a **Stage 0 draft package** for Round 1 / Phase 1.1 Foundation Lock. It is not an implementation release.

## Stage 0 status

- `contract_version`: `0.1.0`
- `status`: `DRAFT / non-authoritative`
- generated_at: `2026-04-28T09:03:53Z`
- contract owner: local main Claude session

## What this package contains

This package provides the Phase 1.1 Stage 0 repository skeleton, architecture documents, decision records, draft contracts, non-binding fixtures, reuse candidates, gate scripts, and exactly one full task card: `TASK-1.1.4_schema.md`.

It intentionally does **not** include business implementation code for schema logic, ledger append, guards, browser workers, Console pages, or Obsidian writing. Those start in later steps.

## Authority rule

GPT-5.5 Pro Web may generate Stage 0 draft project artifacts. It must not freeze contracts. The local main Claude session owns contract freezing after TASK-1.1.4 implementation and local double review.

## Repository shape

The physical layout follows the user-approved open monorepo + private separated directories strategy:

- open workspace packages live under `packages/`;
- private data/config placeholders live under `private/` and must not be committed;
- legacy code is stored under `legacy/helixmind_phase1/` and treated as read-only;
- workflow orchestration artifacts are not produced here except where explicitly allowed.

## Phase 1.1 principle

Foundation Lock means: establish the skeleton, guardrails, draft contracts, run-evidence vocabulary, and review boundaries before any heavy feature implementation.
