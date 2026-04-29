# Phase 1.1 Stage 2 Guard reuse candidates (GPT-C)

contract_pin: 1.0.0
stage: 2_guard
status: stage2_guard_candidate
generated_at: 2026-04-29T10:03:23Z

## Reuse strategy

GPT-C does NOT introduce new external dependencies. Implementation uses Python
stdlib + pydantic (already a Stage 1 dep, frozen in pyproject) + pytest (already
a Stage 1 test dep). pyfakefs is already declared in Stage 0
`reuse_log/phase1_1_reuse_candidates.md` and remains available for future file-
boundary tests; current Stage 2 GPT-C test set does not yet require it.

## Components reused (stdlib only)

| Component | Source | License | Use |
|---|---|---|---|
| dataclasses | stdlib | PSF-2.0 | CliRunnerSpec, Decision (frozen=True) |
| enum | stdlib | PSF-2.0 | Action enum, DecisionVerdict enum |
| typing.Protocol | stdlib (3.8+) | PSF-2.0 | LedgerSink structural Protocol |
| typing.runtime_checkable | stdlib | PSF-2.0 | isinstance check on LedgerSink |
| typing.Literal | stdlib | PSF-2.0 | Mode = Literal["dry_run", "supervised", "autonomous"] |
| os.environ | stdlib | PSF-2.0 | NOETICBRAID_APPROVAL_TIMEOUT_SEC env var read |
| uuid.uuid4 | stdlib | PSF-2.0 | approval_request_id generation |
| pytest | already a Stage 1 dep | MIT | Test runner |
| pytest.mark.parametrize | pytest | MIT | 48-cell matrix coverage |
| unittest.mock.patch | stdlib | PSF-2.0 | patch.dict for env var override tests |

## Components considered and rejected

| Component | Reason rejected |
|---|---|
| pydantic BaseModel for Decision | Decision is intra-package value type, not a contract; @dataclass(frozen=True) suffices and avoids pulling pydantic into guard import graph |
| typing_extensions.Protocol | Python 3.11+ stdlib already supports Protocol; no need for backport |
| portalocker | GPT-B's territory (RunLedger JSONL lock); guard does not write files |
| anyio / trio | Phase 1.1 stub does not need async; ModeEnforcer.check() is sync |

## Forbidden additions

GPT-C does NOT modify packages/noeticbraid-core/pyproject.toml. Any new dependency
addition belongs to GPT-B (portalocker for RunLedger) or to local main session at
Stage 3 integration.

## Cross-module decoupling note

guard/protocols.py defines LedgerSink Protocol. GPT-C does NOT import
the GPT-B ledger package. GPT-B's RunLedger naturally satisfies LedgerSink via
structural subtyping without inheritance. Stage 3 local main session will inject
RunLedger instance into ModeEnforcer constructor.
