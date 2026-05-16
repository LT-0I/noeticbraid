# Vendor reference: gbrain

- Upstream URL: https://github.com/garrytan/gbrain
- Inspected commit: `3933eb6a7915cb5495b8057b75567e2b1588b5ac`
- License: MIT
- License evidence: `LICENSE and upstream package.json license=MIT`
- Execution status: TS/JS/JSON files under `upstream/` are reference only and are not executed by NoeticBraid runtime.

## Exact files copied

- `upstream/src/core/search/token-budget.ts`
- `upstream/src/core/search/dedup.ts`
- `upstream/src/core/eval-capture-scrub.ts`

## Adaptation notes

Deduplication, token-budget, and PII/eval scrubber behavior are ported into noeticbraid_backend.memory.recall_ranker and noeticbraid_backend.privacy.scrub.

The production adapter is pure Python, additive, and does not introduce Node, Rust, network, or new runtime dependency requirements.

recall_ranker.py mirrors gbrain dedup split(/\s+/) with re.split(r"\s+", …) so empty and leading-whitespace chunk_text preserve JS token parity.
