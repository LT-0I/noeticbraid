# Vault Encryption

- status: user-approved decision
- decided_at: 2026-04-28
- source: Round 1 Step 4 user decisions


## Candidate Set

The candidate set was narrowed during Step 4 review. This Stage 0 record does not repeat the full comparison table; it records the final user decision and its implementation consequences.

## User Selected

A. Windows DPAPI

## Rationale

The user is on a Windows host, and the previous HelixMind implementation already treated DPAPI as a preserved asset. The old state directory was deleted, so the new architecture starts from an empty vault; however, the DPAPI approach remains appropriate for local machine-bound secrets and private configuration references. DPAPI avoids overbuilding cross-platform secret infrastructure at Phase 1.1 while still giving a meaningful local boundary for startup tokens, webhook secrets, and account metadata references.

## Implementation Consequence

This decision is treated as an input to Phase 1.1 Stage 0 and later task cards. It does not freeze contracts by itself, but it constrains package layout, documentation, placeholders, gate scripts, and the first implementation target.

## Re-evaluation Trigger

Reevaluate if cross-machine restore, Linux support, encrypted backups, or multi-host synchronization become first-class requirements. At that point, keyring, Infisical, SOPS, or a dedicated secret manager may be considered.

## Stage 0 Handling

Stage 0 records this decision but does not over-implement it. The decision constrains repository layout, documentation language, placeholders, and future task cards. Any later implementation that needs to go beyond this decision must be raised in local review rather than silently changing the architecture.

## Audit Note

This file intentionally contains only the selected option, rationale, implementation consequence, and re-evaluation trigger. It does not include self-critique, reflection excerpts, or unrelated workflow lessons. That keeps decision records clean for later gate checks.

## Security Boundary Note

DPAPI protects local secret material at rest, but it is not a substitute for open/private directory hygiene. Browser cookies, profile directories, and real provider tokens must still remain outside the published repository. The Stage 0 package therefore creates only placeholder private directories and no actual vault entries.
