---
nb_type: run_record
schema_version: "obsidian-hub-0.1"
contract_version: "1.3.0"
run_id: "{{run_id}}"
task_id: "{{task_id}}"
event_type: task_completed
actor: system
status: recorded
created_at: "{{created_at}}"
model_refs:
  - "{{model_ref}}"
source_refs:
  - "{{source_ref_id}}"
artifact_refs:
  - "{{artifact_ref}}"
tags:
  - noeticbraid/run
---

# Run {{run_id}}

## Routing advice

{{routing_advice}}

## Evidence

- Sources: [[{{source_ref_id}}]]
- Artifacts: [[{{artifact_ref}}]]

## Outcome

{{outcome_summary}}
