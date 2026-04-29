---
contract_version: 1.0.0
status: AUTHORITATIVE
authoritative: true
frozen: true
owner: local_main_claude_session
stage1_implementation_commit: b8d7152
stage1_review_claude_commit: b8d7152
stage1_review_codex_commit: b8d7152
freeze_decision: TASK-1.1.4 dual review PASS, local owner freeze applied
---

# Phase 1.1 API Contract (Frozen 1.0.0)

This document is the frozen authoritative Phase 1.1 contract. It defines names, boundaries, schema vocabulary, and field constraints for the Stage 2 GPT-B/C/D consumers after TASK-1.1.4 implementation and dual review PASS.

## 1. Contract authority

The contract owner is the local main Claude session. GPT-5.5 Pro Web can produce implementation and freeze artifacts under explicit prompts, but no GPT session can unilaterally mark or alter contract authority. This file is authoritative only because Stage 1 implementation passed dual review and this freeze flow upgraded it to `1.0.0`.

The contract lifecycle is:

```text
0.1.0 draft
→ GPT-A implementation
→ local Claude + Codex double review PASS
→ local owner reverse-syncs stub and freezes 1.0.0
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

The contract stub preserves only class names, field names, bare types, and Literal sets. Implementation constraints such as min length, defaults, validators, and serialization helpers are authoritative in §20 and mirrored as `CONTRACT_NOTE` comments in `phase1_1_pydantic_schemas.py`.

## 3. Task frozen fields

`Task` represents a unit of work before it is fully scheduled. It carries `task_type`, `risk_level`, `approval_level`, `status`, `user_request`, and `source_channel`. The only multi-account placeholder allowed in Phase 1.1 public schema is `account_hint: Optional[str]`. It is a routing hint, not a private credential or runtime profile field.

## 4. RunRecord and event vocabulary

Run Ledger stores append-only evidence. Frozen event types are:

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

A `RunRecord` does not encode account-pool internals in Phase 1.1. It may reference models, sources, artifacts, and routing advice. The private/runtime layer is intentionally deferred to later phases.

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

Frozen endpoint names for planning surface:

- `GET /api/health`
- `POST /api/auth/startup_token`
- `GET /api/dashboard/empty`
- `GET /api/workspace/threads`
- `GET /api/approval/queue`
- `GET /api/account/pool`
- `GET /api/ledger/runs`

These endpoints remain read-heavy and placeholder-friendly. They let the Console shell and MSW mock plan around an API shape without requiring a real backend implementation in Stage 1.1.

## 9. Fixture policy

Phase 1.1 fixtures are now authoritative. Each JSON file in `docs/contracts/fixtures/` carries:

```text
contract_version: 1.0.0
status: authoritative
```

Downstream consumers must remove `$schema_status` and `contract_version` before `model_validate`, matching `packages/noeticbraid-core/tests/conftest.py`.

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

## 11. Stage 1.1 non-goals

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

The frozen stub remains a bare shape contract:

```text
field names + bare types + Literal values
```

All other semantics live in `CONTRACT_NOTE` comments and the field constraint table in this document. This rule prevents the docs stub from becoming a second implementation that can drift from package code.

## 13. Endpoint intent

The endpoint list is intentionally narrow. `/api/health` and `/api/auth/startup_token` support the local Console shell. `/api/dashboard/empty` gives the Console a safe empty state. `/api/workspace/threads`, `/api/approval/queue`, `/api/account/pool`, and `/api/ledger/runs` give the UI shape without implying real task execution.

No endpoint in Phase 1.1 should imply that browser workers, profile launch, subprocess execution, Obsidian writing, or IM approval callbacks are implemented. Those actions require later guard and approval contracts.

## 14. Approval field semantics

`ApprovalRequest` is a queue object. It is not a permission grant by itself. It records what the system wants to do, why, what scope it affects, and whether the user has accepted or rejected the request. The queue is not allowed to contain forbidden actions. If an action is forbidden, ModeEnforcer must block it before it becomes an approval request.

Phase 1.1 only needs the common vocabulary: none, light, strong, forbidden; pending, approved, rejected, blocked.

## 15. SideNote and DigestionItem semantics

`SideNote` is evidence-linked reflection, not a psychological verdict. It must link to sources and use a type such as fact, hypothesis, challenge, or action. `DigestionItem` tracks whether the user has seen, responded to, acted on, or rejected a challenge. These objects support the user-growth loop, but they must never rewrite user raw notes.

Existing SideNote content is protected by ModeEnforcer. Future automation must append or create new records rather than mutate protected source material.

## 16. Source and run relationship

The Source Index is a global provenance layer. The Run Ledger is a run-specific evidence layer. A source may exist before many runs and may be reused across them. A run may use multiple sources for different purposes. That is why `RunRecord.source_refs` stores references and `SourceRecord` stores the metadata.

A later implementation may add a join table or event payload to say exactly how a source was used in one run. Phase 1.1 keeps the shape simple and captures the vocabulary needed for that join.

## 17. Frozen 状态下的禁止操作

The local owner must reject any change request that:

- downgrades `contract_version` from `1.0.0` without an approved change request;
- removes `frozen: true` or `authoritative: true` without an approved successor version;
- marks fixtures non-authoritative while keeping this version number;
- adds public cookie/session/profile credential fields to public schemas;
- adds executable validators to `phase1_1_pydantic_schemas.py` instead of keeping it as a stub;
- claims downstream tasks can bypass this frozen contract.

These are not stylistic issues. They are authority-boundary violations.

## 18. Minimal stability promises

The six names `Task`, `RunRecord`, `SourceRecord`, `ApprovalRequest`, `SideNote`, and `DigestionItem` are stable for Phase 1.1. The same is true for the approval levels and the forbidden-action concept. These names appear across Console, Runtime, Obsidian, and guard planning, so arbitrary renaming by downstream GPT sessions should be treated as a contract violation.

Field changes after this freeze require `docs/contracts/contract_change_requests/` and dual review.

## 19. OpenAPI components.schemas authority

The OpenAPI file is the frozen `components.schemas` baseline for the six Phase 1.1 models. Endpoints stay as the Stage 0 design surface: they define Console planning names but do not promise backend implementation in Stage 1.1. The goal is to let TASK-1.1.7 build an empty Console shell and MSW mock against stable names after contract freeze.

## 20. Frozen field constraint table (1.0.0)

This table is the authoritative constraint contract for Phase 1.1 1.0.0. Implementation in `packages/noeticbraid-core/src/noeticbraid_core/schemas/**` follows it. Any drift between this table and the implementation is a contract violation.

### 20.0 Global model_config (all 6 models)

```python
model_config = ConfigDict(
    extra="forbid",
    frozen=False,
    str_strip_whitespace=True,
    validate_assignment=True,  # M-1 from Stage 1 Claude review
)
```

`validate_assignment=True` means every field reassignment after model construction triggers secondary validation. Downstream GPT-B/C/D must be aware that `task.status = "completed"` re-runs Pydantic validation on `status`, not just blind attribute set.

### 20.1 Task

| field | type | required | default | constraints | notes |
|---|---|---|---|---|---|
| task_id | str | yes | — | min_length=1, max_length=128, pattern=r"^task_[A-Za-z0-9_]+$" | stable identifier prefixed with `task_` |
| task_type | Literal | yes | — | one of {project_planning, research, code_review} | Phase 1.1 supported task categories |
| risk_level | Literal | yes | — | one of {low, medium, high} | routing and approval risk |
| approval_level | Literal | yes | — | one of {none, light, strong, forbidden} | approval strength before execution |
| created_at | datetime | no | utc_now() | UTC-normalized; naive→replace UTC, aware→astimezone UTC | timezone-aware storage |
| status | Literal | no | "draft" | one of {draft, ready, queued, running, waiting_for_user, failed, completed} | lifecycle status |
| user_request | str | yes | — | min_length=1, max_length=8192 | original user request text |
| source_channel | Literal | yes | — | one of {console, obsidian, im, schedule, local} | request ingress channel |
| account_hint | Optional[str] | no | None | max_length=64; blank string → None | non-authoritative routing hint |
| project_ref | Optional[str] | no | None | max_length=128; blank string → None | project or workspace reference |

Methods:
- `is_terminal() -> bool` — `status in {"failed", "completed"}`
- `requires_user_approval() -> bool` — `approval_level in {"light", "strong", "forbidden"}`
- `to_event_dict() -> dict[str, str]` — returns `{task_id, task_type, status, source_channel}`

### 20.2 RunRecord

| field | type | required | default | constraints | notes |
|---|---|---|---|---|---|
| run_id | str | yes | — | min_length=1, max_length=128, pattern=r"^run_[A-Za-z0-9_]+$" | stable run identifier |
| task_id | str | yes | — | min_length=1, max_length=128, pattern=r"^task_[A-Za-z0-9_]+$" | linked task identifier |
| event_type | Literal | yes | — | one of {task_created, task_classified, context_built, approval_requested, approval_decision_recorded, web_ai_call_requested, profile_health_checked, source_record_linked, artifact_created, security_violation, lesson_candidate_created, routing_advice_recorded, task_completed, task_failed} | run ledger event vocabulary |
| created_at | datetime | no | utc_now() | UTC-normalized; naive→replace UTC, aware→astimezone UTC | event timestamp |
| actor | Literal | yes | — | one of {user, system, model, local_review} | event actor |
| model_refs | list[str] | no | [] | max_items=100; each item pattern=r"^model_[A-Za-z0-9_]+$"; no duplicates | model references |
| source_refs | list[str] | no | [] | max_items=100; each item pattern=r"^source_[A-Za-z0-9_]+$"; no duplicates | source references |
| artifact_refs | list[str] | no | [] | max_items=100; each item pattern=r"^artifact_[A-Za-z0-9_]+$"; no duplicates | artifact references |
| routing_advice | Optional[str] | no | None | max_length=4096; blank string → None | optional routing advice |
| status | Literal | no | "draft" | one of {draft, recorded, failed} | persistence status |

Methods:
- `is_failure() -> bool` — `status == "failed" or event_type in {"task_failed", "security_violation"}`
- `has_external_refs() -> bool` — true when any of `model_refs`, `source_refs`, or `artifact_refs` is non-empty
- `to_ledger_event_dict() -> dict[str, object]` — returns `{run_id, task_id, event_type, actor, status, created_at_isoformat}`

### 20.3 SourceRecord

| field | type | required | default | constraints | notes |
|---|---|---|---|---|---|
| source_ref_id | str | yes | — | min_length=1, max_length=128, pattern=r"^source_[A-Za-z0-9_]+$" | stable source identifier |
| source_type | Literal | yes | — | one of {user_note, web_page, github_repo, paper, patent, video, ai_output, paid_database} | source category |
| title | str | yes | — | min_length=1, max_length=512 | source title |
| canonical_url | Optional[str] | no | None | max_length=2048; if present must start with `http://` or `https://`; blank string → None | web-accessible location |
| local_path | Optional[str] | no | None | max_length=1024; blank string → None | local-only or mirrored material path |
| author | Optional[str] | no | None | max_length=256; blank string → None | author, organization, or account label |
| captured_at | datetime | no | utc_now() | UTC-normalized; naive→replace UTC, aware→astimezone UTC | capture timestamp |
| retrieved_by_run_id | str | yes | — | min_length=1, max_length=128, pattern=r"^run_[A-Za-z0-9_]+$" | run that retrieved or linked source |
| content_hash | str | yes | — | min_length=71, max_length=71, pattern=r"^sha256:[A-Fa-f0-9]{64}$" | L-1: validator lowercases the hex portion; storage form is lowercase `sha256:<hex64>` |
| source_fingerprint | str | yes | — | min_length=1, max_length=128, pattern=r"^fingerprint_[A-Za-z0-9_]+$" | stable deduplication fingerprint |
| quality_score | Literal | no | "unknown" | one of {low, medium, high, unknown} | quality assessment |
| relevance_score | Literal | no | "unknown" | one of {low, medium, high, unknown} | relevance assessment |
| evidence_role | Literal | yes | — | one of {user_context, reference_project, source_grounding, contradiction, memory_update_evidence} | role in evidence handling |
| used_for_purpose | Literal | yes | — | one of {project_positioning, constraint_extraction, source_grounding, prior_art_check, other} | purpose for which source was used |

Methods:
- `has_location() -> bool` — true when `canonical_url` or `local_path` is non-None
- `is_high_value() -> bool` — `quality_score == "high" and relevance_score == "high"`
- `to_evidence_key() -> str` — returns `f"{source_ref_id}:{source_fingerprint}"`

### 20.4 ApprovalRequest

| field | type | required | default | constraints | notes |
|---|---|---|---|---|---|
| approval_id | str | yes | — | min_length=1, max_length=128, pattern=r"^approval_[A-Za-z0-9_]+$" | stable approval identifier |
| task_id | str | yes | — | min_length=1, max_length=128, pattern=r"^task_[A-Za-z0-9_]+$" | task requesting approval |
| run_id | Optional[str] | no | None | max_length=128; if present pattern=r"^run_[A-Za-z0-9_]+$"; blank string → None | L-2: Optional+pattern skips pattern when value is None |
| approval_level | Literal | yes | — | one of {none, light, strong, forbidden} | approval strength needed |
| requested_at | datetime | no | utc_now() | UTC-normalized; naive→replace UTC, aware→astimezone UTC | request timestamp |
| requested_action | str | yes | — | min_length=1, max_length=2048 | action requiring approval |
| reason | str | yes | — | min_length=1, max_length=4096 | reason approval or block is needed |
| diff_ref | Optional[str] | no | None | max_length=256; blank string → None | optional diff or artifact reference |
| status | Literal | no | "pending" | one of {pending, approved, rejected, blocked} | decision status |

Methods:
- `is_resolved() -> bool` — `status in {"approved", "rejected", "blocked"}`
- `is_approved() -> bool` — `status == "approved"`
- `needs_user_decision() -> bool` — `status == "pending" and approval_level not in {"none", "forbidden"}`

### 20.5 SideNote

| field | type | required | default | constraints | notes |
|---|---|---|---|---|---|
| note_id | str | yes | — | min_length=1, max_length=128, pattern=r"^note_[A-Za-z0-9_]+$" | stable note identifier |
| created_at | datetime | no | utc_now() | UTC-normalized; naive→replace UTC, aware→astimezone UTC | note timestamp |
| linked_source_refs | list[str] | no | [] | max_items=100; each item pattern=r"^source_[A-Za-z0-9_]+$"; no duplicates | evidence source references |
| note_type | Literal | yes | — | one of {fact, hypothesis, challenge, action} | side note type |
| claim | str | yes | — | min_length=1, max_length=4096 | claim or action text |
| confidence | Literal | yes | — | one of {low, medium, high} | confidence in claim |
| user_response | Literal | no | "unread" | one of {unread, accepted, rejected, modified} | user handling state |
| follow_up_ref | Optional[str] | no | None | max_length=128; blank string → None | optional follow-up reference |

Methods:
- `has_sources() -> bool` — true when `linked_source_refs` is non-empty
- `is_actionable() -> bool` — `note_type in {"challenge", "action"} and user_response in {"unread", "modified"}`
- `is_user_resolved() -> bool` — `user_response in {"accepted", "rejected", "modified"}`

### 20.6 DigestionItem

| field | type | required | default | constraints | notes |
|---|---|---|---|---|---|
| digestion_id | str | yes | — | min_length=1, max_length=128, pattern=r"^digestion_[A-Za-z0-9_]+$" | stable digestion identifier |
| side_note_id | str | yes | — | min_length=1, max_length=128, pattern=r"^note_[A-Za-z0-9_]+$" | source side note |
| created_at | datetime | no | utc_now() | UTC-normalized; naive→replace UTC, aware→astimezone UTC | creation timestamp |
| c_status | Literal | no | "c0" | one of {c0, c1, c2, c3, c4, cX} | review cadence state |
| user_response_ref | Optional[str] | no | None | max_length=128; blank string → None | reference to user response |
| next_review_at | Optional[datetime] | no | None | if present UTC-normalized; None passthrough | optional next review timestamp |
| status | Literal | no | "open" | one of {open, closed, rejected, snoozed} | digestion workflow status |

Methods:
- `is_overdue(now: datetime) -> bool` — false when `next_review_at is None` or `status not in {"open", "snoozed"}`; otherwise compares `next_review_at <= ensure_utc_datetime(now)`
- `is_closed() -> bool` — `status in {"closed", "rejected"}`
- `needs_review(now: datetime) -> bool` — `status == "open" and is_overdue(now)`
