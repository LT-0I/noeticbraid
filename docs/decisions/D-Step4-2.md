# Domain Strategy

- status: user-approved decision
- decided_at: 2026-04-28
- source: Round 1 Step 4 user decisions


## Candidate Set

The candidate set was narrowed during Step 4 review. This Stage 0 record does not repeat the full comparison table; it records the final user decision and its implementation consequences.

## User Selected

C. Do not expose publicly in Phase 1

## Rationale

Phase 1 is about making the local execution substrate reliable. A public endpoint would force premature decisions about TLS, reverse proxy, DNS, remote authentication, CSRF, rate limiting, mobile access, and browser-profile safety. The Console is a privileged control surface that can trigger browser automation, approvals, file writes, subprocess execution, and emergency stop. Until ModeEnforcer, startup-token auth, and the Approval Queue are proven locally, public exposure would create risk without delivering Phase 1 value. The existing domain `jungerpf.top` remains available for later documentation or a project page, but Phase 1 should bind to `127.0.0.1` and use a startup token.

## Implementation Consequence

This decision is treated as an input to Phase 1.1 Stage 0 and later task cards. It does not freeze contracts by itself, but it constrains package layout, documentation, placeholders, gate scripts, and the first implementation target.

## Re-evaluation Trigger

Reevaluate after the local Console, guard layer, and IM bridge are stable, or if mobile remote control becomes a blocking requirement. Possible future strategies remain: `noeticbraid.jungerpf.top`, `jungerpf.top/noeticbraid`, or still no public project site.

## Stage 0 Handling

Stage 0 records this decision but does not over-implement it. The decision constrains repository layout, documentation language, placeholders, and future task cards. Any later implementation that needs to go beyond this decision must be raised in local review rather than silently changing the architecture.

## Audit Note

This file intentionally contains only the selected option, rationale, implementation consequence, and re-evaluation trigger. It does not include self-critique, reflection excerpts, or unrelated workflow lessons. That keeps decision records clean for later gate checks.
