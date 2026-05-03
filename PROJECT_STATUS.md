# NoeticBraid 项目状态矩阵 (PROJECT_STATUS)

> Single source of truth for vision-vs-implementation gap. Generated 2026-05-02.
> Source-of-truth blueprint: `项目文档/HelixMind_Project_Blueprint_Package/HelixMind_Project_Blueprint_CN.md`

## 0. 一段话愿景

NoeticBraid (内部代号 HelixMind / HBA) 不重造大模型，而是站在主流 AI 工具
(ChatGPT / Claude / Gemini / Codex / NotebookLM / Obsidian / GitHub / 浏览器 / CLI)
之上的一层 **个人 AI 调度、记忆、反思与共同进化系统**。核心公式：
**两条成长环 (AI 进化环 + 用户成长环) + 一套调度底盘 (双仓库 + 一账本 + 多账号池
+ 多模型路由辩论 + Workflow 调度器) + 一条不搬运原则 (Playwright + subprocess
全闭环) + 两条神圣红线 (用户原始记录神圣 / 用户主体地位神圣)**。Tagline：
让 AI 越用越准，让人越用越清醒。

## 0.5 命名分歧说明 (Naming Divergence — Unresolved)

**Status: documented, naming divergence unresolved — no decision recorded.**

蓝图 §1.3 (`项目文档/HelixMind_Project_Blueprint_Package/HelixMind_Project_Blueprint_CN.md`)
确定项目最终英文名为 **HelixMind**；但 repo / workflow 当前权威名称仍是
**NoeticBraid** (见 `README.md` / `AGENTS.md` / `docs/architecture/step3_authority.md`)。
两套命名并存，无任何决策记录指明哪一方覆盖另一方 (no commit / decision log / ADR
records "NoeticBraid supersedes HelixMind" or vice versa)。本文档其余部分仍沿用
当前权威命名 NoeticBraid，但所有蓝图引用保留 HelixMind 原文，待 main session
明确定名后统一。

## 1. 当前快照

| 字段 | 值 |
|---|---|
| 当前阶段 | Phase 1.2 Stage 2 已完成 (sub-stage 2.4)；后续进入 modules dispatch phase |
| 最后 noeticbraid commit (HEAD) | `ade6855` |
| 最近 module integration commits | `41aecb3` (user_growth_llmwiki) → `e45c169` (account_quota) → `32f3882` (Stage 2 seal) |
| 当前 contract version | `1.1.0` (frozen at tag `phase-1.2-contract-1.1.0`) |
| 主要 tag | `phase-1.1-complete` (510350a) / `phase-1.2-stage-2-complete` (32f3882) / `module-account-quota-v0` / `module-user-growth-llmwiki-v0` |
| Backend endpoints | 7 (auth / approval / ledger / dashboard / account / health / workspace) |
| Schemas (contract 1.1.0) | 13 OpenAPI schemas |
| pytest core | PASS 408 |
| pytest backend | PASS 72 |
| CI 最近一次跑 | run `25267021996` 全绿 |
| pending_actor (state.json) | `main_session_dispatch_module_phase` |

---

## 2. §17 全量功能落地清单 → 6 模块矩阵

每个模块的状态拆为两列：
- **(a) v3.3 artifact exists**：是否产出了 prompt/bundle/reviews/integration_report 等 v3.3 工件
- **(b) shipped in noeticbraid git**：是否产生真实 noeticbraid commit + tag + audit_trail row

