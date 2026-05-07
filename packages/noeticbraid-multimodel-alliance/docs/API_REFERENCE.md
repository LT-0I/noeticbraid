# API Reference

## `route(task_card: dict) -> dict`

Required input can be minimal:

```json
{"task_id": "task_prompt_cycle", "risk_hint": "medium"}
```

Supported task card fields:

- `task_id`: optional; generated if absent. Must resolve to `task_*`.
- `task_type`: optional hint for default capability.
- `risk_hint` / `risk_level`: `low`, `medium`, `high`, `disputed`.
- `trigger`: default `task_card`; one of frozen trigger enum.
- `required_capabilities`: non-empty list from frozen 12-capability enum.
- `available_models`: optional list. If absent, a deterministic local default pool is used.
- `run_refs`, `artifact_refs`, `source_refs` / `sp_h_source_refs`: optional reference arrays.
- `workflow_id`: optional `workflow_*` reference.
- `disputed`: `true` forces `manual_convergence`.

### `available_models[]` shape

```json
{
  "model_ref": "model_codex_cli",
  "role": "coder",
  "roles": ["coder", "reviewer", "adversary", "verifier"],
  "capabilities": ["coding", "code_review", "adversary", "verification"],
  "invocation": "codex_cli"
}
```

All user-supplied model entries are fail-closed: `model_ref`, role/roles, capabilities, and invocation must be valid.

## `run_debate(route: dict, rounds_input: list[dict]) -> dict`

`rounds_input` records external results. SP-B does not invoke models.

Common round fields:

- `participant_id` or `role`: chooses a participant from the route-derived participant list.
- `artifact_ref`: optional; generated if absent.
- `round_type`: optional; inferred from role.
- `verdict`: default `informational`.
- `summary`: used in the `verdicts[]` section.
- `objections[]`: optional objection records; missing evidence refs default to the round artifact.

Unresolved statuses are `raised`, `unresolved`, and `needs_user_decision`.
Objections may include `raised_by` / `addressed_by` trace actors, each either a `participant_id`, `manual`, or `human`.
`addresses_objection_ref` references an earlier objection and must use `accepted`, `rejected`, or `needs_user_decision` status.

## `converge(debate: dict) -> dict`

Convergence does not majority-vote. It partitions objections:

- `accepted` -> `accepted_objections[]`
- `rejected` -> `rejected_objections[]`
- `raised` / `unresolved` / `needs_user_decision` -> `unresolved_disagreements[]`

Critical or explicit user-decision objections generate blocking `user_decision_requirements[]`; high unresolved evidence issues become verifier `next_actions[]`.

## CLI

```powershell
python -m multimodel_alliance validate-fixtures
python -m multimodel_alliance route examples/task_card_medium.json --pretty
python -m multimodel_alliance run-fixture multimodel_alliance/fixtures/dual_review_prompt_cycle.json --pretty
```
