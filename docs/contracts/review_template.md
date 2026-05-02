# Phase 1.2 Stage 1.5 Contract Freeze Review Template

Candidate artifact: `docs/contracts/phase1_2_openapi.yaml`
Contract version: `1.1.0`
Frozen SHA256: `D7F3759390C34766CFF0CA14C8CB554704110E298BDBBCF28C195781C8084861`

## Construction note

This freeze starts from `phase1_2_stage1_v2_openapi_source.yaml`, preserves the Stage 1 v2 paths, operations, response shapes, and source-snapshot `components.schemas` order, and updates the contract metadata to Phase 1.2 Stage 1.5 / OpenAPI contract version `1.1.0`.

The six Phase 1.1 core schemas (`Task`, `RunRecord`, `SourceRecord`, `ApprovalRequest`, `SideNote`, `DigestionItem`) were non-empty in the Stage 1 v2 runtime source. Because `phase1_1_openapi.yaml` is the authoritative tie-breaker for core schema shapes and the runtime source differed from that baseline, the frozen artifact uses the Phase 1.1 core schema definitions while preserving the source snapshot schema order.

## Reviewer checklist

### 1. Schema completeness

- [ ] `components.schemas` contains exactly 13 schemas.
- [ ] The schema-name set exactly matches `contracts.py::ALL_SCHEMA_NAMES`:
  - `HealthResponse`
  - `AuthResponse`
  - `EmptyDashboard`
  - `WorkspaceThreads`
  - `ApprovalQueue`
  - `AccountPoolDraft`
  - `RunLedgerRuns`
  - `Task`
  - `RunRecord`
  - `SourceRecord`
  - `ApprovalRequest`
  - `SideNote`
  - `DigestionItem`
- [ ] The source-snapshot schema definition order is preserved; it has not been alphabetized or otherwise reordered.
- [ ] None of the six core schemas has empty `properties`.
- [ ] The six core schemas match the authoritative `phase1_1_openapi.yaml` shapes.

### 2. Version consistency

- [ ] `info.version == 1.1.0`
- [ ] `info.x-contract-version == 1.1.0`
- [ ] `info.x-status == AUTHORITATIVE`
- [ ] `info.x-frozen == true`
- [ ] `info.x-phase == "1.2"`
- [ ] `info.x-stage == "1.5-contract-freeze"`

### 3. Byte-equal hash

- [ ] `docs/contracts/phase1_2_openapi.yaml.sha256` is ASCII.
- [ ] The sidecar uses the exact format `<UPPERCASE_64_HEX_SHA256> *phase1_2_openapi.yaml`.
- [ ] The sidecar hash matches `docs/contracts/phase1_2_openapi.yaml`.
- [ ] The local freeze gate passes.

Local gate command template:

```powershell
python C:\Users\13080\Desktop\HBA\GPT5_Workflow\.codex\scripts\contract_freeze.py `
  --openapi C:\Users\13080\Desktop\HBA\GPT5_Workflow\.tmp\phase1_2_stage1_5_candidate\phase1_2_openapi.yaml `
  --frozen C:\Users\13080\Desktop\HBA\noeticbraid\docs\contracts\phase1_2_openapi.yaml `
  --mode check
```

The local main session may adapt the `--openapi` candidate path during integration, but the gate must remain `contract_freeze.py --mode check` and must be byte-equal.

### 4. License whitelist

- [ ] No new dependency is introduced.
- [ ] Existing whitelist remains Apache-2.0 / MIT / BSD-2-Clause / BSD-3-Clause / ISC.

### 5. Forbidden dependencies

- [ ] No PSF-2.0 dependency is introduced.
- [ ] No GPL, LGPL, MPL, EPL, or AGPL dependency is introduced.
- [ ] No `pywin32` dependency is introduced.
- [ ] No `mcp-server-sqlite` dependency is introduced.

### 6. Boundary compliance

- [ ] No backend source file under `packages/noeticbraid-backend/src/**` is changed or included beyond the frozen contract output.
- [ ] No auth implementation, token-store, SDK, DPAPI, SQLite schema, or generated SDK work is introduced.
- [ ] `noeticbraid/docs/contracts/phase1_1_openapi.yaml` is untouched.
- [ ] `packages/noeticbraid-core/**`, `packages/noeticbraid-console/**`, `private/**`, and `pnpm-lock.yaml` are untouched.
