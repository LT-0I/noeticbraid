---
nb_type: dashboard
schema_version: "obsidian-hub-0.1"
contract_version: "1.3.0"
dashboard_id: dashboard_today
title: NoeticBraid Today
date: "{{date}}"
generated: true
generated_at: "{{generated_at}}"
source_run_id: "{{run_id}}"
tags:
  - noeticbraid/dashboard
---

# NoeticBraid Today

> Generated surface. Manual notes belong under `## Manual notes` or in a separate user-owned note.

## Today focus

- [ ] `{{task_id}}` — {{task_summary}}; risk: {{risk_level}}; entry: {{source_channel}}

## Pending tasks

| Task | Status | Approval | Project |
|---|---|---|---|
| [[{{task_id}}]] | {{status}} | {{approval_level}} | [[{{project_ref}}]] |

## AI observations

- [[{{note_id}}]] — {{note_type}}, confidence: {{confidence}}

## Questions to face

- [ ] [[{{digestion_id}}]] — {{question}}

## Information radar

- High-value sources: {{high_value_source_count}}
- Needs verification: {{needs_verification_count}}
- Program-memory candidates: {{memory_candidate_count}}

## Active projects

- [[{{project_ref}}]] — latest run: `{{run_id}}`

## Digestion queue

- C0: {{c0_count}}
- C1: {{c1_count}}
- C2+: {{c2_plus_count}}

## Recent run ledger

- [[{{run_id}}]] — {{event_type}}

## Manual notes

Keep user-written notes here only if the future renderer preserves this section.
