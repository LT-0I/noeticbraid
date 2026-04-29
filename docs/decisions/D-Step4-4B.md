# Console Authentication

- status: user-approved decision
- decided_at: 2026-04-28
- source: Round 1 Step 4 user decisions


## Candidate Set

The candidate set was narrowed during Step 4 review. This Stage 0 record does not repeat the full comparison table; it records the final user decision and its implementation consequences.

## User Selected

A. 127.0.0.1 plus startup token

## Rationale

The Console is privileged: it can approve tasks, display account state, inspect ledger evidence, and eventually trigger browser and CLI actions. Phase 1 does not need public access, so the simplest safe choice is to bind to localhost and require a startup token. This avoids prematurely building OAuth, remote sessions, device pairing, or Tailscale ACL logic. It also keeps the Console usable during local development and review. The token is not a long-term identity system; it is a local startup guard for Phase 1.

## Implementation Consequence

This decision is treated as an input to Phase 1.1 Stage 0 and later task cards. It does not freeze contracts by itself, but it constrains package layout, documentation, placeholders, gate scripts, and the first implementation target.

## Re-evaluation Trigger

Reevaluate before any public, LAN, Tailscale, Cloudflare Tunnel, or mobile remote access is enabled. Remote access should require a new threat model and likely stronger device/session controls.

## Stage 0 Handling

Stage 0 records this decision but does not over-implement it. The decision constrains repository layout, documentation language, placeholders, and future task cards. Any later implementation that needs to go beyond this decision must be raised in local review rather than silently changing the architecture.

## Audit Note

This file intentionally contains only the selected option, rationale, implementation consequence, and re-evaluation trigger. It does not include self-critique, reflection excerpts, or unrelated workflow lessons. That keeps decision records clean for later gate checks.
