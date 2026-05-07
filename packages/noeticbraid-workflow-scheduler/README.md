# noeticbraid-sp-E-scheduler

SP-E Workflow Scheduler + Notifier standalone package.

This package implements a neutral `workflow_scheduler` runtime from the old `workflow_scheduler_telegram` prototype. It is not a daemon, cron service, queue worker, broker-backed task system, browser automation entrypoint, or durable workflow platform.

## Core API

```python
from workflow_scheduler import WorkflowScheduler, parse_card

card = parse_card({...})
result = WorkflowScheduler(ledger_path="runs.jsonl").run_card(card, dry_run=True)
```

## CLI

```powershell
python -m workflow_scheduler validate-card --card fixtures/reactive_card.json
python -m workflow_scheduler run --card fixtures/reactive_card.json --ledger out/runs.jsonl --dry-run
python -m workflow_scheduler notify --message "review needed" --level requires_confirmation --events out/notify.jsonl
python -m workflow_scheduler dry-run-schedule --card fixtures/autonomous_card.json --now-epoch 120
python -m workflow_scheduler show-config-example
```

## Safety boundaries

- Runtime dependencies: Python standard library only.
- Webhook tokens are env-var only; no token is written to repo, ledger, report, or CLI output.
- Telegram is disabled by default and only represented as a local fallback channel.
- Shell execution is default-deny and only allowed through `StepExecutor` exact-match allowlist + policy approval gate + cwd guard + timeout + redaction.
- Autonomous scheduling is dry-run only in this package.
- Frozen NoeticBraid contracts and main `noeticbraid/` are not modified.
- No zip is built for this deliverable per user instruction.

