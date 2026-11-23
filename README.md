# warden_testing

> 独立的 **warden 黑盒 API / 业务流验收测试仓库**。
> `pytest + requests + allure`，按 `case / lib / tools / config` 分层，针对 warden 的授权、审批、执行、审计模型做黑盒验收。

## 当前状态

- 共 **53 个用例**，三个 workflow 全绿：
  - 核心 API 31（健康/认证/租户/项目/Principal/Key/Connector/执行/审批/审计/隔离/签名负向）；
  - 集成 17（联邦断言 5、AI 助手 2、OIDC 2、钉钉渠道 8）；
  - UI 冒烟 5（登录 2 + 资源目录/审批/审计三页 3）。
- 覆盖：健康检查、平台/租户登录、租户生命周期、项目、Principal/API Key、测试 Connector、执行状态机、审批、审计、租户隔离、Connector 签名负向、联邦断言登录、AI 助手、OIDC、钉钉审批渠道、UI 登录与三页冒烟。
- 不依赖真实 Kubernetes / Jenkins / 网络设备：仓库内置 **Python 版测试 Connector**，复刻 warden 的 HMAC 请求签名协议；集成测试用 mock（假 IdP / mock LLM / RSA 自签断言）。

## 为什么独立成仓

warden 主仓库已有 500+ Go 测试，覆盖单元、Handler 和 DB 门控集成测试。本仓库不重复这些内容，专注：

1. **黑盒契约**：从外部 HTTP 视角验证 `docs/api.md` 的路由、状态码、错误码。
2. **跨层业务流**：租户 → 项目 → 资源 → Agent → 执行 → 审批 → 审计。
3. **安全边界**：跨租户、Scope、签名重放、审批前后权限变化。
4. **发布前验收**：对固定镜像/commit 跑独立回归，不侵入 Go 单测速度。

## 目录结构

```text
warden_testing/
├── case/                       # 场景编排层，只调用 lib/factory 与 lib 客户端
│   ├── conftest.py             # 全局 fixture：健康检查、平台管理员、隔离租户、Agent、Connector、各 mock
│   ├── platform/               # 健康检查、登录、租户生命周期
│   ├── tenant/                 # 项目、Principal、API Key
│   ├── connector/              # 测试 Connector 驱动的执行闭环与签名负向
│   ├── security/               # 跨租户隔离
│   ├── federation/             # 联邦断言登录
│   ├── ai/                     # AI 助手（mock LLM）
│   ├── oidc/                   # OIDC（假 IdP）
│   ├── dingtalk/               # 钉钉通知渠道与租户隔离
│   └── ui/                     # Playwright UI 冒烟
├── lib/
│   ├── control/client.py       # warden 控制面 API 封装
│   ├── connector/simulator.py  # 测试 Connector：注册/心跳/资源同步/拉任务/回传
│   └── factory.py              # 租户、项目、Agent、Connector 工厂
├── tools/
│   ├── request.py              # 统一 HTTP，脱敏后写 allure
│   ├── assertTool.py           # 结构化断言
│   ├── crypto.py               # Connector HMAC 签名
│   ├── federation.py           # RSA 密钥对 + 联邦断言 JWT 签名
│   ├── mock_llm.py             # mock OpenAI 兼容 SSE 流式服务
│   ├── fake_oidc.py            # 假 OIDC IdP（discovery/jwks/token）
│   ├── waitTool.py             # 条件轮询
│   ├── ids.py                  # 唯一测试数据标识
│   └── printTool.py            # zPrint
├── config/environment.py       # 环境与凭据加载（含 warden 本地仓库回退）
├── .github/workflows/          # e2e / integration / ui-smoke 三个 workflow
├── scripts/                    # stack_up / stack_down / run_tests / sync-github
├── docs/TEST_PLAN.md           # 覆盖矩阵与后续路线
├── pytest.ini
├── requirements.txt
└── Makefile
```

## 快速开始

### 1. 安装依赖

```bash
make install
```

### 2. 准备被测控制面

**方式 A：复用已启动的 warden**

```bash
# .env
WARDEN_BASE_URL=http://127.0.0.1:8090
```

**方式 B：由本仓库启动本地 warden**

```bash
# 默认 WARDEN_HOME=../warden，可用环境变量覆盖
scripts/stack_up.sh
```

`stack_up.sh` 会：

1. 先探测 `/api/v1/health`，已就绪则直接返回；
2. 检查 PostgreSQL（必要时用 warden 的 compose 拉起）；
3. 空库时执行 warden migrations；
4. 构建并后台启动 `warden-control`，PID 写入 `.warden_test.pid`；
5. 等待健康检查通过。

停止：`scripts/stack_down.sh`（只停止由本仓库启动的进程）。

### 3. 运行

```bash
make smoke        # 冒烟
make test         # 全量
make connector    # 测试 Connector / 执行链路
make security     # 安全与隔离
make approval     # 审批链路
make report       # allure serve allure-results
```

