# 常用 fixture

所有 fixture 定义在 `case/conftest.py`。新增用例优先复用，不要自己离线造数据。

| fixture | 作用域 | 类型 | 说明 |
|---------|--------|------|------|
| `control_plane_ready` | session | autouse | 启动前确认 `/api/v1/health` 可访问，不可达则 `pytest.exit(2)` |
| `platform_admin` | session | `WardenClient` | 平台管理员会话，用于租户生命周期 |
| `admin_api` | session | `WardenClient` | 用 `WARDEN_ADMIN_API_KEY` 的 Bearer 客户端 |
| `tenant_factory` | function | callable | `tenant_factory(prefix=None)` 创建租户，用例结束自动停用 |
| `tenant` | function | dict | 单个唯一 `e2e-*` 租户（含 slug / name / admin 凭据） |
| `tenant_admin` | function | `WardenClient` | 租户管理员会话（已断言租户正确） |
| `default_project` | function | dict | 租户默认项目 |
| `agent` | function | dict | Agent Principal + API Key + 客户端，结束自动清理 |
| `connector` | function | dict | 已注册、已心跳的测试 Connector |

## 依赖链

```
platform_admin ──► tenant_factory ──► tenant ──► tenant_admin ──► default_project ──► agent / connector
admin_api（独立，仅依赖 session 凭据）
```

## 数据字段

- `tenant`：`slug` / `name` / `admin_name` / `admin_password` / `tenant`（bootstrap 返回）/ `administrator`。
- `agent`：`principal` / `api_key` / `credential` / `client`。
- `connector`：`id` / `name` / `client`（TestConnector）/ `created`。

## Factory 函数（lib/factory.py）

| 函数 | 作用 |
|------|------|
| `new_tenant_payload(prefix=None)` | 构造租户 payload |
| `bootstrap_tenant(platform_admin, prefix=None)` | 建租户并返回扩展字典 |
| `tenant_admin_client(tenant)` | 登录得到租户管理员客户端 |
| `default_project(tenant_admin)` | 取默认项目 |
| `create_agent(tenant_admin)` | Agent Principal + API Key + 客户端 |
| `create_connector(tenant_admin, project)` | 建网络 Connector + 注册 + 心跳 |
| `create_tenant_stack(platform_admin, prefix=None)` | 一键建完整隔离栈（租户+管理员+项目+Agent+Connector） |

> 需要更细粒度控制（如独立模块、手动审批）时，用 `create_tenant_stack` 或逐个 factory 函数拼装，而不是复制 fixture 逻辑。