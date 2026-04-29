# Channel Health Probe Strategy

- status: user-approved decision
- decided_at: 2026-04-28
- source: Round 1 Step 4 user decisions


## Candidate Set

The candidate set was narrowed during Step 4 review. This Stage 0 record does not repeat the full comparison table; it records the final user decision and its implementation consequences.

## User Selected

Startup 60s / recovery 30s / stable 1h or on-demand

## Rationale

IM health checks must be reliable without becoming noise. During startup, the system needs to learn which notification channels are reachable; sixty seconds is enough to detect immediate failures without flooding Feishu, Discord, Telegram, or ntfy. After a failure, shorter thirty-second recovery checks are justified because the system has already degraded and the user needs confidence that approvals and emergency notices can return. During stable idle periods, hourly or on-demand checks avoid status-message spam and reduce the chance of leaking sensitive operational context through IM. Real sends should count as health signals and should not trigger additional probe messages.

## Implementation Consequence

This decision is treated as an input to Phase 1.1 Stage 0 and later task cards. It does not freeze contracts by itself, but it constrains package layout, documentation, placeholders, gate scripts, and the first implementation target.

## Re-evaluation Trigger

Reevaluate if critical notifications are missed, if proxy instability makes Discord unreliable, if Feishu webhook configuration changes, or if the user enables a self-hosted always-on Gotify/ntfy endpoint.

## Stage 0 Handling

Stage 0 records this decision but does not over-implement it. The decision constrains repository layout, documentation language, placeholders, and future task cards. Any later implementation that needs to go beyond this decision must be raised in local review rather than silently changing the architecture.

## Audit Note

This file intentionally contains only the selected option, rationale, implementation consequence, and re-evaluation trigger. It does not include self-critique, reflection excerpts, or unrelated workflow lessons. That keeps decision records clean for later gate checks.
