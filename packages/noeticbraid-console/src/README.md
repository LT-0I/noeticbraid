# noeticbraid-console/src

Phase 1.1 Web Console source: React + Vite + TypeScript + MSW.

Code-based TanStack Router with 4 routes (`/`, `/workspace`, `/runs`, `/approvals`)
matching the 5 frozen authoritative endpoints in the contract 1.0.0 OpenAPI
(`/api/health`, `/api/dashboard/empty`, `/api/workspace/threads`, `/api/ledger/runs`,
`/api/approval/queue`). MSW 2.x serves the endpoints from `src/mocks/fixtures/`
during dev and tests; Phase 1.2 will swap in a real backend.
