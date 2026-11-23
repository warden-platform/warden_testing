# Project Rules Index

本目录维护当前仓库的详细项目规则，供 Agent 或开发者按需加载，避免每次都读取整份大文档。

## 入口用途

- `AGENTS.md` 是仓库总入口，本文件是详细规则入口。
- 进入仓库后，先读 `AGENTS.md`，再根据其中指引读取本文件并按任务选择需要的规则模块。
- 规则模块统一放在 `docs/project_rules/modules/`。
- 除非任务跨度很大，否则不要一次性全量加载所有模块，优先最小化加载。

## 加载策略

1. 先判断任务类型，再加载对应模块。
2. 任务涉及多个关注点时，组合加载多个模块。
3. 新增用例优先加载「核心原则、定位、用例结构、基线、fixture、工具、领域」几个模块。
4. 局部修改（如只改断言或只改配置）时，不加载无关模块。

## 模块索引

| 主题 | 路径 | 适用场景 | 关键触发词 |
| --- | --- | --- | --- |
| 一句话硬规则 | `docs/project_rules/modules/core_principles.md` | 任何任务开场，最小规则集 | 硬规则、原则、红线 |
| 项目定位与分层 | `docs/project_rules/modules/project_positioning.md` | 初次理解仓库、判断职责边界 | 分层、项目定位、case/lib/tools/config |
| 目录职责 | `docs/project_rules/modules/directory_responsibilities.md` | 判断代码放哪一层 | 目录职责、case、lib、tools、config |
| 用例结构规范 | `docs/project_rules/modules/case_structure.md` | 新增/重构测试用例 | 用例结构、fixture、factory、模板、标记 |
| 参考基线 | `docs/project_rules/modules/reference_baseline.md` | 新增用例前找参考实现 | 基线、参考、test_connector_execution_001 |
| 常用 fixture | `docs/project_rules/modules/fixtures.md` | 复用 fixture / factory 造数据 | fixture、tenant_factory、factory、agent、connector |
| 工具规则 | `docs/project_rules/modules/tools_rules.md` | 日志/断言/轮询/脱敏/唯一 ID | zPrint、assert_json、assert_error、wait_until、unique_slug |
| 配置与凭据 | `docs/project_rules/modules/configuration_rules.md` | 环境变量、凭据回退、stack 启停 | WARDEN_、.env、Origin、凭据、stack_up |
| 关键领域知识 | `docs/project_rules/modules/domain_knowledge.md` | 执行/审批/隔离/签名业务语义 | 状态机、REQUIRE_APPROVAL、签名、租户隔离、Idempotency |

## 常见任务的推荐加载组合

### 新增测试用例

- `core_principles.md`
- `project_positioning.md`
- `case_structure.md`
- `reference_baseline.md`
- `fixtures.md`
- `tools_rules.md`
- `domain_knowledge.md`

### 新增/修改接口封装（lib 层）

- `project_positioning.md`
- `directory_responsibilities.md`
- `domain_knowledge.md`
- `core_principles.md`

### 环境、凭据、地址或 CSRF 相关修改

- `directory_responsibilities.md`
- `configuration_rules.md`
- `core_principles.md`

### 只补日志 / 断言 / 轮询

- `tools_rules.md`
- `core_principles.md`

### 写执行/审批/隔离/签名用例

- `domain_knowledge.md`
- `reference_baseline.md`
- `case_structure.md`

## 维护原则

- `AGENTS.md` 只保留高优先级摘要和加载指引，详细规则以本目录为准。
- 规则细节更新时，优先同步对应模块；只有总入口或硬规则变化时再更新 `AGENTS.md`。
- 新增规则类型时，在 `modules/` 下补新模块，并在本文件登记用途、路径和触发词。