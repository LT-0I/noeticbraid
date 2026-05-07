# Advisory OpenAPI change request draft

This document is advisory only. It does not modify the frozen Phase 1.2 OpenAPI 1.1.0 YAML, does not modify the SHA sidecar, and does not add backend routes. Any future API work must go through a separate contract change process and preserve the existing `/api/` prefix, OpenAPI 3.1.0 style, tags, operation ids, strict schemas, and stable id prefixes.

## Proposed future endpoints

| Method | Path | Tag | operationId | Purpose |
| --- | --- | --- | --- | --- |
| POST | `/api/routes` | route | `create_model_route_api_routes_post` | Create a model route recommendation or decision for a task/context bundle. |
| GET | `/api/routes/{route_id}` | route | `get_model_route_api_routes_route_id_get` | Read one route record by stable route id. |
| POST | `/api/debates` | debate | `create_debate_api_debates_post` | Create a debate record from a route and registered participants. |
| GET | `/api/debates/{debate_id}` | debate | `get_debate_api_debates_debate_id_get` | Read debate participants, rounds, verdicts, and unresolved objections. |
| POST | `/api/debates/{debate_id}/rounds` | debate | `append_debate_round_api_debates_debate_id_rounds_post` | Append a producer, reviewer, adversary, or verifier round. |
| POST | `/api/convergences` | convergence | `create_convergence_api_convergences_post` | Create a convergence recommendation from a debate. |
| GET | `/api/convergences/{convergence_id}` | convergence | `get_convergence_api_convergences_convergence_id_get` | Read recommendation, objection handling, user decision requirements, next actions, and memory candidates. |

## Draft contract rules

- These endpoints would record collaboration metadata only; they would not trigger high-risk execution.
- Request and response schemas should use `additionalProperties: false`, stable id prefixes, bounded arrays, explicit enums, and preserved declaration order.
- `ModelRoute`, `Debate`, and `Convergence` should remain separate objects instead of being embedded into `RunRecord.routing_advice`.
- Future persistence should link to `RunRecord` through `task_id`, `run_refs`, `source_refs`, and `artifact_refs`.
- The current module fixtures can be used as contract examples, but they are not API fixtures yet.

## Out of scope for this module round

- No OpenAPI YAML or sidecar patch.
- No generated SDK.
- No backend route implementation.
- No Console or frontend display.
- No database migration.
- No new dependency on a multi-agent framework.

## Future acceptance gate

A later contract round should require independent review, a contract-diff gate, schema tests, route/debate/convergence fixture tests, and explicit proof that the frozen Phase 1.2 behavior remains unchanged unless the contract version is intentionally advanced.
