# 关键领域知识

写执行/审批/隔离/签名用例前先读本文件，避免对业务语义的误判。

## 1. 执行状态机

```text
WAITING_APPROVAL → QUEUED → DISPATCHED → SUCCEEDED
                                       ├→ FAILED
                                       └→ UNKNOWN
QUEUED ──取消──► CANCELLED
```

- 只读网络动作（如 `network.device.get`）默认 `ALLOW`，直接进队列。
- 网络变更动作（如 `network.interface.description.update`）默认 `REQUIRE_APPROVAL`，先停在 `WAITING_APPROVAL`，批准后才入队。
- 幂等：相同 `Idempotency-Key` 返回相同 execution id，不重复创建。

## 2. Connector 请求签名

`lib/connector/simulator.py` 复刻 `server/internal/domain/connector_request.go`：

```text
canonical = warden-connector-request-v1 + METHOD + path?query + timestamp + nonce + sha256(body)
signature = hmac-sha256:hex(HMAC_SHA256(key, canonical))
headers   = X-Warden-Timestamp / X-Warden-Nonce / X-Warden-Signature
```

约束：

- nonce 在 2 分钟窗口内不可重放。
- 过期时间戳、错误 Key、篡改 body、缺失签名头 → `401 CONNECTOR_UNAUTHORIZED`。

## 3. 租户隔离

- 服务端强制执行，跨租户读取执行/资源应返回 404，列表不得泄露其他租户对象。
- 每个测试用例独立 `e2e-*` 租户；`platform` 与演示租户 `acme` 不属于测试域，不得写。

## 4. 认证与 Scope

- 平台管理员登录走 `tenant="platform"`，`/auth/me` 返回 `is_platform_admin` 等。
- 租户管理员登录走 `{admin_name}@{slug}`。
- API Key 创建时指定 Scope；非法 Scope → 400；只读 Scope 的 Key 不能创建执行。
- 未认证 `/auth/me` → 401；登出后访问 → 401。

## 5. 审批

- 变更动作产生 access request（`WAITING_APPROVAL`），管理员 `approve` 后执行才继续。
- 覆盖：审批前权限变化、重复审批、拒绝后执行状态。
- 审计事件含 `execution.queued`、`execution.completed` 等。

## 6. 测试 Connector 能力

`TestConnector` 方法：`register` / `heartbeat` / `sync_resources` / `sync_network_device` / `sync_network_interface` / `poll_tasks` / `submit_result` / `find_task`。它用一次性 `taskSigningKey` 签名，跑通真实状态机而不依赖真实设备。