# Browser Profile Strategy

- status: user-approved decision
- decided_at: 2026-04-28
- source: Round 1 Step 4 user decisions


## Candidate Set

The candidate set was narrowed during Step 4 review. This Stage 0 record does not repeat the full comparison table; it records the final user decision and its implementation consequences.

## User Selected

A. Playwright Persistent Context

## Rationale

The user's real AI access is through personal web subscriptions. The browser session, cookies, Google login, 2FA state, and service-specific UI state must persist across tasks. Playwright persistent context is the cleanest way to create automation-owned profiles without touching the user's daily Chrome profile. Reusing the host Chrome profile would risk cookie collisions, Captcha triggers, tab interference, and accidental account logout. Starting with dedicated persistent contexts also supports the future Account Pool: ten registry slots can exist while one real healthy profile is used for the first Web AI Worker path.

## Implementation Consequence

This decision is treated as an input to Phase 1.1 Stage 0 and later task cards. It does not freeze contracts by itself, but it constrains package layout, documentation, placeholders, gate scripts, and the first implementation target.

## Re-evaluation Trigger

Reevaluate if persistent contexts create unacceptable service friction, if selectors repeatedly fail under isolated profiles, or if a remote browser pool becomes more robust than local Playwright on Windows.

## Stage 0 Handling

Stage 0 records this decision but does not over-implement it. The decision constrains repository layout, documentation language, placeholders, and future task cards. Any later implementation that needs to go beyond this decision must be raised in local review rather than silently changing the architecture.

## Audit Note

This file intentionally contains only the selected option, rationale, implementation consequence, and re-evaluation trigger. It does not include self-critique, reflection excerpts, or unrelated workflow lessons. That keeps decision records clean for later gate checks.
