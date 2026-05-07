# RunRecord and archive mapping

This module is an upper-layer collaboration record. It does not modify the frozen `RunRecord` implementation, does not add event types in code, and does not change how the current ledger stores events. The mapping below describes how module records can link to existing evidence once a future integration round chooses to persist them.

## Stable references

| Module record field | Existing evidence it can reference | Notes |
| --- | --- | --- |
| `task_id` | task card id or module task id | Keeps route, debate, convergence, and ledger evidence grouped. |
| `run_refs[]` | `RunRecord.run_id` values | Existing `run_` ids remain the append-only event anchors. |
| `artifact_refs[]` | prompt drafts, response zips, review files, arbitration notes, reports | Module records use stable artifact ids rather than embedding file contents. |
| `source_refs[]` | design drafts, archived reports, frozen contract references | The source list identifies evidence without copying frozen files. |
| `selected_models[].model_ref` | `RunRecord.model_refs[]` | Model references stay plain strings; this module does not introduce a `ModelProfile` registry. |
| `rationale` and `recommendation` | `RunRecord.routing_advice` or future report artifact | Existing `routing_advice` can hold short summaries during the freeze, but full records should be artifacts. |

## Current frozen RunRecord behavior

The read-only `RunRecord` reference exposes stable fields for `run_id`, `task_id`, `event_type`, `actor`, `model_refs`, `source_refs`, `artifact_refs`, `routing_advice`, and `status`. Its event type enum is frozen for the current implementation surface. This module therefore treats route/debate/convergence records as file artifacts that can be linked through existing `artifact_created`, `routing_advice_recorded`, and `source_record_linked` events.

## Evidence chain

A future archive can connect these records in this order:

1. `ModelRoute` points to the task id, route trigger, selected models, rejected models, and context source refs.
2. `Debate` points back to `route_id`, registers participants, and links every round to an artifact ref for a prompt, response, review, adversarial note, or verifier result.
3. `Convergence` points back to `debate_id`, records objection handling, and lists next actions or user decision requirements.
4. Existing `RunRecord` rows can reference the same model, source, and artifact ids so ledger queries can reconstruct the collaboration without embedding the new objects inside the frozen schema.

## Future ledger event types

If the contract is reopened later, these event types would be candidates for a separate change request rather than implemented behavior in this module:

- `route_selected`
- `debate_started`
- `debate_round_recorded`
- `convergence_reported`
- `user_decision_requested`

Until such a contract change is accepted, the safe bridge is to store the three module records as artifacts and use the existing ledger fields to point at them.

## Archive evidence examples

The module records are designed to reference archive evidence such as:

- prompt paths for context-bundle instructions;
- response zip artifacts produced by a model session;
- reviewer markdown reports;
- arbitration or convergence markdown;
- integration reports with local command evidence;
- frozen-source references such as the Phase 1.2 OpenAPI contract and sidecar digest.

The mapping is intentionally one-way and documentary in this round: it makes future integration easier without changing `RunRecord`, backend storage, Console behavior, or the frozen API contract.
