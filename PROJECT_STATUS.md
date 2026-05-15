# NoeticBraid 项目状态矩阵 (PROJECT_STATUS)

> Status snapshot updated 2026-05-12 (δ demo day-0). `PROJECT_DEFINITION_v3.2.md` is the current spec source of truth.
> Legacy HelixMind blueprints remain historical references only; when conflicts exist, v3.2 wins.

## 0.0 状态文档变更记录

- `2026-05-11` (γ 阶段): 同步 §1 表格至 contract 1.2.0 / 8 端点 / 17 schemas；
  §2 表格按 Codex II 审计 Part 3 的 4 模块归属裁决重写（详见 `noeticbraid-workflow/MODULE_VERDICTS.md`）；
  补充 §0.5 命名分歧解决：项目最终名 NoeticBraid（drops HelixMind），驱动来源：`PROJECT_DEFINITION_v3.2.md §0`。

- `2026-05-12` (δ demo day-0): 进入 v3.2 §10.2 14 天 AI sidenote 追踪 demo（day-0=2026-05-12；day-14=2026-05-26）；δ-A 整链路（spec → impl → dual review → commit → P1 verified）已闭环；δ-B 组（D-1 #3-#5）平行启动，不阻塞 demo。

- `2026-05-12` (δ demo day-0 close): Part 2.C #1/#2/#3/#5 5 SDD 合并 + 1 hotfix（D1-01 / D1-02 / D2-01 / D2-01-hotfix-01 / D2-02 / D2-03），backend contract 升至 `1.3.0` 14 routes / 28 schemas（17 frozen 1.2.0 + 11 D2-02/D2-03 additive）；pytest counts 升 core 485 / backend 101 / multimodel-alliance 46 / console routes.test.tsx 12；HEAD `f06b044`。SDD-D1-02-hotfix-02 doc-only wording polish 同步落地。详见 `.omx/artifacts/sdd-ledger.md`。

- `2026-05-14` (δ demo day-2): **D5 系列 NotebookLM RPC 迁移完结**（SDD-D5-01..07，全 7 SDD + 2 hotfix + 1 retroactive，全程 dual-review）。`notebooklm-py==0.4.1` RPC 路线（新包 `noeticbraid-notebooklm-rpc`，`__all__` 38→55）完整替代 browser-automation `noeticbraid-notebooklm-bridge`，后者于 D5-07 经 R-6 授权退役删除（0 消费者；workspace 包数 8→7）。新增 RPC 测试 → notebooklm-rpc 323 PASS；删 bridge −24；6-包计量从峰值 1124 收至 1100。HEAD `9dcae5d`（D5-03 `d02e65d` ← D5-04 `de71ecd` ← D5-05 `6e12535` ← D5-06 `7b21faa` ← D5-07 `9dcae5d`）。所有 frozen contract byte-equal 保持；contract_diff / private_leak_scan gate 全绿。详见 §2 "D5 系列 closures (2026-05-14)" + `1workflowR&D/specs/SDD-D5-0{1..7}-*.md`。

## 0. 一段话愿景

NoeticBraid (内部代号 HelixMind / HBA) 不重造大模型，而是站在主流 AI 工具
(ChatGPT / Claude / Gemini / Codex / NotebookLM / Obsidian / GitHub / 浏览器 / CLI)
之上的一层 **个人 AI 调度、记忆、反思与共同进化系统**。核心公式：
**两条成长环 (AI 进化环 + 用户成长环) + 一套调度底盘 (双仓库 + 一账本 + 多账号池
+ 多模型路由辩论 + Workflow 调度器) + 一条不搬运原则 (Playwright + subprocess
全闭环) + 两条神圣红线 (用户原始记录神圣 / 用户主体地位神圣)**。Tagline：
让 AI 越用越准，让人越用越清醒。

## 0.5 命名分歧说明 (Naming Divergence — Resolved)

**Status: resolved on 2026-05-11 — NoeticBraid is the final engineering name.**

早期蓝图 §1.3 (`项目文档/HelixMind_Project_Blueprint_Package/HelixMind_Project_Blueprint_CN.md`)
曾把项目最终英文名写为 **HelixMind**；但 repo / workflow / v3.2 项目定义当前权威名称均为
**NoeticBraid** (见 `README.md` / `AGENTS.md` / `docs/architecture/step3_authority.md` / `PROJECT_DEFINITION_v3.2.md`)。

**2026-05-11 裁决**：项目最终工程名为 **NoeticBraid**，蓝图遗留命名 HelixMind 仅保留在历史 0ropodefinition / 蓝图引用中。
驱动：`PROJECT_DEFINITION_v3.2.md` 开头 §0 命名段。后续不再混用。

## 1. 当前快照