集成测试与 UI 冒烟按 marker 单独跑（需先准备对应 mock 与配置，见 TEST_PLAN）：

```bash
# 集成：联邦断言 / AI / OIDC / 钉钉（需控制面带上对应配置 + mock）
pytest -m "federated or ai or oidc or dingtalk"

# UI 冒烟：需前端 dev server + playwright 浏览器
pytest -m ui
```

### 4. 配置与凭据

`config/environment.py` 的读取顺序：

```text
进程环境变量 > 本仓库 .env > warden 仓库 .env / var/warden/secrets.json > 默认值
```

| 配置 | 来源 | 说明 |
|---|---|---|
| `WARDEN_BASE_URL` | 本仓库 `.env` | 控制面地址 |
| `WARDEN_HOME` | 本仓库 `.env` | 本地 warden 源码目录，默认 `../warden` |
| `WARDEN_ADMIN_PASSWORD` | warden `.env` | 平台管理员登录 |
| `WARDEN_ADMIN_API_KEY` | warden `var/warden/secrets.json` | 平台管理员 Bearer Key |
| `WARDEN_CORS_ORIGIN` | warden `.env` | Cookie 会话写请求的 `Origin` 必须与它一致 |

**仓库内不保存任何真实凭据。** `.env` 已加入 `.gitignore`，只提交 `.env.example`。

> 重要：warden 对 Cookie 会话的 POST/PUT/DELETE 做 CSRF 校验，`Origin` 必须与 `WARDEN_CORS_ORIGIN` 完全一致。`tools/request.py` 已自动带上该头，不要移除。

## 测试设计

### 数据隔离

每个用例（或每个 `tenant_factory()` 调用）都会：

1. 通过平台管理员 `POST /tenants/bootstrap` 创建唯一 `e2e-*` 租户；
2. 在该租户内创建默认项目、Agent Principal、API Key、Connector；
3. 用例结束后停用租户（`POST /tenants/{slug}/disable`）。

不按手机号/全局条件删除共享数据，因此 `pytest-xdist` 并行时也不会互相污染。

### 测试 Connector

`lib/connector/simulator.py` 复刻了 `server/internal/domain/connector_request.go` 的签名：

```text
canonical = warden-connector-request-v1
            METHOD
            path?query
            timestamp
            nonce
            sha256(body)
signature = hmac-sha256:hex(HMAC_SHA256(key, canonical))
headers   = X-Warden-Timestamp / X-Warden-Nonce / X-Warden-Signature
```

因此无需真实目标即可覆盖：

- Connector 注册、心跳、资源同步；
- `GET /connectors/{id}/tasks` 领取 `TaskEnvelope`；
- `POST .../tasks/{executionId}/result` 回传 `SUCCEEDED` / `FAILED` / `UNKNOWN`；
- 错误 Key、篡改 body、过期时间戳、重放 nonce、缺失签名头。

### 设计取舍

在四层分工、统一 request/assert/log、allure 报告、业务流编排之上，采用以下更贴合黑盒验收的设计：

| 常见做法 | warden_testing |
|---|---|
| 每个文件固定 `preset → case → reset` 三步结构 | 标准 pytest 函数 + fixture + factory |
| 共享账号与全局数据清理 | 每用例随机租户，天然隔离 |
| 正则解析响应做断言 | 结构化 dict/list 断言 + jsonschema |
| 固定 `sleep` | `wait_until` 条件轮询 |
| 凭据入库 | 环境变量 / 本地 warden 配置回退 |
| 请求响应含密码进 allure | 统一脱敏后再 attach |

## 新增用例

1. 在对应目录新建 `case/<domain>/test_<module>_<number>.py`；
2. 从 `lib/factory.py` 或 `case/conftest.py` 取 fixture；
3. 接口调用只走 `WardenClient` / `TestConnector`；
4. 日志用 `zPrint()`，断言用 `tools/assertTool.py`；
5. 异步状态用 `wait_until()`，不要 `time.sleep()`；
6. 负向用例用 `allow_error=True` + `assert_error(...)`。

模板：

```python
import pytest
from lib.control.client import WardenClient
from tools.assertTool import assert_error, assert_json

pytestmark = pytest.mark.smoke

def test_example(tenant_admin: WardenClient):
    projects = tenant_admin.list_projects()
    assert_json(projects[0], is_default=True)
```

## 后续路线

详见 [docs/TEST_PLAN.md](docs/TEST_PLAN.md)：

- Phase 2：策略矩阵、更多审批/取消/并发边界；
- Phase 3：Connector 租约过期、TaskEnvelope 本地验签、变更安全结果；
- Phase 4 已落地：联邦断言、OIDC（假 IdP）、钉钉渠道、AI（mock）、UI 冒烟；剩余：委托 Token、下载接口。