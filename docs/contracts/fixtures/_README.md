# Fixtures (DRAFT, non-authoritative)

contract_version: 0.1.0
status: draft_fixture_nonbinding

These fixtures are NOT test baselines or gate inputs.

阶段 1 GPT-A schema 冻结 1.0.0 后，必须刷新 fixtures 并升级到 contract_version: 1.0.0 + status: authoritative。
This is a TASK-1.1.4 exit requirement.

阶段 0 fixtures 仅用作:

- Console 端 MSW mock 的初步占位（用户可跳过）
- 设计文档示例

**禁止**用作:

- pytest fixture
- gate 验证输入
- 阶段 1 之前任何 CI 测试基线
