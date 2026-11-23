# warden_testing Agent Guide

独立于 warden 主仓库的**黑盒 API / 业务流验收测试仓库**，技术栈 `pytest + requests + allure`。
warden 主仓库负责 Go 单元/组件/DB 集成测试；本仓库负责从外部 HTTP 视角验证契约、跨层业务流和安全边界。

## 规则入口

详细规则统一维护在：

- `docs/project_rules/project_rules.md`
- `docs/project_rules/modules/*.md`

处理任务时，先读 `docs/project_rules/project_rules.md`，再按任务类型动态加载对应模块；除非任务跨度很大，否则不要一次性全量加载所有模块。

## 常驻硬规则

- 仓库内不保存真实凭据；凭据从进程环境变量、本仓库 `.env`、warden 仓库 `.env` / `secrets.json` 读取。
- `case/` 层禁止直接 `requests.get/post`，统一走 `WardenClient` / `TestConnector`。
- 日志统一 `from tools.printTool import zPrint`，禁止裸 `print()`。
- 断言统一 `tools/assertTool.py`，禁止用正则解析 `str(response)`。
- 异步状态统一 `tools.waitTool.wait_until`，禁止固定 `time.sleep()`。
- 每个用例使用 `tenant_factory()` 创建唯一 `e2e-*` 租户；不要复用共享账号或删除全局数据。
- Cookie 会话的写请求必须带 `Origin`（`tools/request.py` 已统一处理）；不要移除。
- 请求/响应写入 allure 前必须脱敏（`tools/request.py` 已统一处理）。
- 文件与函数命名使用 Python 标准 `snake_case`；测试函数以 `test_` 开头。
- 新增用例后必须实际跑通；无法连接环境时明确说明，不伪造结果。

## 基线参考

新增用例优先参考：

1. `case/connector/test_connector_execution_001.py`：完整执行链路、审批、幂等。
2. `case/platform/test_health_and_auth_001.py`：认证与健康检查。
3. `case/security/test_tenant_isolation_001.py`：跨租户安全。

详情见 `docs/project_rules/modules/reference_baseline.md`。

## 常用 fixture

- `platform_admin`：平台管理员会话（租户生命周期）。
- `admin_api`：`WARDEN_ADMIN_API_KEY` 客户端。
- `tenant_factory` / `tenant`：唯一测试租户，用例结束自动停用。
- `tenant_admin`：租户管理员会话。
- `default_project`：租户默认项目。
- `agent`：Agent Principal + API Key + 客户端。
- `connector`：已注册、已心跳的测试 Connector。

详情见 `docs/project_rules/modules/fixtures.md`。

## 动态加载建议

### 新增测试用例

优先加载：

- `docs/project_rules/modules/core_principles.md`
- `docs/project_rules/modules/project_positioning.md`
- `docs/project_rules/modules/case_structure.md`
- `docs/project_rules/modules/reference_baseline.md`
- `docs/project_rules/modules/fixtures.md`
- `docs/project_rules/modules/tools_rules.md`
- `docs/project_rules/modules/domain_knowledge.md`

### 修改 lib 层接口封装

优先加载：

- `docs/project_rules/modules/project_positioning.md`
- `docs/project_rules/modules/directory_responsibilities.md`
- `docs/project_rules/modules/domain_knowledge.md`

### 环境、地址、凭据、CSRF 相关修改

优先加载：

- `docs/project_rules/modules/configuration_rules.md`
- `docs/project_rules/modules/core_principles.md`

### 只补日志 / 断言 / 轮询

- `docs/project_rules/modules/tools_rules.md`

## 常用命令

```bash
make install
scripts/stack_up.sh
make smoke
make test
make report
```

## 测试标记

- `smoke`：健康检查、登录、租户、项目、Principal。
- `connector`：测试 Connector 与执行链路。
- `security`：越权、隔离、签名负向。
- `approval`：审批链路。
- `slow`：耗时较长。

## 维护原则

- `AGENTS.md` 只保留总入口、常驻硬规则、基线摘要和加载指引；详细规则以 `docs/project_rules/` 为准。
- 若详细规则变更但不影响入口或硬规则，优先只更新 `docs/project_rules/`。