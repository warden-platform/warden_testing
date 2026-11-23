# warden_testing 测试方案

## 1. 目标与边界

**目标**：在不修改 warden 源码的前提下，从外部 HTTP 视角验证：

- API 契约（路由、状态码、错误码、字段）；
- 跨层业务流（租户 → 项目 → 资源 → Agent → 执行 → 审批 → 审计）；
- 安全边界（租户隔离、Scope、签名、重放、权限变更）；
- 发布前回归（固定镜像/commit，独立于 Go 单测）。

**不做**：

- 重复 warden 的 Go 单元测试与 Handler 测试；
- 使用真实 Kubernetes / Jenkins / 网络设备；
- 在生产租户或共享数据上执行写操作。

## 2. 分层与执行模型

```text
case/    场景编排
lib/     控制面客户端、测试 Connector、数据工厂
tools/   HTTP、断言、轮询、签名、日志
config/  环境与凭据
```

- 每个用例通过 `tenant_factory()` 获得唯一 `e2e-*` 租户；
- 用例结束停用租户，不做全局删除；
- 测试 Connector 使用一次性 `taskSigningKey` 签名，跑通真实执行状态机；
- 失败信息包含 HTTP 状态、错误码、脱敏后的请求响应与 allure 附件。

## 3. 覆盖矩阵

### 已实现（53 个用例）

**核心 API（31）**：

| 域 | 用例 | 关键断言 |
|---|---|---|
| 健康检查 | `health/livez/readyz` | 200；未认证 `/auth/me` 401 |
| 平台认证 | 平台管理员登录、`/auth/me`、登出 | `is_platform_admin`、`warden:admin`、登出后 401 |
| 租户认证 | 租户管理员登录 | 租户 slug、`warden:tenant:admin`、`warden:approve` |
| 管理员 Key | Bearer `WARDEN_ADMIN_API_KEY` | 可读资源列表 |
| 租户生命周期 | bootstrap、重复 slug、非法 slug、停用、越权 bootstrap | 201/409/400/401/403 |
| 项目 | 默认项目、CRUD、默认项目保护、重名 | 201/200/204/409 |
| Principal | 创建、列表、metadata.role 剥离 | 201；不能提权 |
| API Key | 创建、列表不返回明文、撤销、轮换、非法 Scope | 201/400/401 |
| Connector | 网络 Connector 创建、注册、心跳、资源同步 | 201/200 |
| 执行（只读） | `network.device.get` 全链路 | QUEUED → DISPATCHED → SUCCEEDED |
| 执行（失败） | 回传 FAILED | FAILED + `EXECUTION_ERROR` |
| 执行（变更） | `network.interface.description.update` | WAITING_APPROVAL → approve → QUEUED → SUCCEEDED |
| 幂等/取消 | 相同 `Idempotency-Key`、QUEUED 取消 | 同 execution id；CANCELLED |
| 审计 | 执行审计 | `execution.queued`、`execution.completed` |
| 签名负向 | 错误 Key、篡改 body、过期、重放、缺头 | 401 `CONNECTOR_UNAUTHORIZED` |
| 租户隔离 | 资源动作、执行、资源列表、Principal、项目成员 | 404 / 空列表 / 不泄露 |

**集成（17）**：

| 域 | 用例 | mock / 关键断言 |
|---|---|---|
| 联邦断言 | 链路、未绑定、重放、错签名、过期 | RSA 自签 JWT；200 accessToken / 403 `FEDERATED_TENANT_NOT_BOUND` / 401 `ASSERTION_REPLAYED` |
| AI 助手 | 链路、未认证 | mock `/chat/completions` SSE；delta+done 事件；401 |
| OIDC | 授权码链路、state 负向 | 假 IdP（discovery/jwks/token + RS256）；session 签发 / 400 `INVALID_OIDC_STATE` |
| 钉钉渠道 | 默认/未配置启用/名称事件/测试未配置/非 admin/跨租户群隔离 | 409 `DINGTALK_NOT_CONFIGURED` / 400 `INVALID_CHANNEL` / 409 `DINGTALK_GROUP_BOUND` / 403 |