| 字段 | 值 |
|---|---|
| 当前阶段 | v3.2 δ demo **day-2** (2026-05-14；14-day timer day-0=2026-05-12 / day-14=2026-05-26)；Phase 1.2 SP integrations 完结；δ day-0 后续 SDD 全部落地：D2-04 (R-6 gate 全局化, Part 2.C #6) / D2-05 (SideNote opt-out 交互, Part 2.C #4) / D2-06 (ChatGPT Web real ping) / D3-01 (real OMC knowledge extraction) / D4-01 (OMC task reuse loop) + 各 hotfix；**D5-01..07 NotebookLM browser→RPC 迁移完结**（bridge 退役，详 §0.0 / §2）；console UI-SPEC-console-v1 redesign 落地；§10.2 sidenote demo P1 verified |
| 最后 noeticbraid commit (HEAD) | `db56ccb` (`docs(status): record D5 series completion (NotebookLM RPC migration, bridge retired)`) |
| 最近 module integration commits | δ day-2 (2026-05-14) D5 系列：`db56ccb` (status sync) ← `9dcae5d` (D5-07 删 bridge) ← `7b21faa` (D5-06) ← `6e12535` (D5-05) ← `de71ecd` (D5-04) ← `d02e65d` (D5-03) ← `05bb624`/`7bcf26d` (D5-02+hotfix-02) ← `1f626ea`/`bcbbe78` (D5-01+hotfix-01)；δ day-0..1 另落 D2-04 `fdf5f81`(+hotfix `99e05f2`) / D2-05 `dbd5da4`(+hotfix `1c3e013`) / D2-06 `0ac2e1a`(+hotfix `35f91a7`) / D3-01 `499c335`(+hotfix `48a342d`) / D4-01 `801d562`(+hotfix `0ececb2`) / console `aa52d0e` / CI-leak-allowlist `3ef55c6` |
| 当前 contract version | Backend API `1.4.0` (`packages/noeticbraid-backend/src/noeticbraid_backend/contracts.py::CONTRACT_VERSION`)；δ-E5 minor bump from 1.3.0 by SDD-D2-04 (additive: R-6 candidate→confirmed gate state；**无新 route**，RunRecord frozen 3-event enum 不变)；1.3.0 (D2-02/03) 与 1.2.0 byte-equal frozen snapshot 8 routes 均保留；SideNote v2 `CONTRACT_V2_VERSION=2.0.0` (SDD-D1-01) 并存 |
| 主要 tag | `phase-1.2-contract-1.2.0` / `phase-1.2-contract-1.3.0` / `phase-1.2-SP-C1-account-quota-1.0.0` / `phase-1.2-SP-C2-runtime-1.0.0` / `phase-1.2-SP-D-obsidian-1.0.0` / `phase-1.2-SP-H-notebooklm-1.0.0` / `phase-1.2-SP-E-scheduler-1.0.0` / **`phase-1.2-SP-H-notebooklm-rpc-2.0.0`** (D5 RPC 迁移完结 @ `9dcae5d`，supersedes SP-H-notebooklm-1.0.0) |
| Backend endpoints | 14 routes：8 frozen 1.2.0 (`FROZEN_ROUTE_SPECS`: health / auth / dashboard / workspace / approval / account / ledger runs / ledger aggregate) + 6 D2-02/D2-03 additive (`OMC_WORKSPACE_ROUTE_SPECS`: omc-ingest project task GET/POST + project candidates GET + project adopted GET + project adopt POST + capabilities GET + capability health-check POST)；SDD-D2-04 R-6 gate 为 embedded state，**未新增 route** |
| Schemas | 29 OpenAPI schema names (`ALL_SCHEMA_NAMES`)：δ day-0 的 28 (17 frozen 1.2.0 + 11 D2-02/D2-03 additive) + SDD-D2-04 additive 1 (`R6GateState`)；SideNote v2 contract `CONTRACT_V2_VERSION=2.0.0` 并存 |
| pytest core | PASS 533 (2026-05-14 δ day-2 全量重跑) |
| pytest backend | PASS 148 (2026-05-14 δ day-2 全量重跑) |
| pytest multimodel-alliance | PASS 62 (2026-05-14 δ day-2 全量重跑) |
| pytest obsidian | PASS 34 (2026-05-14 δ day-2 全量重跑) |
| pytest notebooklm-rpc | PASS 323 (D5-01..07；2026-05-14 δ day-2 全量重跑) |
| pytest workflow-scheduler / runtime | PASS 29 / 21 (2026-05-14 δ day-2 全量重跑)；7-package 合计 1150 |
| console routes.test.tsx | PASS 12 (δ day-0 末记录；本次 δ day-2 reconcile 未重跑 node runner，沿用上次记录值待复核) |
| CI 最近一次跑 | run `25381385524` PASS (last recorded remote gate；δ day-0..2 commits 走本地 pytest 全量验证 + dual-review，未全部走远端 CI) |
| pending_actor (state.json) | `idle` in `noeticbraid-workflow/state.json`；δ day-2 D5-01..07 + δ day-0..1 全部 SDD 已落地并 push origin main（+ tag `phase-1.2-SP-H-notebooklm-rpc-2.0.0`） |

---

## 2. §17 全量功能落地清单 → 6 模块矩阵

> 2026-05-11 γ 阶段更新：4 模块归属裁决落地，详见 `noeticbraid-workflow/MODULE_VERDICTS.md`。
> 本表格仅为快照；权威裁决以 MODULE_VERDICTS.md 为准。

每个模块的状态拆为两列：
- **(a) v3.3 artifact exists**：是否产出了 prompt/bundle/reviews/integration_report 等 v3.3 工件
- **(b) shipped in noeticbraid git / 裁决归属**：是否产生真实 noeticbraid commit + tag + audit_trail row，或已被 v3.2 MUP 裁决降级/归档

| 蓝图小节 | 模块名 | (a) v3.3 artifact exists | (b) shipped in noeticbraid git / 裁决归属 | 双评 A/B verdict / γ 裁决 | 当前位置 |
|---|---|---|---|---|---|
| §17.1 信息收集与研究 | **bestblogs_info_tracking** | ⚠ historical prototype exists — scanner / RSS / OPML 实现 + 13 pytest pass + integration_report；no Reviewer A artifact | ❌ 不进入第一阶段 runtime；v3.2 §10.4 信息雷达下调，裁决为历史归档 + post-MUP RSS adapter 候选 | Codex II Part 3：不阻塞第一阶段 | `noeticbraid-workflow/archive/tools-legacy/bestblogs_info_tracking/` |
| §17.2 多模型联合 | **multimodel_alliance** | ✅ TRUE — schemas / fixtures / validator / router-debate-convergence skeleton | ✅ 已迁入主仓 `noeticbraid/packages/noeticbraid-multimodel-alliance` (package `noeticbraid-multimodel-alliance`, namespace `noeticbraid.tools.multimodel_alliance`)；旧原型归档 | Codex II Part 3：进化引擎核心；真实辩论闭环 + ledger/candidate 留 δ | 主仓包 + `noeticbraid-workflow/archive/tools-legacy/multimodel_alliance/` |
| §17.3 账号与 quota 管理 | **account_quota** | ✅ TRUE — design + reviews + reply + integration_report 全套 v3.3 工件 | ✅ TRUE — commit `b11f203` (current SP-C1 integration; legacy module tag `module-account-quota-v0`)；audit prose `0a946c9` | ✅ A=APPROVE / B=CONDITIONAL PASS (legacy module review) | `noeticbraid/packages/noeticbraid-core/src/noeticbraid_core/account/` + backend account route |
| §17.4 Obsidian 中心 | **obsidian_hub** | ⚠ historical prototype exists + v3.3 SP-D integration; old archive lacked Reviewer A artifact | ✅ 已迁入主仓 `noeticbraid/packages/noeticbraid-obsidian` (package `noeticbraid-obsidian`)；旧原型归档 | Codex II Part 3：SideNote 安全 demo 依赖；§11.b.S 加固留 δ，阻塞第一阶段 demo 验收但不在 γ 改代码 | 主仓包 + `noeticbraid-workflow/archive/tools-legacy/obsidian_hub/` |
| §17.5 用户成长系统 | **user_growth_llmwiki** | ✅ TRUE — design + reviews + reply + integration_report 全套 v3.3 工件 | ✅ TRUE — commit `41aecb3`，tag `module-user-growth-llmwiki-v0`，audit_trail commit `80dcf15` | ✅ A=COMMENT 2MED+2LOW；B=REQUEST CHANGES 2HIGH+2MED | `noeticbraid/packages/noeticbraid-core/src/noeticbraid_core/user_growth_llmwiki/` + `docs/modules/user_growth_llmwiki/` |
| §17.6 自动化底盘 | **workflow_scheduler_telegram** | ✅ TRUE — runner state machine + JSONL events + Telegram rate cap + 10 pytest pass + reviewer A/B artifacts | ✅ scheduler 已迁入主仓 `noeticbraid/packages/noeticbraid-workflow-scheduler` (package `noeticbraid-workflow-scheduler`, namespace `noeticbraid.tools.workflow_scheduler`)；Telegram 降为可选 adapter；旧原型归档 | Codex II Part 3：scheduler 保留；Telegram adapter 不阻塞第一阶段 | 主仓包 + `noeticbraid-workflow/archive/tools-legacy/workflow_scheduler_telegram/` |

**汇总**：4 模块归属不再 pending。`multimodel_alliance` / `obsidian_hub` / `workflow_scheduler_telegram` 的主仓 package 已从 `noeticbraid/pyproject.toml` workspace 确认；`bestblogs_info_tracking` 裁决为历史归档 + 第二阶段 adapter 候选。旧 `noeticbraid-workflow/tools/` 原型不再当 runtime 源。

---

## 3. 蓝图全章节覆盖矩阵 (§1 - §22)

| 蓝图节 | 主题 | 状态 | 主要落地物 | 关键缺口 |
|---|---|---|---|---|
| §0 | 一句话定义 | ✅ 完成 | README.md tagline / PROJECT_STATUS §0 | — |
| §1 | 命名 (HelixMind) | ✅ resolved | 见 §0.5；2026-05-11 裁决最终工程名 NoeticBraid，HelixMind 仅作历史蓝图引用 | 后续文档不再混用；历史引用保留原名 |
| §2 | 项目总定位 | ⚠ 部分 | `docs/architecture/step3-5*.md` + 8 backend frozen routes + 17 backend schema names | UI/控制台前端 (noeticbraid-console) 仍未达到 v3.2 默认工作台 / 双 demo project 入口 |
| §3 | 完整心智模型 (两环+底盘+不搬运+红线) | ⚠ 部分 | 双仓库概念固化在 schemas (Task/RunRecord/SourceRecord/SideNote/DigestionItem/ApprovalRequest) | 两条成长环只有数据载体 (SideNote+DigestionItem)，无主动反思引擎 |
| §4.1 | AI 进化环 | ❌ 未开始 | RunRecord schema 含 `lesson_candidate_created` event_type；**`lessons` 字段不存在** (codex §1，实测 run_record.py) | 任务后反思生成器 / 程序记忆写入器 / failure_cases 抽象都未实现；详见 §20 字段对齐表 |
| §4.2 | 用户成长环 | ⚠ 部分 | user_growth_llmwiki 模块 (scanner/reuse/persistence) 已入库 | 反向投影 / 旁注质疑生成 / 报告体系 (日/周/月/年) 未实现 |
| §5 | 调度底盘总结构 | ⚠ 部分 | backend FastAPI app + storage factories + auth (DPAPI vault) | 任务分类器 / 工作流选择器 / 多模型路由器 / 上下文组装器 / Playwright/CLI runner 未实现 |
| §6 | 双仓库 + 一账本 | ⚠ 部分 | RunLedger (`noeticbraid_core/ledger/run_ledger.py`) + JSONL backend + 8 frozen routes (含 ledger aggregate); SourceIndex (`source_index/`) 落地；LOCK_SH reader 已 Phase 1.2 兑现 | 程序记忆仓库 / 情景记忆仓库 物理目录与索引器未独立实现；RunRecord 未连接真实 workflow 执行 |
| §7 | 多账号池 + quota | ⚠ partial | `account_quota/{enforcer,store,models}.py` + `api/routes/account.py` (commit `e45c169`)；**`QuotaStateRecord` 含 `remaining_estimate` / `usage_limit_estimate` / `_estimate_after_usage` / `would_limit` / `preflight_usage` 已落地** (codex §2) | 缺失：浏览器 profile 真实联通 / session health 检查 / browser-derived quota observation / 自动轮换调度 / context bundle 切换 |
| §8 | 多模型路由 + 辩论 | ✅ δ day-0 完成 | `noeticbraid/packages/noeticbraid-multimodel-alliance` + backend contract 1.3.0 `ModelRoute` schema name；SDD-D2-01 multimodel debate loop δ-B5 + hotfix-01 已合并（commit `e1649e5` + `c16bc88`），手工对抗辩论 + ledger/candidate 写入 + word-boundary mention scanner + env-override workspace path 全闭环 | candidate→confirmed 全局 gate 规则化（R-6 跨模块）留 Part 2.C #6 |
| §9 | 不搬运原则 | ⚠ partial | **`CliRunnerRegistry` / `CliRunnerSpec` 已 export from `noeticbraid_core.__init__`** (实测 __init__.py 第 22, 41 行) 作为白名单注册器 (codex §2) | Missing: execution runner (subprocess wrapper) / Playwright controller / browser_profiles / web_extractors |
| §10 | 神圣红线 | ✅ schema 完成 ／ opt-out UI 留 Part 2.C #4 | source_record.py 的 raw/source-only validator + `noeticbraid-obsidian` path/write policy；SDD-D1-01 SideNote §11.b.S metadata 5 项 + tone_constraint literal + user_response_channel 4 动作 + contract 2.0.0 并存已合并（commit `059ef91`） | opt-out 交互 UI（per-type disable / 3-rebut auto-降频 / 整体暂停 / first-note 同步显示入口）留 Part 2.C #4 (SDD-D2-05) |
| §11 | 信息收集中心 | ❌ 第一阶段延后 | `bestblogs_info_tracking` 已裁决归档为历史；第二阶段 RSS adapter 候选 | v3.2 §10.4 信息雷达不进第一阶段；无 GitHub / X / YouTube / arXiv / 专利 / NotebookLM 抓取 |
| §12 | NotebookLM 桥接 | ❌ 未开始 | — | 完全未实现 |
| §13.a | 文档写作链路 | ❌ 未开始 | — | 蓝图 §13 文档生产侧未实现 |
| §13.b | 代码生成链路 | ❌ 未开始 | — | 蓝图 §13 代码生产侧未实现 |
| §13.c | 代码评审标准 | ❌ 未开始 | — | 蓝图 §13 评审标准未沉淀为运行时规则 |
| §13.d | 产出归档 | ❌ 未开始 | — | 蓝图 §13 产出物归档闭环未实现 |
| §14 | Obsidian 管理中心 | ⚠ 部分入库 | `noeticbraid/packages/noeticbraid-obsidian` schemas/templates/path policy/writer；§11.b.S 加固 (D1-01) + b-1 detector candidate flow (D1-02) + P1 demo verified | Dashboard / 聊天调度入口 / 文件自动归档 / AI 旁注侧栏 / 报告自动生成未完整串通；opt-out 交互 UI 留 Part 2.C #4 |
| §15 | Telegram 推送 | ⚠ 降级为可选 adapter | 旧 Telegram prototype 归档；scheduler 主仓包为 `noeticbraid-workflow-scheduler` | 第一阶段只保留单通知渠道；Telegram adapter 不作为默认 runtime |
| §16 | Workflow 调度器 | ⚠ 部分入库 | `noeticbraid/packages/noeticbraid-workflow-scheduler` (`noeticbraid.tools.workflow_scheduler`) | v3.2 第一阶段只手工触发；autonomous/cron、多渠道 fanout 与完整 workflow 卡片体系留后续 |
| §17 | 全量功能落地清单 (6 子节) | ⚠ 归属裁决已落地 | 见 §2 矩阵 + `noeticbraid-workflow/MODULE_VERDICTS.md` | 旧 tools 归档；后续缺口转为 δ 的真实闭环 / SideNote 安全 / 可选 adapter 加固 |
| §18.1 | idea → 项目 端到端 | ❌ 未串通 | — | task_classifier + workflow_scheduler + model_router runtime 未实现 |
| §18.2 | 论文写作 端到端 | ❌ 未串通 | — | 文献检索 / 阅读 / 写作 / 审核 链路未串通 |
| §18.3 | 代码任务 端到端 | ❌ 未串通 | — | 任务理解 / 代码生成 / 评审 / 提交 链路未串通 |
| §18.4 | 周报 端到端 | ❌ 未串通 | — | 周内事件聚合 / 反思 / 报告生成 链路未串通 |
| §19 | 系统模块清单 (helixmind/core/...) | ⚠ 部分 | noeticbraid-core (schemas / ledger / source_index / guard / user_growth_llmwiki) + noeticbraid-backend (auth / approval / api / account_quota) | core/{task_classifier, workflow_scheduler, model_router, context_builder, convergence_engine}.py 未实现；automation/, telegram/, workflows/ 子树未建 |
| §20 | 关键数据对象 | ⚠ partial semantic coverage; field divergence remains | Backend contract 1.3.0 publishes 28 schema names（17 frozen 1.2.0 + 11 D2-02/D2-03 additive：WorkspaceProject / CapabilityRegistryEntry / CapabilityHealthResult / CandidateLesson 等）；SideNote v2 `CONTRACT_V2_VERSION=2.0.0` 由 SDD-D1-01 并存登记（含 5 项 §11.b.S 安全字段）；详见 §6 字段对齐表 | RunRecord 与蓝图 §20 聚合字段仍不对齐 |
| §21.a | 质量标准：调度质量 | ❌ 未实现 (runtime metric) | — | 仅 test-suite gates 存在；蓝图 §21 调度质量 runtime 指标未定义 |
| §21.b | 质量标准：产物质量 | ❌ 未实现 (runtime metric) | — | 仅 test-suite gates 存在；蓝图 §21 产物质量 runtime 指标未定义 |
| §21.c | 质量标准：记忆质量 | ❌ 未实现 (runtime metric) | — | 仅 test-suite gates 存在；蓝图 §21 记忆质量 runtime 指标未定义 |
| §21.d | 质量标准：成长质量 | ❌ 未实现 (runtime metric) | — | 仅 test-suite gates 存在；蓝图 §21 成长质量 (周报让用户看见模式) runtime 指标未定义 |
| §21 (test-suite) | CI / 守门 | ⚠ 部分 | 28 backend schema names + 14 route contract guard (8 frozen 1.2.0 + 6 D2-02/D2-03 additive) + leak scan + δ day-0 末 core 485 / backend 101 / multimodel-alliance 46 / console routes.test.tsx 12 pytest + CI gate | 仅覆盖 schema/契约/泄漏；不覆盖运行时调度/产物/记忆/成长；Playwright e2e 全部留 future-verify（无 headless browser env） |
| §22 | 最终产品形态 | ❌ 未达成 | — | 用户每天打开 Obsidian、聊天框发起任务、自动调度的端到端形态尚未形成 |
| §23 | 项目宣言 | ⚠ 故意不在矩阵范围 | 蓝图 §23 原文保留；本矩阵聚焦 §1-§22 vision-vs-implementation gap | intentionally outside §1-§22 vision matrix scope, see blueprint for original text |

---

## 4. Phase 进度时间线

### 已完成

- **Phase 1.1 Foundation Lock** — COMPLETE (tag `phase-1.1-complete`，commit `510350a`)
  - Stage 1 import (`b8d7152`，candidate tag `phase-1.1-stage1-candidate`) — PASS
  - Stage 1.5 Freeze (PR #1 → `4be314d`，tag `phase-1.1-contract-1.0.0`) — PASS (Codex S/M 本地补丁)
  - Stage 2 ledger (PR #3 → `ba8166b`) — PASS (consensus 2M deferred)
  - Stage 2 guard (PR #4 → `bcfa1a1`) — PASS
  - Stage 2 console (PR #5 → `bcc5502`) — PASS (1 vitest race + 1 src/README 本地补丁)
  - Stage 2 integration (PR #6 → `510350a`) — PASS (CI gate 全绿)

- **Phase 1.2 Stage 1 backend skeleton** — `5650751` (candidate tag `phase-1.2-stage1-candidate`) — v1 REVISE → v2 PROCEED；15 pytest pass；OpenAPI 13 schemas

- **Phase 1.2 Stage 1.5 contract freeze** — tag `phase-1.2-contract-1.1.0` (commit `de90178`) — historical freeze；后续 backend API authoritative version 已到 `1.2.0`

- **Phase 1.2 Stage 2 (4 sub-stages)** — COMPLETE (tag `phase-1.2-stage-2-complete`，commit `32f3882`)
  - Stage 2.1 ledger storage backend → `e5d4ad0` (tag `phase-1.2-stage-2.1-candidate`)
  - Stage 2.2 guard auth approval backend → `9f276c7` (tag `phase-1.2-stage-2.2-candidate`)
  - Stage 2.3 console read API backend → `7f88f2a` (tag `phase-1.2-stage-2.3-candidate`)
  - Stage 2.4 integration seal → `32f3882`
  - Historical final gates: pytest core 398 / backend 55 / root 9 PASS；contract gate 7 paths 13 schemas；smoke 7 endpoints

- **Contract follow-ups**
  - `phase-1.2-contract-1.2.0` → `3224aa7`：backend API contract version `1.2.0`，8 frozen routes / 17 schema names
  - `phase-1.2-contract-1.3.0` → `9965e1c`：Obsidian sidecar/schema freeze；backend API `CONTRACT_VERSION` remains `1.2.0`

- **Module / SP integrations** — 部分进入主仓，部分裁决归档
  - account_quota → legacy `e45c169` / current SP-C1 integration `b11f203` (tag `phase-1.2-SP-C1-account-quota-1.0.0`) ✅
  - user_growth_llmwiki → `41aecb3` (tag `module-user-growth-llmwiki-v0`) ✅
  - runtime → `5faef09` / `8933bd1` (tag `phase-1.2-SP-C2-runtime-1.0.0`) ✅
  - obsidian_hub → `44d04c7` (tag `phase-1.2-SP-D-obsidian-1.0.0`) ✅ main package exists; §11.b.S 加固 δ day-0 完成 (D1-01 / D1-02 / D1-01-hotfix-01)
  - notebooklm_bridge → `e2a9a6f` / `2a9e91f` (tag `phase-1.2-SP-H-notebooklm-1.0.0`) ✅ **[SUPERSEDED & REMOVED 2026-05-14 by SDD-D5-07 commit `9dcae5d`]** — browser-automation 路线退役，由 `noeticbraid-notebooklm-rpc`（D5-01..06）完整替代；历史里程碑保留供审计回溯
  - multimodel_alliance → `c36cb17` ✅ main package exists；真实辩论闭环 δ day-0 完成 (D2-01 + hotfix-01: `e1649e5` / `c16bc88`)
  - workflow_scheduler_telegram → `33b1d55` / `91fdd77` (tag `phase-1.2-SP-E-scheduler-1.0.0`) ✅ scheduler main package exists; Telegram optional adapter
  - bestblogs_info_tracking → v3.2 §10.4 裁决为历史归档 + 第二阶段 adapter 候选

- **δ demo day-0 SDD closures (2026-05-12)** — 5 SDD + 1 hotfix + 1 doc-hotfix bundle
  - SDD-D1-01 SideNote §11.b.S Metadata 加固 + contract 2.0.0 并存 → commit `059ef91` (γ 末)
  - SDD-D1-02 b-1 detector：项目提到 ≥3 distinct days 但未推进 → SideNote candidate → commit `a82ed88`
  - SDD-D2-01 multimodel debate loop + candidate-first ledger 写入 → commit `e1649e5`
  - SDD-D2-01-hotfix-01 (3 sonnet δ-B6 LOW polish: cli parens / env-override workspace / word-boundary regex) → commit `c16bc88`
  - SDD-D2-02 OMC ingestion 工作台 minimum-demo-pass (Part 2.C #1) → commit `b2ee841`，backend contract minor bump 1.2.0 → 1.3.0
  - SDD-D2-03 capability 4-端 real health-check (Part 2.C #2 + §10.4 item 1 demo) → commit `f06b044`
  - SDD-D1-02-hotfix-02 doc-only spec wording polish (P1 demo dry-run granularity gap) → 无 commit（spec 区域非 git tree）

- **D5 系列 closures (2026-05-14, δ demo day-2)** — NotebookLM browser→RPC 迁移，7 SDD 全程 dual-review（codex spec-review 多轮 + code-reviewer impl-review）
  - SDD-D5-01 RPC foundation + 多账号 pool（account_op / run_with_pool）→ committed（基线 `d02e65d` 含 hotfix-01 `1f626ea`）
  - SDD-D5-02 artifacts 生成：ArtifactKind taxonomy + serializer + 11 generate-and-download composites → committed（含 hotfix-02 `05bb624`）
  - SDD-D5-03 notebook lifecycle + sharing serializer + 2 composites → commit `d02e65d`（含 retroactive rev4 doc note）
  - SDD-D5-04 sources serializer + 2 frozen mappings + 4 add-and-serialize composites（`__all__` 38→46）→ commit `de71ecd`（5 spec-review 轮 + retroactive rev5 accepted-drift）
  - SDD-D5-05 note serializer + 2 note composites + 1 chat composite（research 显式 deferred；`__all__` 46→53）→ commit `6e12535`（2 spec-review 轮）
  - SDD-D5-06 `revise_slide_and_serialize` composite + artifact-lifecycle error（settings + 单步 lifecycle 全 out-of-scope；`__all__` 53→55）→ commit `7b21faa`（2 spec-review 轮）
  - SDD-D5-07 删除 `noeticbraid-notebooklm-bridge` 包（R-6 授权退役：0 消费者 + 被 D5-01..06 完整替代 + browser-automation 路线被否决；workspace 8→7 包）→ commit `9dcae5d`
  - 净效果：新包 `noeticbraid-notebooklm-rpc` `__all__` 55；notebooklm-rpc pytest 323 PASS；6-包计量峰值 1124 → 删 bridge 后 1100；全 frozen contract byte-equal；4 次 forward-compat test-drift 经 pre-declare / retroactive-accept pattern 处理

### 当前

`PROJECT_DEFINITION_v3.2.md` 已取代旧蓝图作为 spec source of truth。δ demo day-0 (2026-05-12) 已闭环 5 SDD + 1 hotfix（D1-01 / D1-02 / D2-01 + hotfix-01 / D2-02 / D2-03）+ D1-02-hotfix-02 doc-only polish；剩余 Part 2.C #4 (SideNote opt-out 交互) / #6 (candidate→confirmed gate 全局化) / #7 (External Reference Pool 边界) 在 δ day-0 内继续推进。14-day demo timer day-14=2026-05-26。

### 计划

- δ 阶段剩余 Part 2.C：
  - #4 SideNote opt-out 交互 UI (SDD-D2-05)：per-type disable / 3-rebut auto-降频 / 整体暂停 / first-note 同步显示入口
  - #6 candidate→confirmed gate 全局化 (SDD-D2-04)：显式用户采纳 OR ≥3 复用 + ≥1 ledger 证据，跨 tracked_project / lesson_candidate / omc adoption 三表面
  - #7 External Reference Pool v3.2 边界：SP-A radar scope 裁为 AI 元知识 only（institutional research DBs / 领域知识 → 第二阶段）
- δ 阶段：把 scheduler 第一阶段降级为手工触发 + 单通知渠道；Telegram 保持 optional adapter
- 第一阶段双 demo：OMC demo + AI 旁注追踪 demo；工作台需最小 project / chat / health / SideNote 可见面
- 第二阶段或更后：信息雷达自动抓取、多源 RSS adapter、完整 capability registry（版本系统 + manual patch workflow）、cron/autonomous 调度、NotebookLM 深接入、Playwright headless e2e 真跑

---

## 5. 已知缺口 (按蓝图分类)

### AI 进化环 (§4.1)

- (§4.1.1) 任务后主动反思引擎未实现；**`RunRecord.lessons` 字段不存在** (codex §1，实测 run_record.py)；当前仅有 `lesson_candidate_created` event_type 标记，没有 `lessons` 数据字段承接反思内容
- (§4.1.3) 程序记忆抽象方法论生成器未实现
- (§4.1.4) `/program_memory/` 物理目录 (workflows / prompt_cards / model_routes / checklists / failure_cases / experiments) 未创建
- (§4.1.5) 候选经验区 vs 核心程序记忆区的证据门控未实现

### 用户成长环 (§4.2)

- (§4.2.2) 反向投影引擎未实现 (现有 SideNote schema 仅是数据载体)
- (§4.2.3) 旁注质疑三层 (事实 / 解释 / 行动) 生成器未实现
- (§4.2.4) DigestionItem schema 已就绪，但追踪状态机 (active / resolved / recurring) 未串通
- (§4.2.5) 报告体系 (日 / 周 / 月 / 年) 全部未实现；user_growth_llmwiki 仅做 scanner+persistence，未做投影

### 调度底盘 (§5 - §8 + §16)

- (§5) 任务分类器 / 工作流选择器 / 上下文组装器 / 收敛引擎 / 记忆写入器 模块均未在 noeticbraid-core 创建
- (§6.1) 程序记忆仓库目录树未建
- (§6.2) 情景记忆仓库目录树未建
- (§6.3) 运行账本 schema (RunRecord) 已在 backend contract 1.2.0 schema names 中发布，但 runtime 未连接真实任务执行
- (§7.2) 账号池对象模型 (browser_profile / session_health / preferred_tasks) 已落 account_quota 模型，但 browser_profile 字段未联通真实 Chrome profile
- (§7.4) 自动轮换策略仅 quota 估算，未做能力匹配 / 切换成本评估
- (§7.5) context bundle 切换器未实现
- (§7.6) 账号池控制台 (Obsidian Account Pool Dashboard) 未实现
- (§8.2) 模型路由 router runtime 未实现；ModelRoute 尚未进入 contract
- (§8.3) 辩论收敛引擎未实现，仅在 multimodel_alliance schemas 层有定义
- (§8.4) Final Convergence Report 模板未落地
- (§16) Workflow 卡片格式 (yaml) 未在 noeticbraid 落地；现 workflow_scheduler_telegram 仅最小 state machine

### 不搬运 (§9)

- (§9.3) Web 端 Playwright 闭环 0% 实现 (无 playwright_controller / browser_profiles / web_extractors)
- (§9.4) CLI 端 subprocess runner 0% 实现 (除 guard/cli_runner_registry.py 占位外)
- (§11.4) 学术数据库脚本 / 专利查新脚本未实现
- (§12) NotebookLM 桥接器未实现
- (§14.3) Obsidian 聊天调度入口未实现
- (§15.3) Telegram 交互命令集仅占位

### 红线 (§10)

- (§10.1) 用户原始记录写入区 (10_user_raw/) 物理目录未在 vault 落地
- (§10.2) AI 旁注 metadata (依据 / 类型 / 置信度 / 用户认可) 已在 SideNote schema 定义，但 vault 写入器未实现
- (§10.3) AI 起草不默认发送 / 不默认决定的执行守卫已部分落地 (guard/mode_enforcer.py + Decision)，但未连接真实发送链路

---

## 6. 数据对象 (§20) 缺口

### 6.1 实体级别对齐

蓝图 §20 列出 5 个关键数据对象；backend contract 1.2.0 当前发布 17 个 schema names，其中核心实体 / sidecar 对齐如下：

| 蓝图 §20 | noeticbraid contract state | 备注 |
|---|---|---|
| Task | ✅ Task | partial semantic coverage; field divergence remains |
| Workflow | ✅ Workflow | backend contract 1.2.0 已有 schema name；runtime workflow card / scheduler 映射仍未完整串通 |
| ModelRoute | ✅ ModelRoute | backend contract 1.2.0 已有 schema name；multimodel runtime 已入主仓，但真实辩论闭环 + ledger/candidate 留 δ |
| RunRecord | ⚠ shape mismatch | 蓝图为聚合记录；shipped 为 append-only event；另有 `RunRecordAggregate` wrapper；详见 6.2 字段表 |
| SideNote | ⚠ SideNote | 基础实体存在；v3.2 §11.b.S 的 metadata / opt-out / tone 安全字段仍需 δ 加固 |
| (蓝图未列) | ✅ SourceRecord | noeticbraid 拓展 |
| (蓝图未列) | ✅ ApprovalRequest | noeticbraid 拓展 |
| (蓝图未列) | ✅ DigestionItem | noeticbraid 拓展 |
| (蓝图未列) | ✅ VaultLayoutMinimum | Obsidian path-policy sidecar |

### 6.2 RunRecord 字段对齐表 (codex §1 critical fix)

**Shipped fields** (实测 `packages/noeticbraid-core/src/noeticbraid_core/schemas/run_record.py`):
`run_id` / `task_id` / `event_type` / `created_at` / `actor` / `model_refs` /
`source_refs` / `artifact_refs` / `routing_advice` / `status`。

`event_type` 取值含 `task_created` / `task_classified` / `context_built` /
`approval_requested` / `approval_decision_recorded` / `web_ai_call_requested` /
`profile_health_checked` / `source_record_linked` / `artifact_created` /
`security_violation` / **`lesson_candidate_created`** / **`routing_advice_recorded`** /
`task_completed` / `task_failed`。

**Blueprint §20 wants** (HelixMind 蓝图原文): `run_id` / `task_id` / `workflow_id` /
`models_used` / `accounts_used` / `sources_used` / `artifacts_created` / `quota_cost` /
`errors` / `user_feedback` / `lessons`。

| Blueprint §20 field | Shipped equivalent | Status | 备注 |
|---|---|---|---|
| `run_id` | `run_id` | ✓ | 同名同义 |
| `task_id` | `task_id` | ✓ | 同名同义 |
| `workflow_id` | (none in RunRecord) | ❌ | Workflow schema 已存在，但 RunRecord 事件模型仍缺 workflow_id 字段 |
| `models_used` | `model_refs: list[str]` | ⚠ | 仅引用 ID，无 usage 量 / role / verdict |
| `accounts_used` | (none) | ❌ | 多账号池信息未挂入 ledger |
| `sources_used` | `source_refs: list[str]` | ⚠ | 仅引用 ID |
| `artifacts_created` | `artifact_refs: list[str]` | ⚠ | 仅引用 ID |
| `quota_cost` | (none) | ❌ | quota 消耗未在 ledger 记录 |
| `errors` | `event_type=task_failed` / `security_violation` 标记 | ⚠ | 只有事件标记，没有结构化 errors 列表 |
| `user_feedback` | (none) | ❌ | 用户反馈通道未在 RunRecord 落地 |
| `lessons` | `event_type=lesson_candidate_created` (marker only) | ⚠ | **lessons 不存在为字段**；仅作为 event_type 标记 (codex §1) |
| (Shipped extra) `event_type` | — | — | shipped 额外字段：append-only event 模型 |
| (Shipped extra) `actor` | — | — | shipped 额外字段：user / system / model / local_review |
| (Shipped extra) `routing_advice` | — | — | shipped 额外字段：路由建议文本 |
| (Shipped extra) `status` | — | — | shipped 额外字段：draft / recorded / failed |

**结论**：shape 不一致 — 蓝图 RunRecord 是单任务聚合；shipped RunRecord 是
append-only event 流。要满足蓝图 §20 / §4.1.2-§4.1.4 需要：(1) 聚合视图或新 schema；
(2) 引入 workflow_id / accounts_used / quota_cost / errors / user_feedback / lessons
真实字段。

---

## 7. 模块归属裁决记录

2026-05-11 γ 阶段已将 4 个未入库模块的归属裁决登记到
`noeticbraid-workflow/MODULE_VERDICTS.md`，并将旧原型移动到
`noeticbraid-workflow/archive/tools-legacy/`。

后续不再把 `noeticbraid-workflow/tools/` 视为 runtime 来源；δ 阶段只处理已登记的
真实闭环 / SideNote 安全 / optional adapter 加固，不在 γ 阶段做代码迁移。
