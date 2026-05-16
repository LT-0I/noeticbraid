# Vendor reference: everything_claude_code

- Upstream URL: https://github.com/affaan-m/everything-claude-code
- Inspected commit: `0df46ec870a2c86b41f2da7a4bb46836704d3952`
- License: MIT
- License evidence: `LICENSE, upstream package.json license=MIT, and pyproject.toml license=MIT`
- Execution status: TS/JS/JSON files under `upstream/` are reference only and are not executed by NoeticBraid runtime.

## Exact files copied

- `upstream/schemas/state-store.schema.json`
- `upstream/scripts/lib/agent-compress.js`
- `upstream/scripts/lib/cost-estimate.js`

## Adaptation notes

State-store schema is ported into noeticbraid_backend.orchestration.ledger_schema, and token-cost estimation is ported into noeticbraid_backend.orchestration.cost_estimate. Agent compression remains reference-only.

The production adapter is pure Python, additive, and does not introduce Node, Rust, network, or new runtime dependency requirements.
