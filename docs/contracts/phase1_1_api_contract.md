---
contract_version: 0.1.0
status: DRAFT
authoritative: false
owner: local_main_claude_session
freeze_decision_pending: TASK-1.1.4 double review PASS, then local owner freeze
---

# Phase 1.1 API Contract Draft

This document is a non-authoritative Stage 0 contract overview. It defines names, boundaries, and vocabulary for Phase 1.1 only. It is not a frozen implementation contract and must not be used as a test baseline until the local main Claude session promotes it to `1.0.0` after TASK-1.1.4.

## 1. Contract authority

The contract owner is the local main Claude session. GPT-5.5 Pro Web can draft this document; GPT-A can implement schemas under the package path; GPT-B/C/D can consume the frozen contract later. None of those GPT sessions can mark this draft authoritative.

The contract lifecycle is:

```text
0.1.0 draft
→ GPT-A implementation
→ local Claude + Codex double review
→ local owner reverse-syncs stub
→ local owner freezes 1.0.0
→ downstream GPT-B/C/D consume 1.0.0
```

## 2. Model inventory

Six model names are reserved:

1. **Task**: classification, risk, approval, source channel, and future account hint.
2. **RunRecord**: evidence event for the Run Ledger.
3. **SourceRecord**: provenance entry for Source Index.
4. **ApprovalRequest**: approval-queue item.
5. **SideNote**: evidence-linked user reflection note.
6. **DigestionItem**: tracked follow-up state for a SideNote.

Stage 0 stubs preserve only class names, field names, bare types, and Literal sets. Implementation constraints such as min length, defaults, derived fields, validators, and serialization helpers belong to package implementation and later CONTRACT_NOTE comments after reverse-sync.

## 3. Task draft fields

`Task` represents a unit of work before it is fully scheduled. It carries `task_type`, `risk_level`, `approval_level`, `status`, `user_request`, and `source_channel`. The only multi-account placeholder allowed in Stage 0 is `account_hint: Optional[str]`. It is a routing hint, not an account id, profile id, cookie path, session token, subscription tier, or quota field.

## 4. RunRecord and event vocabulary

Run Ledger stores append-only evidence. Draft event types are:

- `task_created`
- `task_classified`
- `context_built`
- `approval_requested`
- `approval_decision_recorded`
- `web_ai_call_requested`
- `profile_health_checked`
- `source_record_linked`
- `artifact_created`
- `security_violation`
- `lesson_candidate_created`
- `routing_advice_recorded`
- `task_completed`
- `task_failed`

A `RunRecord` does not need to encode account-pool internals in Stage 0. It may reference models, sources, artifacts, and routing advice. The account/profile layer is intentionally deferred to private/runtime schema in later phases.

## 5. Source Index and provenance

`SourceRecord` is the canonical source metadata object. Run Ledger events should reference source records by `source_ref_id` instead of duplicating source content.

Important fields:

- `source_ref_id`: stable identifier for this source entry;
- `source_type`: user note, web page, GitHub repo, paper, patent, video, AI output, or paid database entry;
- `content_hash`: SHA256 of the exact content snapshot;
- `source_fingerprint`: normalized or approximate fingerprint for near-duplicate detection;
- `evidence_role`: why the source matters as evidence;
- `used_for_purpose`: how a particular run uses the source.

This closes the Step 3 v3 requirement that Run Ledger `sources_used.used_for` must map into Source Index vocabulary.

## 6. Approval Queue

Approval levels:

- `none`: direct execution, still recorded;
- `light`: one-time or one-hour allow/reject path;
- `strong`: explicit Console confirmation for every execution, with reason and diff;
- `forbidden`: static block, never enters Approval Queue.

The forbidden level is not a fourth button in the queue. It is a guard outcome. If a forbidden request appears in the Approval Queue, that is a system bug.

## 7. ModeEnforcer blocked actions

ModeEnforcer must statically block:

1. deleting or moving user raw records;
2. rewriting existing SideNote content;
3. automatic cross-account transfer or payment.

These actions produce `security_violation` evidence if attempted. They must not be downgraded to light or strong confirmation.

## 8. Console/backend endpoints

Draft endpoints:

- `GET /api/health`
- `POST /api/auth/startup_token`
- `GET /api/dashboard/empty`
- `GET /api/workspace/threads`
- `GET /api/approval/queue`
- `GET /api/account/pool`
- `GET /api/ledger/runs`

These endpoints are intentionally read-heavy and placeholder-friendly. They let the Console shell and MSW mock plan around an API shape without requiring a real backend implementation in Stage 0.

## 9. Fixture policy

All Stage 0 fixtures are examples only. They may help humans understand shape or help a future Console mock start, but they are not pytest fixtures, not gate input, not snapshot baselines, and not authoritative schema examples.

After local contract freeze, fixtures must be refreshed to:

