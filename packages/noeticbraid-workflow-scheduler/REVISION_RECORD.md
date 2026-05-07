# SP-E Round-2 ????

date: 2026-05-07
target round: round-2 verifier
based on: ARBITRATION.md round-1 + REVISION_PROMPT_for_A_session.md
executor: codex CLI?? A-session ????????
package root: `noeticbraid-sp-E-scheduler/`

## 8 ? MUST ??

### MUST-1 HIGH ? Shell executor approval gate
- file:line: `workflow_scheduler/executor.py:48-64`
- ????: `StepExecutor` ?? `ExecutionPolicy`?`approval_required_for_shell=true` ???? shell step ?? `blocked/policy_requires_shell_approval`?
- ????: `tests/test_executor.py:66` `test_executor_approval_required_for_shell_blocks_when_unconfirmed`

### MUST-2 HIGH ? Allowlist exact-match
- file:line: `workflow_scheduler/executor.py:115-119`
- ????: shell argv allowlist ? prefix-match ?? normalized exact-match???/??????? argv?
- ????: `tests/test_executor.py:83-101` ?????? prefix escape ???

### MUST-3 HIGH ? Redaction marker + key ????
- file:line: `workflow_scheduler/redaction.py:27-49`, `workflow_scheduler/redaction.py:87-98`, `workflow_scheduler/ledger.py:105-119`, `workflow_scheduler/notifier.py:164-183`
- ????: ?? `raw_token/dpapi_blob/webhook_url/bot_token`??? key denylist?ledger/notifier ????????????
- ????: `tests/test_ledger_state.py:58` ?? key denylist?marker regex?ledger fsync?

### MUST-4 MED ? Autonomous approval + run_id idempotency
- file:line: `workflow_scheduler/cards.py:84-91`, `workflow_scheduler/cards.py:226-246`, `workflow_scheduler/scheduler.py:70-84`, `workflow_scheduler/ledger.py:69-92`
- ????: autonomous enabled ?? `approval_level in {light,strong}`?`run_card(..., run_id=...)` ???? ledger ??? cached run ???????
- ????: `tests/test_cards.py:101`, `tests/test_scheduler_cli.py:60`

### MUST-5 MED ? 5 ? outbound ?? + urgent fanout
- file:line: `workflow_scheduler/ledger.py:15-21`, `workflow_scheduler/notifier.py:57-71`, `workflow_scheduler/notifier.py:85-93`
- ????: 5 ? outbound ??? frozen RunRecord 14 ??????`urgent_interrupt` ?? fanout ? enabled Lark/DingTalk?
- ????: `tests/test_notifier.py:9`, `tests/test_notifier.py:94`

### MUST-6 MED ? ?? dead RunRecord mapping keys
- file:line: `workflow_scheduler/ledger.py:22-33`, `workflow_scheduler/scheduler.py:118-136`, `workflow_scheduler/scheduler.py:158-174`
- ????: `security_violation` ? `run_failed` ??? emit ?????? `schedule_due` emit???? mapping ????? dead key?
- ????: `tests/test_scheduler_cli.py:75`, `tests/test_ledger_state.py:38-54`

### MUST-7 MED ? Ledger + notifier fsync
- file:line: `workflow_scheduler/ledger.py:58-64`, `workflow_scheduler/notifier.py:176-182`
- ????: JSONL append ? `flush()` + `os.fsync()`?
- ????: `tests/test_ledger_state.py:58`, `tests/test_notifier.py:74`

### MUST-8 MED ? WorkflowCard schema strict enum
- file:line: `workflow_scheduler/schemas/workflow_card.schema.json:5-35`, `workflow_scheduler/cards.py:17-18`, `workflow_scheduler/cards.py:142-145`
- ????: schema root `additionalProperties=false`???/?? `card_id/task_id/task_type/approval_level`?`task_type` ?? frozen enum `project_planning/research/code_review`?`approval_level` ?? `none/light/strong/forbidden`?
- ????: `tests/test_cards.py:121`

## ????? 1.x backlog?
- 6 LOW ?? REVISION_PROMPT_for_A_session.md ?2 ???

## ????
- pytest: `python -m pytest -q --basetemp=.tmp/pytest-tmp -o cache_dir=.tmp/pytest-cache` -> `29 passed`??? `............................. [100%]`, `PYTEST_PASS_29`??
- compileall: `python -m compileall -q workflow_scheduler` -> `COMPILEALL_PASS`?
- CLI smoke: PASS??? `--help`?reactive dry-run?autonomous ? dry-run ?????autonomous dry-run?dry-run-schedule?notify?
- Security probes: 3/3 PASS?MUST-1 approval gate?MUST-2 exact allowlist?MUST-3 key redaction??

## ????
- license: `pytest` / `setuptools` ?? license gate ? PASS?
- frozen Task / Workflow / RunRecord 14: ??? `noeticbraid/docs/contracts/**`?RunRecord ?????? frozen 14 ??????
- private leak: `redact_value` key denylist ?? `raw_token/dpapi_blob/webhook_url/bot_token` ?? `[REDACTED]`?
- zip: ??????????? zip??? zip ?????

## ????
- `pyproject.toml` `0.1.0` -> `0.2.0`
- `workflow_scheduler.__version__` `0.1.0` -> `0.2.0`