| 蓝图小节 | 模块名 | (a) v3.3 artifact exists | (b) shipped in noeticbraid git | 双评 A/B verdict | 当前位置 |
|---|---|---|---|---|---|
| §17.1 信息收集与研究 | **bestblogs_info_tracking** | ⚠ partial — scanner / RSS / OPML 实现 + 13 pytest pass + integration_report；**no Reviewer A artifact in v3.3 archive** (codex §1) | ❌ FALSE — 未提交 noeticbraid，state.json `step=integrated` 仅指 GPT5_Workflow 本地；无 commit / tag / audit_trail row | ⚠ 仅 reviewer B (`reviews/reply_reviewer_B.md` + `reviews/reviewer_B.md`)；无 reviewer A | `GPT5_Workflow/tools/bestblogs_info_tracking/` |
| §17.2 多模型联合 | **multimodel_alliance** | ✅ TRUE — schemas (model_route / debate / convergence) + 3 fixtures + 7 pytest pass + reviewer A + reviewer B + reply_B + integration_report | ❌ FALSE — `integration_report.md` 明确说 "GPT5_Workflow is not a local git repository"；无 commit / tag / audit_trail row | ⚠ reviewer A + reviewer B + reply_B 全部 CONCERN-class | `GPT5_Workflow/tools/multimodel_alliance/` |
| §17.3 账号与 quota 管理 | **account_quota** | ✅ TRUE — design + reviews + reply + integration_report 全套 v3.3 工件 | ✅ TRUE — commit `e45c169`，tag `module-account-quota-v0`，audit_trail.md 第 14 行 (commit `64cec72`) | ✅ A=APPROVE 1MED+2LOW；B=CONDITIONAL PASS 1MAJ+3MIN | `noeticbraid/packages/noeticbraid-backend/src/noeticbraid_backend/account_quota/` + `api/routes/account.py` |
| §17.4 Obsidian 中心 | **obsidian_hub** | ⚠ partial — 6 schemas + 7 templates + write_policy + vault_layout + validator + 11 pytest pass + integration_report；**no Reviewer A artifact in v3.3 archive** (codex §1) | ❌ FALSE — state.json 标 `step=archived`，commit/tag/push gate 显式被阻断 (GPT5_Workflow is not a git repo)；无 commit / tag / audit_trail row | ⚠ 仅 reviewer B + reply_B (`reviews/`) | `GPT5_Workflow/tools/obsidian_hub/` |
| §17.5 用户成长系统 | **user_growth_llmwiki** | ✅ TRUE — design + reviews + reply + integration_report 全套 v3.3 工件 | ✅ TRUE — commit `41aecb3`，tag `module-user-growth-llmwiki-v0`，audit_trail.md 第 15 行 (commit `80dcf15`) | ✅ A=COMMENT 2MED+2LOW；B=REQUEST CHANGES 2HIGH+2MED | `noeticbraid/packages/noeticbraid-core/src/noeticbraid_core/user_growth_llmwiki/` + `docs/modules/user_growth_llmwiki/` |
| §17.6 自动化底盘 | **workflow_scheduler_telegram** | ✅ TRUE — runner state machine + JSONL events + telegram rate cap + 10 pytest pass + reviewer A + reviewer B + reply_A + reply_B + integration_report | ❌ FALSE — 未提交 noeticbraid；无 commit / tag / audit_trail row | ⚠ reviewer A + reviewer B + reply_A + reply_B (CONCERN-class) | `GPT5_Workflow/tools/workflow_scheduler_telegram/` |

**汇总**：v3.3 工件维度上，4/6 模块 (multimodel_alliance / account_quota /
user_growth_llmwiki / workflow_scheduler_telegram) 完整产出双评 + integration；
2/6 (bestblogs / obsidian) 缺 Reviewer A artifact。在 noeticbraid git 入库维度上，
仅 2/6 (account_quota + user_growth_llmwiki) 为 TRUE，其余 4 个模块停留在
GPT5_Workflow 本地，等待 main session 关于 GPT5_Workflow vs noeticbraid
模块仓库归属的最终决策。

---

## 3. 蓝图全章节覆盖矩阵 (§1 - §22)

