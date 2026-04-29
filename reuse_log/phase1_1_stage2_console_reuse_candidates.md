# Phase 1.1 Stage 2 Console — Reuse Candidates

> 修订 9 命名约定：Stage 2 新依赖单独成文件，不并入 Stage 0 旧 reuse_log。
> 本文件由 GPT-D 在 Stage 2 console 实装时新增；与
> `reuse_log/phase1_1_reuse_candidates.md`（Stage 0 锁定）并存。

## Already-approved (Stage 0 reuse_log)

下列 2 项已在 Stage 0 `reuse_log/phase1_1_reuse_candidates.md` 显式标 `直接并入`，
本 Stage 2 console 仅继续使用，不重复审；列在此处仅作引用方便审计。

| 名称 | 许可 | 用途 | Stage 0 状态 |
|---|---|---|---|
| react | MIT | UI runtime | 直接并入（Stage 0 reuse_log 显式列出） |
| vite | MIT | Build tool / dev server | 直接并入（Stage 0 reuse_log 显式列出） |

> 注：TanStack Table 在 Stage 0 reuse_log 显式批准，但 Phase 1.1 console 实际不使用（4 路由均为简单列表，未引入表格组件）；保留 Stage 0 批准状态供 Phase 1.2+ 使用。shadcn-ui 在 Stage 0 标 `参考`，本 Stage 2 console 未引入（不增加额外组件库依赖）。

## Newly added (Stage 2 console)

| 名称 | 许可 | 用途 | Stage 2 状态 | 备注 |
|---|---|---|---|---|
| react-dom | MIT | DOM renderer (React 18 配套) | 直接并入 | package.json 已存在但 Stage 0 reuse_log 未显式列出，本 Stage 2 显式补审 |
| @vitejs/plugin-react | MIT | React + Vite glue | 直接并入 | package.json 已存在但 Stage 0 reuse_log 未显式列出，本 Stage 2 显式补审 |
| typescript | Apache-2.0 | Type system | 直接并入 | package.json 已存在但 Stage 0 reuse_log 未显式列出，本 Stage 2 显式补审 |
| @tanstack/react-query | MIT | Server state cache | 直接并入 | package.json 已存在但 Stage 0 reuse_log 未显式列出，本 Stage 2 显式补审 |
| @tanstack/react-router | MIT | Type-safe router | 直接并入 | package.json 已存在但 Stage 0 reuse_log 未显式列出，本 Stage 2 显式补审 |
| msw | MIT | API mock layer (browser worker + node server) | 直接并入 | Phase 1.1 frontend-only 必需；拦截 5 endpoints |
| vitest | MIT | Unit test runner（与 Vite 同栈） | 直接并入 | 6 unit tests |
| @vitest/ui | MIT | Vitest 交互 dashboard（dev only） | 直接并入 | scripts.test:ui |
| @testing-library/react | MIT | DOM 测试（render / screen / waitFor） | 直接并入 | 6 unit tests 使用 |
| @testing-library/jest-dom | MIT | Custom DOM matchers (toBeInTheDocument 等) | 直接并入 | tests/setup.ts |
| @playwright/test | Apache-2.0 | E2E 测试（chromium） | 直接并入 | 4 e2e specs |
| jsdom | MIT | Vitest 测试环境（Node 内 DOM） | 直接并入 | vite.config.ts test.environment |
| @types/react | MIT | React 18 TypeScript 类型定义 | 直接并入 | strict mode + React 18 必需；版本与 react 主版本对齐（^18.3.0） |
| @types/react-dom | MIT | React DOM TypeScript 类型定义 | 直接并入 | strict mode + React 18 必需；版本与 react-dom 主版本对齐（^18.3.0） |

## License audit summary

- 全部新增依赖许可均为 OSI-approved（MIT / Apache-2.0），与项目 Apache-2.0 主许可兼容
- 无 GPL / AGPL / SSPL / BSL / 商业许可项
- 无安全漏洞已知项（截至 2026-04 时点）
- 全部直接并入；不需走 contract_change_request 流程
- Phase 1.2 console 扩展（`/sources` `/inbox` 等）不在本文件清单，由 Phase 1.2 启动时新建 `phase1_2_stage*_console_reuse_candidates.md`
