# Stage 2 Console zip 一审 (Claude Opus critic)

## 总判
PASS — 0D / 0S / 1M / 2L 一句话总评：v3 强约束（独立 routeTree.ts、MSW 2.x 5 handlers、4 routes、16 deps 全 caret、types NOTE 注 1.0.0+b8d7152、fixtures 仅业务字段、Phase 1.2/1.3 不暴露 auth/account 路由）全数对齐；唯一可记账的瑕疵是 package.json `description` 仍写 "Stage 0 placeholder"，属可后续修订的轻量 bug。

## 14 自检项判定

| # | 项 | 实际 | 证据 (file:line / SHA) |
|---|---|---|---|
| 1 | routes 对齐 OpenAPI 5 endpoints | PASS | `src/routes/__root.tsx:7-10` (Dashboard/Workspace/Runs/Approvals 4 nav links) + `src/routes/routeTree.ts:7-12` (4 children) + `src/routes/{index,workspace,runs,approvals}.tsx` 各定义路径 `/`, `/workspace`, `/runs`, `/approvals` |
| 2 | package.json 无 latest（4 deps + 12 devDeps = 16，全 caret） | PASS | `packages/noeticbraid-console/package.json:16-35` 4 deps（react, react-dom, @tanstack/react-query, @tanstack/react-router）+ 12 devDeps；全部 `^MAJOR.MINOR.0`，无 `latest` |
| 3 | MSW handlers 5 个 | PASS | `src/mocks/handlers.ts:8-20` 恰好 5 个 `http.get`（health, dashboard/empty, workspace/threads, ledger/runs, approval/queue） |
| 4 | vitest 6 + playwright 4 + typecheck 执行 | BLOCKED（已诚实声明） | `manifest.md:256-269` 沙箱无 pnpm + DNS；本机另跑 |
| 5 | types/contracts.ts NOTE 引用 1.0.0 + b8d7152 | PASS | `src/types/contracts.ts:5-9` 明列 contract_version 1.0.0 + stage1_implementation_commit b8d7152 |
| 6 | fixtures 字段对齐 OpenAPI（不复制元字段） | PASS | `dashboard_empty.json:1-5` / `threads.json` / `runs.json` / `approvals.json` 均无 `$schema_status` / `contract_version`；仅业务字段 |
| 7 | reuse_log 14 新候选 + 2 已批引用 | PASS | `reuse_log/phase1_1_stage2_console_reuse_candidates.md:12-15` 2 Stage 0 引用（react, vite）+ `:21-36` 14 新候选（react-dom, @vitejs/plugin-react, typescript, @tanstack/react-query, @tanstack/react-router, msw, vitest, @vitest/ui, @testing-library/react, @testing-library/jest-dom, @playwright/test, jsdom, @types/react, @types/react-dom）= 16 = package.json 16 |
| 8 | 不动 noeticbraid-core / docs/contracts / 顶级文件 | PASS | manifest 内 12 contract SHA + Stage 1 core 文件全部声明 unchanged from main HEAD `4a3f962`；diff 也确认仅 noeticbraid-console/** + reuse_log 新文件被改动 |
| 9 | TypeScript strict mode | PASS | `tsconfig.json:15` `"strict": true` + `:19` `"noUncheckedIndexedAccess": true` + `:16-18` 三个 noUnused* / noFallthrough |
| 10 | Playwright config chromium + install 提示 | PASS | `playwright.config.ts:14-19` 仅 chromium 项目；`README.md:65-67` 含 `pnpm exec playwright install chromium` |
| 11 | README 4 routes + Phase 1.2/1.3 声明 | PASS | `README.md:11-16` 4 routes 表 + `:26-31` 明确声明 auth/startup_token (Phase 1.2)、account/pool (Phase 1.3)、/sources /inbox 不在 1.0.0 |
| 12 | manifest 自洽 | PASS | `manifest.md:7-12` self_reference_note + main_head_commit + contract_tag_commit 全列；总数 119 + baseline 92 + added 28 + modified 2 数字闭合（92 + 28 - 1[manifest 替换] = 119） |
| 13 | zip naming 标准 | PASS | manifest 第 13 项写 `noeticbraid_phase1_1_stage2_console.zip`；外部 zip 名匹配 |
| 14 | 8 项禁止 | PASS | manifest `:289-292` 列全 8 条；diff 中 packages/noeticbraid-core/** + docs/contracts/** + 顶级文件 + .github/workflows/ci.yml 全 unchanged；handlers 中无 auth/startup_token、无 account/pool；package.json 无 `latest` |

## 新硬伤

| 级 | 项 | 文件:行 | 说明 |
|---|---|---|---|
| M | package.json `description` 字段未升级，仍写 "NoeticBraid Web Console Stage 0 placeholder." | `packages/noeticbraid-console/package.json:7` | 自检第 11 条 README 已升级至 Phase 1.1 console，但 package.json `description` 未同步；与 manifest `:95` 描述（"version stage2-console, pinned 4 deps + 12 devDeps, added test/typecheck scripts"）轻微不一致；不阻塞构建 / 测试，但 npm metadata 错位会让外部消费者误认为仍是 placeholder。建议改为 "NoeticBraid Phase 1.1 Web Console (Stage 2 candidate)." |
| L | `src/api/client.ts` `requestUrl()` 在 `window === undefined` 分支返回原 path，而 fetch 在 Node 测试态会拒绝相对 URL；当前测试态由 Vitest `environmentOptions.jsdom.url` 提供 window，因此实际不命中分支 | `src/api/client.ts:11-22` + `vite.config.ts:51-56` | 此分支为防御性死代码（Phase 1.1 console 100% 在 jsdom/browser 下运行），不影响测试通过；但读者会困惑分支何时执行，建议加注释说明"留给 Phase 1.4+ SSR 接入"或直接删 |
| L | `routeTree.ts` 用 `import { indexRoute } from './index'` 显式带 `./index`，TS bundler resolution 下可解析但语义上略冗 | `src/routes/routeTree.ts:3` | 与 `./workspace` `./runs` `./approvals` 对齐显式写法可读性提升，问题不算 bug，仅记号风格 |

## 5 endpoints / 4 routes / 16 deps 完整性

- **5 MSW endpoints** — `handlers.ts:9-19` 完整匹配 OpenAPI 1.0.0 中 console 范围内的 5 个：`GET /api/health`, `GET /api/dashboard/empty`, `GET /api/workspace/threads`, `GET /api/ledger/runs`, `GET /api/approval/queue`。无 6 号、无 7 号；无 `auth/startup_token` 或 `account/pool` 越权 mock。
- **4 routes** — 仅 `/`, `/workspace`, `/runs`, `/approvals`（在 `routeTree.ts:7-12` 与 4 个 route 文件之 `path:` 字段一一对应）。**无** `/sources` `/inbox` `/tasks`（v3 § 4.6 反复强调 Phase 1.2 才加），符合预期。
- **16 deps** — 4 deps + 12 devDeps，全 caret `^MAJOR.MINOR.0`：

  - deps: react ^18.3.0, react-dom ^18.3.0, @tanstack/react-query ^5.59.0, @tanstack/react-router ^1.79.0
  - devDeps: @vitejs/plugin-react ^4.3.0, vite ^5.4.0, typescript ^5.5.0, @types/react ^18.3.0, @types/react-dom ^18.3.0, msw ^2.6.0, vitest ^2.1.0, @vitest/ui ^2.1.0, @testing-library/react ^16.0.0, @testing-library/jest-dom ^6.5.0, @playwright/test ^1.48.0, jsdom ^25.0.0
  - 与 manifest `:30-46` 表完全对齐；与 reuse_log 14+2 计数自洽。

无遗漏。

## 跨 prompt 一致性

| 检查项 | 判定 | 说明 |
|---|---|---|
| v3 修订 1（4 routes 对齐 5 endpoints 含 health badge） | PASS | `routes/index.tsx:18-33` 显式 health badge + contract_version 1.0.0 字样；e2e dashboard.spec.ts 断言 `1.0.0` |
| v3 修订 5（pin 版本 + 加 dev deps，16 条目） | PASS | package.json 16 条 + reuse_log 16 条交叉勾对 |
| v3 修订 9（reuse_log 命名 phase1_1_stage2_console_reuse_candidates.md，14 新 + 2 引用） | PASS | 文件名精确匹配；2 已批 + 14 新 = 16，与 package.json 一致 |
| Codex v2 M-2 强制方案 A（routeTree 独立文件） | PASS | `src/routes/__root.tsx` 仅 export `rootRoute`、不 import 任何子 route、不 export `routeTree`；`src/routes/routeTree.ts` 独立汇编；`main.tsx:6` 与 `tests/routes.test.tsx:8` 均从 `./routes/routeTree` import |
| MSW 2.x API（http.get + HttpResponse.json） | PASS | `handlers.ts:1` import { http, HttpResponse } from 'msw'；无任何 1.x `rest.get` / `res(ctx.json(...))` |
| types/contracts.ts NOTE 双 pin（1.0.0 + b8d7152） | PASS | `src/types/contracts.ts:5-8` |
| fixtures 仅业务字段 | PASS | 4 fixtures 文件均无 `$schema_status` / `contract_version` 元字段 |
| Phase 1.2/1.3 不暴露 auth/startup_token + account/pool | PASS | handlers 中无对应 endpoint；README `:28-29` 显式记账 |
| zip 命名标准（noeticbraid_phase1_1_stage2_console.zip） | PASS | manifest `:13` + `:285` |
| baseline 92 → current 119（+28 added, ~2 modified, 1 manifest replace） | PASS | manifest `:14-17` + `:243-253` 数字自洽 |
| PR # = #TBD | PASS | manifest 与 README 均无具体 PR 号；自检第 14 项 `统一 PR #TBD` |
| TanStack Router code-based（非 file-based） | PASS | 4 routes 全用 `createRoute({ getParentRoute, path, component })`；无 `Route` file convention |
| Vite + React 18 对齐 | PASS | @vitejs/plugin-react ^4.3.0 + react ^18.3.0；vite.config.ts:40 `plugins: [react(), mswWorkerPlugin()]` |

## 进 GPT-A 的判断

PASS — 14 自检项 13 PASS / 1 BLOCKED（已诚实声明，本机用 pnpm install + pnpm test + pnpm test:e2e + pnpm typecheck 复跑即可），新硬伤仅 1M（package.json description 文案，可与下一次 review 一并修），所有 v3 强约束 + Codex M-2 强制方案 A 已落地；建议放行进二审，本机 review 时附带在 description 字段升级。
