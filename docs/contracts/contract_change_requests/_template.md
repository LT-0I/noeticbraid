# Contract Change Request

- request_id: ccr_{YYYYMMDD}_{topic_slug}
- requester: GPT-A | GPT-B | GPT-C | GPT-D | local_claude | user
- requested_at: <ISO timestamp>
- target_contract_version: 1.0.0 → ?
- requested_change_type: patch | minor | major

## Change Description

<具体改什么字段 / 接口>

## Justification

<为什么需要改>

## Impact Analysis

- 影响模块: TASK-1.1.X / TASK-1.1.Y
- 向后兼容性: yes / no
- 测试影响: <具体>

## Approval

- [ ] local_main_claude_session reviewed
- [ ] codex_xhigh_reviewed
- [ ] user_approved
- approval_decision: pending | approved | rejected
- approval_at: <timestamp>
- new_contract_version: <after_approval>
