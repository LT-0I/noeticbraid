# TASK-1.1.4 — Schema Implementation

- task_id: TASK-1.1.4
- name: Implement Phase 1.1 core schemas
- linked_phase: Phase 1.1 Foundation Lock
- linked_deliverable: Step 4 v2 deliverable 4, draft contract to implementation
- contract_pin: 0.1.0 start; local owner freezes 1.0.0 after double review
- status: ready_for_GPT_A_after_stage0_review

## Scope

Implement the six schema models in the open core package:

- Task
- RunRecord
- SourceRecord
- ApprovalRequest
- SideNote
- DigestionItem

This task turns Stage 0 contract intent into real Pydantic v2 implementation under the package path. It does not freeze the contract and does not modify docs/contracts directly.

## Dependencies

No implementation dependency. This is the Stage 1 starting task.

## Estimated work

- optimistic: 0.5–1 day
- realistic: 1–2 days including tests and local review

## Implementation steps

1. Create schema implementation files under `packages/noeticbraid-core/src/noeticbraid_core/schemas/**`.
2. Implement Pydantic v2 models with constraints, defaults, validators, and business checks where appropriate.
3. Export the six models from the schema package.
4. Add schema unit tests under `packages/noeticbraid-core/tests/**`.
5. Add optional top-level smoke test if needed.
6. Run import and round-trip tests locally.
7. Submit output for local Claude + Codex double review.

## Reuse references

Use `reuse_log/phase1_1_reuse_candidates.md`:

- `pydantic` for schema implementation;
- `pytest` for tests;
- `pyfakefs` only if file-boundary tests are needed, but guard implementation is out of scope.

## Write boundary whitelist

GPT-A may modify:

- `packages/noeticbraid-core/src/noeticbraid_core/schemas/**` — schema implementation main path;
- `packages/noeticbraid-core/tests/**` — schema unit tests;
- `packages/noeticbraid-core/pyproject.toml` — only to add dependencies already approved in reuse_log;
- `tests/test_schema_smoke.py` — optional top-level import smoke test.

## Forbidden write paths

Any modification to the following is out of scope and treated as a system bug:

- `docs/contracts/phase1_1_pydantic_schemas.py` — contract stub; local owner reverse-syncs it after double review;
- `docs/contracts/phase1_1_openapi.yaml`;
- `docs/contracts/fixtures/**`;
- `docs/contracts/phase1_1_api_contract.md` top matter or version fields;
- `packages/noeticbraid-console/**`;
- `packages/noeticbraid-obsidian/**`;
- `packages/noeticbraid-runtime/**`;
- `legacy/**`;
- `private/**`;
- `docs/decisions/**`;
- `docs/architecture/**`;
- `scripts/**`;
- `reuse_log/**`.

## Prohibitions

- Do not import any code from `legacy/**`.
- Do not introduce dependencies not marked `直接并入` in `reuse_log/phase1_1_reuse_candidates.md`.
- Do not implement ledger, guard, Console, Obsidian, browser, or IM features.
- Do not directly modify `docs/contracts/**`.
- Do not upgrade `contract_version`.
- Do not claim the contract is frozen.

## Exit verification

Required checks:

```bash
pytest packages/noeticbraid-core/tests/test_schemas.py
python -c "from noeticbraid_core.schemas import Task, RunRecord, SourceRecord, ApprovalRequest, SideNote, DigestionItem"
```

After GPT-A implementation and local double review PASS, the local main Claude session performs the freeze flow:

1. write `frozen: true` and review commit hashes;
2. reverse-sync implementation fields into `docs/contracts/phase1_1_pydantic_schemas.py` while keeping the stub shape;
3. strip `Field()`, defaults, validators, methods, and business logic from the stub;
4. move constraints into `CONTRACT_NOTE` comments and the API contract field table;
5. upgrade `contract_version` to `1.0.0`;
6. refresh fixtures to authoritative status.

Schema equivalence gate uses field names, bare type signatures, and Literal value sets. It does not compare defaults, `ge`, `le`, regexes, validators, or business rules.

`contract_diff.py` must be created by the local main session before the freeze commit and used during freeze. It is not created by GPT-A in this task.

## Acceptance details for local review

Local reviewers should check not only that tests pass, but that the implementation preserves the intended boundary. GPT-A may improve field names or types if the draft is insufficient, but it must explain every divergence in its final report. The local owner then decides whether the contract stub should be reverse-synced with those names or whether a correction request is needed.

The schema implementation should be useful enough for downstream GPT-B/C/D to build around. That means the models should have clear enums, stable identifiers, JSON round-trip behavior, and test coverage for representative valid and invalid inputs. It should not overfit to future browser/account details. In particular, no schema implementation should introduce cookie, CSRF, browser profile, or quota-window fields in Phase 1.1.

## Required final note from GPT-A

GPT-A must end its response with a short implementation note listing:

- files changed;
- dependencies added;
- tests added;
- any field names changed from the Stage 0 stub;
- any constraints that should become CONTRACT_NOTE comments during freeze;
- any contract issue that should become a change request instead of direct modification.
