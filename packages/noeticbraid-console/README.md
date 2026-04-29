# noeticbraid-console

NoeticBraid Phase 1.1 Web Console (Stage 2 candidate).

> Stage 0 placeholder is upgraded by this package to a fully working console
> with mock backend (MSW). Phase 1.1 console is **frontend-only**: it talks
> to mocked API endpoints; no real backend process exists in Phase 1.1.

## Routes (Phase 1.1)

| Route | Page | Backing endpoint(s) |
|---|---|---|
| `/` | Dashboard | `GET /api/dashboard/empty` + `GET /api/health` |
| `/workspace` | Threads | `GET /api/workspace/threads` |
| `/runs` | Run Ledger | `GET /api/ledger/runs` |
| `/approvals` | Approval Queue | `GET /api/approval/queue` |

## Mocked endpoints (Phase 1.1)

- `GET /api/health`
- `GET /api/dashboard/empty`
- `GET /api/workspace/threads`
- `GET /api/ledger/runs`
- `GET /api/approval/queue`

## Routes intentionally not exposed in Phase 1.1

- `POST /api/auth/startup_token` — onboarding flow added in Phase 1.2
- `GET /api/account/pool` — multi-account UI added in Phase 1.3
- `/sources` / `/inbox` (legacy mock-up) — endpoints not in OpenAPI 1.0.0;
  Phase 1.2 adds them

## Contract pinning

This console is pinned to:

- `contract_version: 1.0.0`
- `contract_status: AUTHORITATIVE`
- `stage1_implementation_commit: b8d7152`

Sources of truth:
- `docs/contracts/phase1_1_pydantic_schemas.py`
- `docs/contracts/phase1_1_openapi.yaml`
- `docs/contracts/phase1_1_api_contract.md`

TS types in `src/types/contracts.ts` are a hand-written mirror of the 6
frozen schemas plus 5 endpoint response shapes.

## Local development

Prerequisites: Node 20+, pnpm 9+.

```bash
pnpm install
pnpm dev          # http://127.0.0.1:5173 (with MSW worker)
pnpm test         # Vitest unit tests (jsdom + MSW node server)
pnpm test:ui      # Vitest UI dashboard
pnpm test:e2e     # Playwright e2e (chromium)
pnpm typecheck    # tsc --noEmit
pnpm build        # production bundle
```

Before first e2e run:

```bash
pnpm exec playwright install chromium
```

## Dependencies (pinned, stage 2)

Runtime: React 18, TanStack Query 5, TanStack Router 1.
Build: Vite 5, TypeScript 5, @vitejs/plugin-react 4.
Test: MSW 2, Vitest 2, @testing-library/react 16, @testing-library/jest-dom 6,
Playwright 1, jsdom 25.

All versions are pinned via caret ranges in `package.json`. No `latest` tags
are permitted in this package.

See `reuse_log/phase1_1_stage2_console_reuse_candidates.md` for license and
reuse audit of new test-tooling dependencies.
