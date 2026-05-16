# Vendor reference: claude_mem

- Upstream URL: https://github.com/thedotmack/claude-mem
- Inspected commit: `37d24944af5f4afaa0de2b0bd0034bb432f2b714`
- License: Apache-2.0
- License evidence: `LICENSE and upstream package.json license=Apache-2.0; upstream NOTICE reviewed and attribution retained here: Claude-Mem, Copyright 2026 Alex Newman.`
- Execution status: TS/JS/JSON files under `upstream/` are reference only and are not executed by NoeticBraid runtime.

## Exact files copied

- `upstream/src/core/schemas/memory-item.ts`
- `upstream/src/core/schemas/context-pack.ts`
- `upstream/src/utils/context-injection.ts`

## Adaptation notes

Memory item/source/context-pack schemas are ported into noeticbraid_backend.memory.schemas. Context injection is reference-only for future managed-context block updates.

The production adapter is pure Python, additive, and does not introduce Node, Rust, network, or new runtime dependency requirements.
