# Primary Web AI

- status: user-approved decision
- decided_at: 2026-04-28
- source: Round 1 Step 4 user decisions


## Candidate Set

The candidate set was narrowed during Step 4 review. This Stage 0 record does not repeat the full comparison table; it records the final user decision and its implementation consequences.

## User Selected

A. ChatGPT

## Rationale

The primary Web AI target is ChatGPT because the user has multiple ChatGPT accounts and Phase 1 needs to exercise the real multi-account premise. Selecting ChatGPT first makes profile health, account hints, selector work, quota events, and run evidence useful earlier than a Claude-first path would. The selector ecosystem and community examples around ChatGPT Web are broad, and the user can tolerate account/profile experimentation better because the resource pool is larger. Claude remains useful later, but the user has only one Claude account, so it is not the best first target for profile-pool validation.

## Implementation Consequence

This decision is treated as an input to Phase 1.1 Stage 0 and later task cards. It does not freeze contracts by itself, but it constrains package layout, documentation, placeholders, gate scripts, and the first implementation target.

## Re-evaluation Trigger

Reevaluate if ChatGPT Web selectors become too unstable, if account friction blocks the Web AI Worker, or if Claude/Gemini become necessary for the first Project Conversation Workspace loop.

## Stage 0 Handling

Stage 0 records this decision but does not over-implement it. The decision constrains repository layout, documentation language, placeholders, and future task cards. Any later implementation that needs to go beyond this decision must be raised in local review rather than silently changing the architecture.

## Audit Note

This file intentionally contains only the selected option, rationale, implementation consequence, and re-evaluation trigger. It does not include self-critique, reflection excerpts, or unrelated workflow lessons. That keeps decision records clean for later gate checks.
