# SP-C1 implementation notes

## Module layout

Implemented package: `src/noeticbraid_core/account/`.

- `models.py`: Pydantic v2 models for private registry records, quota state, quota events, and sanitized public summaries.
- `store.py`: JSON/JSONL persistence rooted at an explicit `Path`; no backend `Settings` dependency is required, though `from_settings()` accepts any object with `account_quota_dir`.
- `enforcer.py`: deterministic account selection and quota mutation helpers.
- `session_health.py`: pure probe protocol plus `check_session_health()` and `record_session_health()`.
- `account_pool_bridge.py`: frozen `AccountPoolDraft` adapter that returns `{"profiles": [...]}` only.

## Data flow

```text
accounts.private.json
  -> AccountQuotaStore.load_registry()
  -> SessionHealthProbe.check(account)
  -> check_session_health()
  -> record_session_health()
  -> quota_state.json + quota_events.jsonl
  -> AccountQuotaEnforcer.select_account()
  -> account_pool_bridge.to_account_pool_profiles()
  -> {"profiles": [...]}
```

## Session health boundary

`SessionHealthProbe` is caller-owned. SP-C1 does not launch a browser, inspect a browser profile, read cookies, or scrape account sessions. Probes may return `observed_text` as an input convenience; the model excludes it from dumps and stores only `observed_text_hash`.

## Concurrency boundary

`AccountQuotaStore` serializes `update_state()` and `append_event()` with a process-local `threading.Lock`, covering single-process multi-thread/async-task races. It is intentionally not a cross-process file lock; advisory file locking and multiprocess stress tests are deferred to the 1.3.x backlog.

## Frozen contract boundary

The only public wrapper shape emitted by this package is:

```json
{"profiles": []}
```

New health/quota internals remain module-local. Any future OpenAPI top-level field change requires a separate contract bump workflow.