**UI 冒烟（5）**：

| 页 | 断言 |
|---|---|
| 平台/组织登录 | 登录成功离开登录页；错误密码留在登录页 |
| 资源目录 / 审批 / 审计 | 页标题渲染（`Resource Catalog` / `Approval Queue` / `Audit Trail`） |

### 下一阶段

| 阶段 | 内容 |
|---|---|
| Phase 2 | 策略矩阵 `ALLOW/DENY/REQUIRE_APPROVAL`、拒绝原因、审批过期、并发 429、分页、Scope 细分 |
| Phase 3 | Connector 租约过期、TaskEnvelope 本地验签、`UNKNOWN` 语义、变更安全 `_warden_safety`、真实目标集成（可选） |
| Phase 4 | 剩余：委托 Token、下载接口（联邦断言/OIDC/钉钉/AI/UI 已落地） |

## 4. 安全测试矩阵

| 维度 | 用例设计 |
|---|---|
| 租户隔离 | A 的 Agent/Admin 访问 B 的资源、执行、Principal、项目成员 |
| Scope | 只有 `read:self` 的 Key 创建执行；非法 Scope 创建 Key |
| 认证 | 无凭据、错误密码、停用租户、撤销/轮换后的 Key |
| Connector 签名 | 错误 Key、篡改 body、过期时间戳、重放 nonce、缺失头 |
| 审批 | 审批前权限变化、重复审批、拒绝后执行状态 |
| 提权 | `metadata.role` 注入、普通租户管理员创建新租户 |

## 5. 环境与数据

- 控制面：`WARDEN_BASE_URL`，默认本机；`scripts/stack_up.sh` 可启动本地 warden。
- 凭据：从 warden 仓库 `.env` / `var/warden/secrets.json` 回退读取，仓库不保存。
- 数据库：测试不直接连库；通过 API 验证。后续如需 DB 断言，再引入可控的只读连接。
- 隔离：每个用例独立租户；不修改 `platform` 与演示租户 `acme`。

## 6. 运行与 CI

```bash
make smoke        # PR 门禁，约 10 秒
make test         # 全量
make connector    # 执行链路
make security     # 安全
make report       # allure
```

集成与 UI 按 marker 跑（需对应 mock/配置，见各 marker fixture 门控）：

```bash
pytest -m "federated or ai or oidc or dingtalk"   # 集成
pytest -m ui                                       # UI 冒烟
```

CI（GitHub Actions，`scripts/sync-github.sh` 把 gitee 快照同步到 GitHub 镜像后触发）：

| workflow | 触发 | 内容 |
|---|---|---|
| `warden-e2e` | push main | postgres service + 自建 warden → 核心 31（smoke/connector/security/approval） |
| `warden-integration-e2e` | push main / 手动 | 控制面带集成配置 + 各 mock → 联邦/AI/OIDC/钉钉 17 |
| `warden-ui-smoke` | 手动 | 附加前端 dev server + Playwright 浏览器 → UI 5 |

- 各 workflow 内统一套路：postgres service → checkout warden → init secrets/config → 迁移 → `go build` 控制面 → 等 `/api/v1/health` → pytest。
- 产物：`allure-results/` + JUnit XML；凭据经环境变量与本地 warden 回退注入，报告脱敏。

## 7. 已知限制

- 测试 Connector 只模拟网络设备动作，不执行真实设备命令（真实 Kubernetes / Jenkins / 网络设备属联调范畴，不在本黑盒仓库内）；
- 钉钉仅覆盖「渠道 CRUD + 租户隔离 + 错误码」：真实推送/回调因 webhook host 校验 + Stream 长连接的硬约束，未做黑盒覆盖；
- 集成 mock（假 IdP / mock LLM / RSA 自签断言）只验证协议契约，不验证真实 SSO IdP / LLM / 外部 IdP 的行为；
- 未做 TaskEnvelope 的 Python 侧验签（Go 侧与真实 Connector 已覆盖）；
- 未引入数据库直连断言，避免测试仓库持有 DB 凭据。