| 蓝图节 | 主题 | 状态 | 主要落地物 | 关键缺口 |
|---|---|---|---|---|
| §0 | 一句话定义 | ✅ 完成 | README.md tagline / PROJECT_STATUS §0 | — |
| §1 | 命名 (HelixMind) | ⚠ documented, naming divergence unresolved | 见 §0.5；蓝图 §1.3 定名 HelixMind，repo/workflow 当前用 NoeticBraid (`AGENTS.md` / `README.md`) | 无 commit / decision log 记录哪一方覆盖另一方；待 main session 定名 |
| §2 | 项目总定位 | ⚠ 部分 | `docs/architecture/step3-5*.md` + 7 backend endpoints + 6 schema entities | UI/控制台前端 (noeticbraid-console) 仅占位 README，非 Obsidian/Web 入口实现 |
| §3 | 完整心智模型 (两环+底盘+不搬运+红线) | ⚠ 部分 | 双仓库概念固化在 schemas (Task/RunRecord/SourceRecord/SideNote/DigestionItem/ApprovalRequest) | 两条成长环只有数据载体 (SideNote+DigestionItem)，无主动反思引擎 |
| §4.1 | AI 进化环 | ❌ 未开始 | RunRecord schema 含 `lesson_candidate_created` event_type；**`lessons` 字段不存在** (codex §1，实测 run_record.py) | 任务后反思生成器 / 程序记忆写入器 / failure_cases 抽象都未实现；详见 §20 字段对齐表 |
| §4.2 | 用户成长环 | ⚠ 部分 | user_growth_llmwiki 模块 (scanner/reuse/persistence) 已入库 | 反向投影 / 旁注质疑生成 / 报告体系 (日/周/月/年) 未实现 |
| §5 | 调度底盘总结构 | ⚠ 部分 | backend FastAPI app + storage factories + auth (DPAPI vault) | 任务分类器 / 工作流选择器 / 多模型路由器 / 上下文组装器 / Playwright/CLI runner 未实现 |
| §6 | 双仓库 + 一账本 | ⚠ 部分 | RunLedger (`noeticbraid_core/ledger/run_ledger.py`) + JSONL backend + 7 endpoints; SourceIndex (`source_index/`) 落地；LOCK_SH reader 已 Phase 1.2 兑现 | 程序记忆仓库 / 情景记忆仓库 物理目录与索引器未独立实现；RunRecord 未连接真实 workflow 执行 |
| §7 | 多账号池 + quota | ⚠ partial | `account_quota/{enforcer,store,models}.py` + `api/routes/account.py` (commit `e45c169`)；**`QuotaStateRecord` 含 `remaining_estimate` / `usage_limit_estimate` / `_estimate_after_usage` / `would_limit` / `preflight_usage` 已落地** (codex §2) | 缺失：浏览器 profile 真实联通 / session health 检查 / browser-derived quota observation / 自动轮换调度 / context bundle 切换 |
| §8 | 多模型路由 + 辩论 | ⚠ 仅 schema | tools/multimodel_alliance schemas (model_route/debate/convergence) + fixtures + validator | 未入库 noeticbraid；无辩论收敛引擎；无 router runtime；ModelRoute 未列入 contract |
| §9 | 不搬运原则 | ⚠ partial | **`CliRunnerRegistry` / `CliRunnerSpec` 已 export from `noeticbraid_core.__init__`** (实测 __init__.py 第 22, 41 行) 作为白名单注册器 (codex §2) | Missing: execution runner (subprocess wrapper) / Playwright controller / browser_profiles / web_extractors |
| §10 | 神圣红线 | ⚠ 部分 | source_record.py 的 raw/source-only validator + obsidian_hub write_policy | 整体 vault 写入闭环未启用；旁注独立目录策略仅 schema 层 |
| §11 | 信息收集中心 | ⚠ 部分 | bestblogs_info_tracking (RSS/OPML scanner) | 未入库 noeticbraid；无 GitHub trending / X / YouTube / arXiv / 专利 / NotebookLM 抓取；无信息源评分与噪声过滤 |
| §12 | NotebookLM 桥接 | ❌ 未开始 | — | 完全未实现 |
| §13.a | 文档写作链路 | ❌ 未开始 | — | 蓝图 §13 文档生产侧未实现 |
| §13.b | 代码生成链路 | ❌ 未开始 | — | 蓝图 §13 代码生产侧未实现 |
| §13.c | 代码评审标准 | ❌ 未开始 | — | 蓝图 §13 评审标准未沉淀为运行时规则 |
| §13.d | 产出归档 | ❌ 未开始 | — | 蓝图 §13 产出物归档闭环未实现 |
| §14 | Obsidian 管理中心 | ⚠ 部分 | tools/obsidian_hub schemas + templates + write_policy | 未入库 noeticbraid；Dashboard / 聊天调度入口 / 文件自动归档 / AI 旁注侧栏 / 报告自动生成 全部未实现 |
| §15 | Telegram 推送 | ⚠ 部分 | tools/workflow_scheduler_telegram/telegram.py (rate cap + disabled-by-default) | 未入库 noeticbraid；无完整命令集 (/summary_today /show_radar /approve_task ...)；推送强度策略未实现 |
| §16 | Workflow 调度器 | ⚠ 部分 | tools/workflow_scheduler_telegram/runner.py (state machine + events.py) | 未入库 noeticbraid；reactive 主路径仅 cards.py 占位；autonomous 信息收集路径未实现；workflow 卡片体系未落地 |
| §17 | 全量功能落地清单 (6 子节) | ⚠ 4/6 工件齐全 / 2/6 入库 noeticbraid | 见 §2 矩阵；bestblogs / obsidian 缺 Reviewer A artifact | 4 模块 (bestblogs / multimodel / obsidian / scheduler) 仍在 GPT5_Workflow tools/ 待决策 |
| §18.1 | idea → 项目 端到端 | ❌ 未串通 | — | task_classifier + workflow_scheduler + model_router runtime 未实现 |
| §18.2 | 论文写作 端到端 | ❌ 未串通 | — | 文献检索 / 阅读 / 写作 / 审核 链路未串通 |
| §18.3 | 代码任务 端到端 | ❌ 未串通 | — | 任务理解 / 代码生成 / 评审 / 提交 链路未串通 |
| §18.4 | 周报 端到端 | ❌ 未串通 | — | 周内事件聚合 / 反思 / 报告生成 链路未串通 |
| §19 | 系统模块清单 (helixmind/core/...) | ⚠ 部分 | noeticbraid-core (schemas / ledger / source_index / guard / user_growth_llmwiki) + noeticbraid-backend (auth / approval / api / account_quota) | core/{task_classifier, workflow_scheduler, model_router, context_builder, convergence_engine}.py 未实现；automation/, telegram/, workflows/ 子树未建 |
| §20 | 关键数据对象 | ⚠ partial semantic coverage; field divergence remains | Task / RunRecord (event-shaped) / SourceRecord / ApprovalRequest / SideNote / DigestionItem (6 contract entities @ 1.1.0)；详见 §6 字段对齐表 | **Workflow / ModelRoute 未 schema 化**；RunRecord 与蓝图 §20 字段不对齐 (workflow_id / accounts_used / quota_cost / errors / user_feedback / lessons 全部缺失) |
| §21.a | 质量标准：调度质量 | ❌ 未实现 (runtime metric) | — | 仅 test-suite gates 存在；蓝图 §21 调度质量 runtime 指标未定义 |
| §21.b | 质量标准：产物质量 | ❌ 未实现 (runtime metric) | — | 仅 test-suite gates 存在；蓝图 §21 产物质量 runtime 指标未定义 |
| §21.c | 质量标准：记忆质量 | ❌ 未实现 (runtime metric) | — | 仅 test-suite gates 存在；蓝图 §21 记忆质量 runtime 指标未定义 |
| §21.d | 质量标准：成长质量 | ❌ 未实现 (runtime metric) | — | 仅 test-suite gates 存在；蓝图 §21 成长质量 (周报让用户看见模式) runtime 指标未定义 |
| §21 (test-suite) | CI / 守门 | ⚠ 部分 | 13 schemas + contract_diff 守门 + leak scan + 408+72 pytest 覆盖 + CI gate | 仅覆盖 schema/契约/泄漏；不覆盖运行时调度/产物/记忆/成长 |
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

