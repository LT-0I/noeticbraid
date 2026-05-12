# NoeticBraid

**Tagline:** Make AI sharper. Make the user clearer.  
**中文:** 让 AI 越用越准，让人越用越清醒。

This repository is the main NoeticBraid monorepo. As of 2026-05-11, the authoritative project definition is `../PROJECT_DEFINITION_v3.2.md`; older HelixMind / Stage 0 wording is historical only.

## Current status snapshot

- Backend API `contract_version`: `1.2.0`
- Backend frozen routes: 8 (`FROZEN_ROUTE_SPECS`)
- Backend schema names: 17 (`ALL_SCHEMA_NAMES`)
- Latest contract tag present: `phase-1.2-contract-1.3.0` (Obsidian sidecar/schema freeze; backend API version remains `1.2.0`)
- Detailed status matrix: `PROJECT_STATUS.md`

## What this package contains

The workspace contains the current NoeticBraid packages under `packages/`, including core schemas/ledger/guards, backend routes, console scaffolding, runtime, multimodel alliance, Obsidian integration, NotebookLM bridge, and workflow scheduler packages.

## Authority rule

Spec-driven development is mandatory: implementation must stay within the active project definition and approved specs. `PROJECT_DEFINITION_v3.2.md` is the current source of truth when it conflicts with older blueprints or README history.

## Repository shape

The physical layout follows the user-approved open monorepo + private separated directories strategy:

- open workspace packages live under `packages/`;
- private data/config placeholders live under `private/` and must not be committed;
- legacy code is stored under `legacy/` or external archive paths and treated as read-only;
- workflow orchestration artifacts are produced outside this repo unless explicitly allowed.
