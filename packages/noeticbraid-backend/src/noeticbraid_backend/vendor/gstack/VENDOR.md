# Vendor reference: gstack

- Upstream URL: https://github.com/garrytan/gstack
- Inspected commit: `f58977041cc9e0c7b5d677a911c890d08a853449`
- License: MIT
- License evidence: `LICENSE and upstream package.json license=MIT`
- Execution status: TS/JS/JSON files under `upstream/` are reference only and are not executed by NoeticBraid runtime.

## Exact files copied

- `upstream/scripts/question-registry.ts`
- `upstream/scripts/one-way-doors.ts`
- `upstream/scripts/discover-skills.ts`

## Adaptation notes

Approval registry schema and one-way-door classifier are ported into noeticbraid_backend.orchestration.approvals; skill discovery is reference material for future catalog work.

The production adapter is pure Python, additive, and does not introduce Node, Rust, network, or new runtime dependency requirements.
