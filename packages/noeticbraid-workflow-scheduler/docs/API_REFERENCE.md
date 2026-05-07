# API Reference

## `parse_card(payload)`

Parses a JSON-like workflow card. Supported modes are `reactive` and `autonomous`; autonomous cards require `autonomous.enabled=true`, `autonomous.dry_run=true`, `triggers=["schedule"]`, and non-empty interval `schedule_rules`.

## `WorkflowScheduler.run_card(card, dry_run=False, cwd=".")`

Runs one explicit card. A run emits `run_pending`, `run_started`, step events, and `run_finished`. `requires_confirmation` or `note_type="challenge"` blocks the run and sends a `requires_confirmation` local notification.

## `StepExecutor.execute(step, cwd, dry_run=False)`

`note` steps record completion. `shell` steps require an exact argv entry in `allowed_shell_commands`, a cwd under `allowed_cwd_roots`, a timeout, and output redaction. `requires_confirmation` blocks before execution; `approval_required_for_shell=true` also blocks unconfirmed shell steps at policy level.

## `OutboundNotifier.send(message, level, channel, refs)`

Allowed levels: `silent_record`, `low_priority`, `normal`, `requires_confirmation`, `urgent_interrupt`. Lark and DingTalk webhooks are env-var only. Telegram is disabled by default.

## CLI

```powershell
python -m workflow_scheduler validate-card --card fixtures/reactive_card.json
python -m workflow_scheduler run --card fixtures/reactive_card.json --ledger out/runs.jsonl --dry-run
python -m workflow_scheduler notify --message "review needed" --level normal --events out/notify.jsonl
python -m workflow_scheduler dry-run-schedule --card fixtures/autonomous_card.json --now-epoch 120
python -m workflow_scheduler show-config-example
```

