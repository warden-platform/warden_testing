# 配置与凭据规则

## 读取顺序

`config/environment.py` 的读取顺序：

```text
进程环境变量 > 本仓库 .env > warden 仓库 .env / var/warden/secrets.json > 默认值
```

## 关键配置

| 配置 | 来源 | 说明 |
|------|------|------|
| `WARDEN_BASE_URL` | 本仓库 `.env` | 控制面地址 |
| `WARDEN_HOME` | 本仓库 `.env` | 本地 warden 源码目录，默认 `../warden` |
| `WARDEN_ADMIN_PASSWORD` | warden `.env` | 平台管理员登录 |
| `WARDEN_ADMIN_API_KEY` | warden `var/warden/secrets.json` | 平台管理员 Bearer Key |
| `WARDEN_CORS_ORIGIN` | warden `.env` | Cookie 会话写请求的 `Origin` 必须与它一致 |
| `WARDEN_TEST_TENANT_PREFIX` | 本仓库 `.env` | 测试租户前缀，默认 `e2e` |
| `WARDEN_TEST_TENANT_ADMIN_NAME` | 本仓库 `.env` | 测试租户管理员名，默认 `e2e-admin` |
| `WARDEN_HTTP_TIMEOUT` | 本仓库 `.env` | HTTP 超时，默认 30 |
| `WARDEN_VERIFY_TLS` | 本仓库 `.env` | TLS 校验，默认 true |

## 硬规则

1. **仓库内不保存任何真实凭据**。`.env` 已加入 `.gitignore`，只提交 `.env.example`。
2. 代码里禁止硬编码地址、密码、Key、DSN —— 统一通过 `config/environment.py` 的读取函数取。
3. 敏感加载函数：`require_admin_password()`、`require_admin_api_key()`（运行时校验非空）。
4. CSRF Origin：`tools/request.py` 已自动带上 `WARDEN_CORS_ORIGIN`，不要移除。
5. 新增环境变量时：`environment.py` 加读取函数 → `.env.example` 加注释样例 → 本文档登记。

## 环境准备

```bash
scripts/stack_up.sh    # 复用已启动的控制面，或从本地 warden 拉起
scripts/stack_down.sh  # 只停本仓库启动的进程
```

`stack_up.sh` 会先探活 `/api/v1/health`，未就绪才检查 PostgreSQL、跑 migrations、构建并后台启动 `warden-control`。