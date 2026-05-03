# D-Secret-Policy-1: 统一 Secret 处理 ADR

## Status
Accepted (主理人 2026-05-02 决议, 决策点 #17)

## Context
当前 noeticbraid-backend 仅 DPAPI 处理 startup_token 一项 (Stage 2A, ctypes-based)。
未来需引入的多类 secret (cookies / Telegram bot token / browser profile / academic db credential)
不能借 DPAPI 名义自动通过, 因 DPAPI 仅 Windows + 仅 token-class secret, 不适合 cookies/jar/PEM。

## Decision
所有 secret 必须按本 ADR 规定的"分类 + 存放 + 读取 + 审计 + 失效"五维契约处理:

### 5.1 secret 分类

| 类型 | 例子 | 推荐存放 |
|---|---|---|
| OAuth/API token | startup_token / claude_api_key | DPAPI vault (现状) |
| 浏览器 cookies/jar | ChatGPT Web cookies / NotebookLM session | DPAPI 加密 .cookies.bin (新增, 非 plain text) |
| 第三方机器人密钥 | TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID | DPAPI 加密 .bot_secrets.bin |
| 学术付费账号 | arXiv pro / 专利数据库 | DPAPI 加密 .academic_creds.bin |
| 浏览器 profile 路径 | ChatGPT Chrome profile dir | 配置文件 (非 secret 本身), 但路径需 audit |

### 5.2 存放位置
- noeticbraid/private/secrets/ (DPAPI 加密目录, .gitignore)
- 永远不进 git, 永远不进 stdout, 永远不进 RunRecord

### 5.3 读取契约
- 每类 secret 必须有显式读取 API (类似 noeticbraid_backend.auth.tokens.read_startup_token)
- 读取必须 audit 一行 (谁读, 何时读, 哪个调用栈)
- 不允许 os.environ.get 直接读 secret (除非过 SecretReader 包装)

### 5.4 审计要求
- 每类 secret 必须在 audit_trail.md 单独记一行 (引入时间 / 引入 contract 版本 / 退出条件)

### 5.5 失效流程
- 每类 secret 必须有显式 revoke API (清空 DPAPI vault 对应 entry)
- 失效后必须 audit 一行

## Consequences
- 后续任何模块涉及 secret 必须先指出本 ADR 的哪一类, 不能自创
- contract 1.2.0 必须把 secret reader 接口 schema 化 (T-MID-1 子项)

## References
- 决策点 #17 (主理人 2026-05-02 选 A)
- AGENTS §8 license whitelist + DPAPI 锁定
- 蓝图 §7.5 多账号池 cookies 部分
