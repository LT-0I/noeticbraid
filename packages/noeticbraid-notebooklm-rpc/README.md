# NoeticBraid NotebookLM RPC

## Purpose

`noeticbraid-notebooklm-rpc` wraps the pinned upstream `notebooklm-py==0.4.1` client with NoeticBraid multi-account pool semantics. It replaces the browser-automation `noeticbraid-notebooklm-bridge` package for new NotebookLM integrations.

## Risk warning

NotebookLM RPC access uses undocumented Google API behavior implemented by upstream `notebooklm-py`. Users are responsible for account authorization, cookie storage, Terms of Service compliance, quota behavior, and account risk.

## Install

```bash
python -m pip install -e ./packages/noeticbraid-notebooklm-rpc[dev]
```

## Quick start single account

Use upstream directly when one storage state is enough:

```python
import notebooklm

async def list_notebooks():
    client = await notebooklm.NotebookLMClient.from_storage(
        path="/path/to/storage_state.json",
        timeout=30.0,
    )
    async with client:
        return await client.notebooks.list()
```

## Quick start multi-account pool

`account_op(pool)` is a no-retry primitive for one operation:

```python
from noeticbraid.tools.notebooklm_rpc import NotebookLMAccountPool, account_op

pool = NotebookLMAccountPool.from_config()

async def list_once():
    async with account_op(pool) as (client, account_id):
        notebooks = await client.notebooks.list()
        return account_id, notebooks
```

`run_with_pool(pool, op_fn)` retries by rotating accounts on auth, rate-limit, server-streak, or captcha-trigger failures:

```python
from noeticbraid.tools.notebooklm_rpc import run_with_pool

async def list_with_rotation(pool):
    return await run_with_pool(pool, lambda c: c.notebooks.list())
```

`op_fn` must be idempotent because it may run more than once against different accounts. Side effects from a failed attempt can persist on that account.

## Multi-account semantics

`pool.pick()` selects the eligible account with the least recent successful operation, then breaks ties by ascending `account_id`. Accounts are ineligible while in cool-down, when quota is exhausted, or when explicitly excluded by `run_with_pool` after a failed attempt.

Default cool-downs are: rate-limited 3600s, login-required 43200s, captcha 86400s, and server-error streak 1800s after three consecutive `ServerError` failures. Quota is counted by successful pool operation (`mark_success`) per account and resets at the next configured local midnight.

The pool writes state to `NOETICBRAID_NOTEBOOKLM_POOL_STATE` or `~/.noeticbraid/notebooklm/pool-state.json` and appends independent NDJSON pool events to `NOETICBRAID_NOTEBOOKLM_RUNLOG_PATH` or `~/.noeticbraid/notebooklm/runlog.ndjson`.

## Roadmap

- D5-02: artifacts generation and `SourceRecord` serialization.
- D5-03: lifecycle, sharing, research, notes, and settings APIs.
- D5-04: remove the deprecated bridge and revisit multi-process pool safety.
