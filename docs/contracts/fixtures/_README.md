# Fixtures (Authoritative, frozen 1.0.0)

contract_version: 1.0.0
status: authoritative
frozen: true
stage1_implementation_commit: b8d7152

These fixtures are the authoritative test baseline for Phase 1.1 1.0.0.

每个 JSON 文件顶部含 `$schema_status: authoritative` + `contract_version: 1.0.0` 元字段。下游消费者（Stage 2 GPT-B/C/D / 本地集成 / Console MSW mock）必须先 pop 这两个元字段后再 model_validate，与 `packages/noeticbraid-core/tests/conftest.py` 的 `read_fixture()` 行为等值。

允许用作:

- pytest 等价基线（实测样本与 `packages/.../tests/fixtures/` 字节级等值）
- gate 验证输入
- Console MSW mock baseline
- Stage 2 GPT-B/C/D 消费的 schema example

任何修改必须走 `docs/contracts/contract_change_requests/` 流程。
