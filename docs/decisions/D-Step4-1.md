# Repo Strategy

- status: user-approved decision
- decided_at: 2026-04-28
- source: Round 1 Step 4 user decisions


## Candidate Set

The candidate set was narrowed during Step 4 review. This Stage 0 record does not repeat the full comparison table; it records the final user decision and its implementation consequences.

## User Selected

C. Open monorepo plus private separated repository or uncommitted private directories

## Rationale

A pure polyrepo would make Phase 1.1 too expensive for a single developer: schema contracts, runtime adapters, Console mocks, scripts, and tests would need synchronization across separate repositories before the control plane even exists. A pure public monorepo would be unsafe because browser profiles, selector experiments, paid database scripts, account routing preferences, and private workflow cards must not be published. The selected hybrid keeps the open core inspectable and easy to test while preserving a hard private boundary. The physical Stage 0 layout maps Step 3's conceptual package names into `packages/` for open code and `private/` for unpublished state. This makes local review simpler: Codex and Claude can reason over one open workspace, while the user can keep sensitive automation out of Git entirely.

## Implementation Consequence

This decision is treated as an input to Phase 1.1 Stage 0 and later task cards. It does not freeze contracts by itself, but it constrains package layout, documentation, placeholders, gate scripts, and the first implementation target.

## Re-evaluation Trigger

Reevaluate if the private automation side grows into a product of its own, if package releases become blocked by the monorepo, or if multiple external contributors require independent release cadence for core, Console, Obsidian, or runtime packages.

## Stage 0 Handling

Stage 0 records this decision but does not over-implement it. The decision constrains repository layout, documentation language, placeholders, and future task cards. Any later implementation that needs to go beyond this decision must be raised in local review rather than silently changing the architecture.

## Audit Note

This file intentionally contains only the selected option, rationale, implementation consequence, and re-evaluation trigger. It does not include self-critique, reflection excerpts, or unrelated workflow lessons. That keeps decision records clean for later gate checks.