- **Phase 1.2 Stage 1.5 contract freeze** — tag `phase-1.2-contract-1.1.0` (commit `de90178`) — contract 升级 1.0.0 → 1.1.0

- **Phase 1.2 Stage 2 (4 sub-stages)** — COMPLETE (tag `phase-1.2-stage-2-complete`，commit `32f3882`)
  - Stage 2.1 ledger storage backend → `e5d4ad0` (tag `phase-1.2-stage-2.1-candidate`)
  - Stage 2.2 guard auth approval backend → `9f276c7` (tag `phase-1.2-stage-2.2-candidate`)
  - Stage 2.3 console read API backend → `7f88f2a` (tag `phase-1.2-stage-2.3-candidate`)
  - Stage 2.4 integration seal → `32f3882`
  - Final gates: pytest core 398 / backend 55 / root 9 PASS；contract gate 7 paths 13 schemas；leak scan 187 files；smoke 7 endpoints

- **Module Phase (Stage 2 后续 dispatch)** — 部分完成
  - account_quota → `e45c169` (tag `module-account-quota-v0`，audit `64cec72`) ✅
  - user_growth_llmwiki → `41aecb3` (tag `module-user-growth-llmwiki-v0`，audit `80dcf15`) ✅
  - multimodel_alliance / obsidian_hub / workflow_scheduler_telegram / bestblogs_info_tracking → 设计 + 实现 + 集成本地 ✅，但 **未提交 noeticbraid，未登记 audit_trail**

