# Vendor reference: oh_my_claudecode

- Upstream URL: https://github.com/Yeachan-Heo/oh-my-claudecode
- Inspected commit: `90f19265cabb8f35a11e932aa89f206380de0554`
- License: MIT
- License evidence: `LICENSE and upstream package.json license=MIT`
- Execution status: TS/JS/JSON files under `upstream/` are reference only and are not executed by NoeticBraid runtime.

## Exact files copied

- `upstream/src/planning/artifact-names.ts`
- `upstream/src/team/contracts.ts`
- `upstream/src/verification/tier-selector.ts`

## Adaptation notes

Planning artifact naming, task-status contracts, safe-id regexes, and verification-tier selection are ported into noeticbraid_backend.orchestration.*.

The production adapter is pure Python, additive, and does not introduce Node, Rust, network, or new runtime dependency requirements.
