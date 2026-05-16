# Vendor reference: tencentdb_agent_memory

- Upstream URL: https://github.com/Tencent/TencentDB-Agent-Memory
- Inspected commit: `5736acc8711b843756a2c0f8d86e939b28c5e02d`
- License: MIT
- License evidence: `LICENSE and upstream package.json license=MIT`
- Execution status: TS/JS/JSON files under `upstream/` are reference only and are not executed by NoeticBraid runtime.

## Exact files copied

- `upstream/src/core/store/search-utils.ts`
- `upstream/src/core/types.ts`
- `upstream/src/core/conversation/l0-recorder.ts`

## Adaptation notes

RRF search merge and host-neutral L0 capture models are ported into noeticbraid_backend.memory.rrf and noeticbraid_backend.memory.l0. Persistence remains deferred to C2.

The production adapter is pure Python, additive, and does not introduce Node, Rust, network, or new runtime dependency requirements.
