# SDD-D2-01 Multimodel Debate Convergence

> Source of truth: structured ModelRoute, Debate, Convergence, and candidate JSONL records. This markdown is a concise review artifact only.

## Record chain

- SDD: `SDD-D2-01`
- Task: `task_omc_ingest`
- Route: `route_omc_ingest_debate_loop` (`multi_review` / `high`)
- Debate: `debate_omc_ingest_debate_loop` with 3 round(s)
- Convergence: `convergence_omc_ingest_debate_loop` decision `needs_more_evidence`
- Markdown source: structured records only; provider transcripts are excluded.

## Fixed participants

- `model_claude_opus_4_7` as `producer`
- `model_codex_gpt_5_5` as `adversary`
- `model_gemini_3_1_pro` as `source_auditor`

## Evidence refs

- Sources: `source_project_definition_v3_2`, `source_ai_invocation_reference`, `source_omc_metadata`
- Artifacts: `artifact_omc_claude_proposal`, `artifact_omc_codex_adversary`, `artifact_omc_gemini_source_audit`

## Convergence result

Do not accept yet. Complete evidence-gathering next actions and rerun convergence afterward.

### Unresolved disagreements

- `obj_omc_scope_overclaim` (high → next_action): Do not claim full §10.1 OMC demo completion from this loop; it only satisfies the manual §10.4 item 5 evidence slice.

### User decision requirements

- none

### Next actions

- `action_resolve_obj_omc_scope_overclaim` [verifier/planned]: Collect evidence or remediation for unresolved objection obj_omc_scope_overclaim before final acceptance.

## Candidate records

- `memory_omc_ingest_debate_loop` — status `candidate`; decision `needs_more_evidence`; upgrade: explicit user adoption OR reuse >=3 times with at least one independently checkable ledger run; not rejected is never sufficient

## R-6 upgrade gate

explicit user adoption OR reuse >=3 times with at least one independently checkable ledger run; not rejected is never sufficient