### 当前

`pending_actor = main_session_dispatch_module_phase`：等待 main session 决定
4 个未入库模块的归属 (是迁入 noeticbraid 还是保留在 GPT5_Workflow tools/)。

### 计划

- 决定 4 模块仓库归属，更新 `docs/audit_trail_proposed_additions.md` → `audit_trail.md`
- 串通 §18.1-18.4 端到端 workflow，引入 task_classifier + workflow_scheduler + model_router runtime
- 引入 Playwright controller + CLI runner (§9 不搬运闭环)
- 实现 §4.1 任务后反思 + 程序记忆写入器
- 实现 §11 信息雷达多源 (GitHub / X / arXiv) 与评分
- 实现 §12 NotebookLM 桥接
- contract 升级到 1.2.0 引入 Workflow + ModelRoute schema (§20 缺口)

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
- (§6.3) 运行账本 schema (RunRecord) 已 1.1.0 frozen，但 runtime 未连接真实任务执行
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

蓝图 §20 列出 5 个关键数据对象，noeticbraid contract 1.1.0 提供 6 个：

| 蓝图 §20 | noeticbraid contract 1.1.0 | 备注 |
|---|---|---|
| Task | ✅ Task | partial semantic coverage; field divergence remains |
| Workflow | ❌ **缺失** | 需 contract 1.2.0 引入 |
| ModelRoute | ❌ **缺失** | tools/multimodel_alliance 有 schema 草稿；待入库 |
| RunRecord | ⚠ shape mismatch | 蓝图为聚合记录；shipped 为 append-only event；详见 6.2 字段表 |
| SideNote | ✅ SideNote | partial semantic coverage; field divergence remains |
| (蓝图未列) | ✅ SourceRecord | noeticbraid 拓展 |
| (蓝图未列) | ✅ ApprovalRequest | noeticbraid 拓展 |
| (蓝图未列) | ✅ DigestionItem | noeticbraid 拓展 |

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
| `workflow_id` | (none) | ❌ | Workflow 实体本身未 schema 化 |
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

## 7. 模块入库决策待办

参见 `docs/audit_trail_proposed_additions.md`：4 行 proposed audit_trail rows
等待 main session 决定 4 个未入库模块 (bestblogs / multimodel / obsidian / scheduler)
是否迁入 noeticbraid。
