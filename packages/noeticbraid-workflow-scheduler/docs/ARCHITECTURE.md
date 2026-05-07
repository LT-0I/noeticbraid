# SP-E Architecture

SP-E is a standalone top-level workflow scheduler/notifier. It coordinates explicit workflow-card runs, guarded step execution, local run ledgers, scoped state updates, and outbound notifications. It does not provide a daemon, broker, cron service, background worker, browser automation, or durable workflow platform.

## Components

- `cards.py`: validates `WorkflowCard`, `WorkflowStep`, `ScheduleRule`, and `ExecutionPolicy`.
- `scheduler.py`: orchestrates one explicit card run and dry-run schedule checks.
- `executor.py`: runs `note` steps and exact-match allowlisted `shell` steps with policy approval gate with cwd guard, timeout, and redaction.
- `ledger.py`: writes neutral JSONL events and maps them to frozen `RunRecord.event_type` values.
- `notifier.py`: `OutboundNotifier.send(message, level, channel, refs)` with local fallback and webhook adapters.
- `state_store.py`: atomically updates only `modules.workflow_scheduler` in an explicit state file.
- `redaction.py`: shared output redaction for secrets, private paths, local profile hints, and sensitive URL query keys.

## Open-source patterns absorbed

APScheduler influenced the separation between schedule rules, executors, and stores. Prefect influenced explicit run-state tracking and human-in-the-loop states. Temporal influenced the ledger-first mindset and workflow/activity separation. Celery influenced the distinction between scheduler and worker, while SP-E intentionally avoids broker/worker behavior.

No code or runtime dependency from these projects is imported.

