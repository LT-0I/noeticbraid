# noeticbraid-backend

NoeticBraid backend service skeleton for Phase 1.2 Stage 1.

This package provides a FastAPI application factory, seven fixture-safe routes from the frozen Phase 1.1 v1.0.0 contract, a DPAPI boundary skeleton, and a raw-sqlite token-store skeleton. Stage 1 intentionally does not freeze a new contract and does not bind real ledger, account-pool, or DPAPI credential data.

## Install

From the repository root:

```bash
pip install -e packages/noeticbraid-backend
```

For tests:

```bash
pip install -e packages/noeticbraid-backend[dev]
pytest packages/noeticbraid-backend
```

## Run locally

```bash
uvicorn noeticbraid_backend.app:create_app --factory --reload
```

Environment variables:

- `NOETICBRAID_STATE_DIR`: state directory, default `state/`.
- `NOETICBRAID_DPAPI_BLOB_PATH`: optional DPAPI startup-token blob path.

## Stage boundaries

- `/api/auth/startup_token` has no request body and always returns a skeleton rejection.
- `/api/account/pool` returns `{"profiles": []}` only; `profile_records` is deferred to Stage 1.5+.
- DPAPI uses stdlib `ctypes` only; no `pywin32`, `cryptography`, or `keyring`.
- Token storage uses raw synchronous `sqlite3` only.
