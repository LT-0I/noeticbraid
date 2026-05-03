# D-Naming-1: NoeticBraid vs HelixMind 双名映射 ADR

## Status
Accepted (主理人 2026-05-02 决议)

## Context
- 蓝图 §1.3 定项目最终英文名为 HelixMind
- repo / workflow 当前权威名称为 NoeticBraid (README.md / AGENTS.md / docs/architecture/step3_authority.md)
- 所有 commit / tag / CI / contract 已用 NoeticBraid 名
- 两套命名并存, 此前无任何 commit / decision log / ADR 记录哪一方覆盖

## Decision
双名共存, 明确职能分离:
- NoeticBraid = repo / 工程 / 代码 / commit / tag / CI 工程名 (内部 / 开发者面向)
- HelixMind = 产品对外名 (用户 / 文档 / 营销 / 蓝图描述)

类比: React (代码) vs React Native (产品), 同框架不同名。

## Consequences
- README.md / AGENTS.md / 所有现有 commit / tag 不动 (沿用 NoeticBraid)
- 蓝图引用保留 HelixMind 原文
- 未来对外发布 / 用户文档统一用 HelixMind
- noeticbraid/docs/ 新写文档可双写: 标题用 HelixMind, 工程引用用 NoeticBraid
- PROJECT_STATUS.md §0.5 命名分歧节将更新结论指向本 ADR

## Alternatives Considered
- A 维持 NoeticBraid 不变: 违背蓝图原意, 未来宣传仍需澄清
- B 全面改名 HelixMind: 高破坏性, 现有 audit_trail / tag / commit history 全带 NoeticBraid 名

## References
- 决策点 #2 (主理人 2026-05-02 选 C)
- 决策点 #10 (主理人 2026-05-02 选 A)
- 蓝图 §1.3 (项目文档/HelixMind_Project_Blueprint_Package/HelixMind_Project_Blueprint_CN.md)
- noeticbraid/README.md (现有 NoeticBraid 权威引用)
- noeticbraid/AGENTS.md (现有 NoeticBraid 权威引用)
- noeticbraid/docs/architecture/step3_authority.md (现有 NoeticBraid 权威引用)
- noeticbraid/PROJECT_STATUS.md §0.5 命名分歧节
