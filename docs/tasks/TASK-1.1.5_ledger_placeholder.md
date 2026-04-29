# TASK-1.1.5 (Placeholder)

- status: PENDING_SCHEMA_FREEZE
- generated_at: stage 0 (Step 5)
- final_card_to_be_issued_at: Step 7 (after schema 1.0.0 frozen)

## Why placeholder?

阶段 0 时 schema 仍是 0.1.0 草案。子任务卡片的出口验证和 contract_pin 必须基于冻结后的 1.0.0，否则会被锚定到草案错误字段。

## High-level scope (informational only)

- TASK-1.1.5: Run Ledger JSONL append + Source Index minimal schema
- TASK-1.1.6: ModeEnforcer + 动作 12/13/14 拦截 + subprocess 白名单 + #22 CLI Runner registry stub + 红线测试
- TASK-1.1.7: Web Console Shell + 5 页面空态 + MSW mock

## Final card issuance

待 TASK-1.1.4 双审 PASS + schema 锁 1.0.0 后，由本地主 Claude session 按双写规则编排完整卡片。主件在 `GPT5_Workflow/prompts/round1_step7_*.md`，副本替换本 placeholder 并带 source-of-truth commit hash 行。

## Write boundary placeholder

To be filled in Step 7.