```text
contract_version: 1.0.0
status: authoritative
```

## 10. Change request process

After `1.0.0`, direct contract edits are forbidden. Any GPT or local reviewer who finds a contract issue must create a file in `docs/contracts/contract_change_requests/`.

The change request must include:

- requester;
- target version;
- change type: patch, minor, or major;
- field or endpoint changes;
- justification;
- affected modules;
- compatibility analysis;
- test impact;
- local Claude review;
- Codex review;
- user approval.

Only after approval can the local owner update contract files and broadcast the new version.

## 11. Stage 0 non-goals

This contract does not define:

- browser profile directory schema;
- cookie/session schema;
- ChatGPT selector schema;
- quota tracker schema;
- paid database access schema;
- Console page implementation;
- Obsidian write rules;
- ledger JSONL append implementation.

Those belong to later tasks after the foundation contract becomes authoritative.

## 12. Field constraint handling after implementation

When GPT-A implements Pydantic schemas, it may use implementation-level constraints. Examples include required minimum string lengths, timestamp normalization, enum defaults, or model-level validation for logically incompatible states. Those implementation details do not belong in the Stage 0 stub. During the freeze process, the local owner should reduce the implementation to a bare contract shape:

```text
field names + bare types + Literal values
```

All other semantics move into `CONTRACT_NOTE` comments and the field constraint table in this document. This rule prevents the docs stub from becoming a second implementation that can drift from package code.

## 13. Draft endpoint intent

The endpoint list is intentionally narrow. `/api/health` and `/api/auth/startup_token` support the local Console shell. `/api/dashboard/empty` gives the Console a safe empty state. `/api/workspace/threads`, `/api/approval/queue`, `/api/account/pool`, and `/api/ledger/runs` give the UI shape without implying real task execution.

No endpoint in Stage 0 should imply that browser workers, profile launch, subprocess execution, Obsidian writing, or IM approval callbacks are implemented. Those actions require later guard and approval contracts.

## 14. Approval field semantics

`ApprovalRequest` is a draft queue object. It is not a permission grant by itself. It records what the system wants to do, why, what scope it affects, and whether the user has accepted or rejected the request. The queue is not allowed to contain forbidden actions. If an action is forbidden, ModeEnforcer must block it before it becomes an approval request.

The approval model will likely become richer after Console implementation, but Phase 1.1 only needs the common vocabulary: none, light, strong, forbidden; pending, approved, rejected, blocked.

## 15. SideNote and DigestionItem semantics

`SideNote` is evidence-linked reflection, not a psychological verdict. It must link to sources and use a type such as fact, hypothesis, challenge, or action. `DigestionItem` tracks whether the user has seen, responded to, acted on, or rejected a challenge. These objects support the user-growth loop, but they must never rewrite user raw notes.

The schema is deliberately minimal in Stage 0. The actual report engine is later. The important contract boundary is that SideNote history is append-only from the perspective of automation. Existing SideNote content is protected by ModeEnforcer.

## 16. Source and run relationship

The Source Index is a global provenance layer. The Run Ledger is a run-specific evidence layer. A source may exist before many runs and may be reused across them. A run may use multiple sources for different purposes. That is why `RunRecord.source_refs` stores references and `SourceRecord` stores the metadata.

A later implementation may add a join table or event payload to say exactly how a source was used in one run. Stage 0 keeps the shape simple and captures the vocabulary needed for that join.

## 17. What would make this draft invalid

This contract draft should be rejected if it contains any of the following:

- `contract_version: 1.0.0` before local freeze;
- `frozen: true` before local freeze;
- fixtures marked authoritative;
- cookie/session/profile fields in public schema;
- executable validators in `phase1_1_pydantic_schemas.py`;
- docs that claim downstream tasks can begin before TASK-1.1.4 double review.

These are not stylistic issues. They are authority-boundary violations.

## 18. Minimal stability promises

Even though this is a draft, a few names are intended to be stable unless local review finds a strong reason to change them: `Task`, `RunRecord`, `SourceRecord`, `ApprovalRequest`, `SideNote`, and `DigestionItem`. The same is true for the approval levels and the forbidden-action concept. These names appear across Console, Runtime, Obsidian, and guard planning, so arbitrary renaming by GPT-A should be treated as a review item.

The draft does not promise that every listed field will survive unchanged. GPT-A may discover that a field is redundant or that a type should be refined. Such changes are allowed only inside the implementation path during TASK-1.1.4. The local owner then decides whether to accept them into the frozen contract.

## 19. OpenAPI draft limitations

The OpenAPI file is only a Console planning surface. It does not define authentication semantics beyond startup-token shape, and it does not promise that every endpoint will be implemented in Stage 1.1. The goal is to let TASK-1.1.7 build an empty Console shell and MSW mock against stable names after contract freeze. Until then, OpenAPI remains a design artifact.
