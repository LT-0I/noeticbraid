# RunRecord Integration

SP-H emits dictionaries shaped for frozen `RunRecord 1.0.0`:

- required fields: `run_id`, `task_id`, `event_type`, `actor`;
- actor: `system`;
- success mappings: `push_sources -> source_record_linked`, `pull_briefing/pull_faq -> artifact_created`;
- failures: `task_failed`;
- artifact refs: strings matching `artifact_[A-Za-z0-9_]+`;
- source refs: strings matching `source_[A-Za-z0-9_]+`.

No new event enum is introduced. If the host runtime has richer ledger context, it can pass or remap run/task/source/artifact IDs around the public functions.
