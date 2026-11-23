# -*- coding = utf-8 -*-
"""统一环境配置入口。

优先级：进程环境变量 > 本仓库 .env > warden 本地仓库的 .env / secrets.json > 默认值。
仓库中不保存任何真实凭据。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WARDEN_HOME = REPO_ROOT.parent / "warden"

_REPO_ENV_PATH = REPO_ROOT / ".env"
_REPO_ENV = dotenv_values(_REPO_ENV_PATH) if _REPO_ENV_PATH.exists() else {}


def _get(name: str, default: str | None = None) -> str | None:
    """按优先级读取配置：进程环境变量 > 本仓库 .env > 默认值。"""
    value = os.environ.get(name)
    if value is not None:
        return value
    value = _REPO_ENV.get(name)
    if value is not None:
        return value
    return default


def _resolve_warden_home() -> Path:
    raw = Path(str(_get("WARDEN_HOME", str(DEFAULT_WARDEN_HOME)))).expanduser()
    # 相对路径按仓库根目录解析，避免从其他 cwd 运行时指向错误位置。
    return raw.resolve() if raw.is_absolute() else (REPO_ROOT / raw).resolve()


WARDEN_HOME = _resolve_warden_home()


def _read_warden_env(name: str) -> str | None:
    """从 warden 本地仓库的 .env 读取用户提供的凭据。"""
    path = WARDEN_HOME / ".env"
    if not path.exists():
        return None
    return dotenv_values(path).get(name)


def _read_warden_secret(name: str) -> str | None:
    """从 warden 的 var/warden/secrets.json 读取内部签名 Key。"""
    path = WARDEN_HOME / "var" / "warden" / "secrets.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(name)
    except (OSError, ValueError):
        return None


WARDEN_BASE_URL = str(_get("WARDEN_BASE_URL", "http://127.0.0.1:8080")).rstrip("/")
API_PREFIX = "/api/v1"
HTTP_TIMEOUT = float(_get("WARDEN_HTTP_TIMEOUT", "30"))
VERIFY_TLS = str(_get("WARDEN_VERIFY_TLS", "true")).lower() not in {"0", "false", "no"}

ADMIN_USERNAME = str(_get("WARDEN_ADMIN_USERNAME", "admin"))
ADMIN_PASSWORD = _get("WARDEN_ADMIN_PASSWORD") or _read_warden_env("WARDEN_ADMIN_PASSWORD")
ADMIN_API_KEY = _get("WARDEN_ADMIN_API_KEY") or _read_warden_secret("WARDEN_ADMIN_API_KEY")

# Cookie 会话的写请求必须带 Origin，服务端会与 WARDEN_CORS_ORIGIN 做精确比较。
CORS_ORIGIN = (
    _get("WARDEN_CORS_ORIGIN")
    or _read_warden_env("WARDEN_CORS_ORIGIN")
    or "http://localhost:4173"
)

TEST_TENANT_PREFIX = str(_get("WARDEN_TEST_TENANT_PREFIX", "e2e"))
TEST_TENANT_ADMIN_NAME = str(_get("WARDEN_TEST_TENANT_ADMIN_NAME", "e2e-admin"))

# 联邦断言登录：测试端持有签名私钥，与 warden 部署侧的
# WARDEN_FEDERATED_ASSERTION_PUBLIC_KEY 配对。未配置私钥则联邦用例 Skip。
FEDERATED_ASSERTION_ISSUER = str(
    _get("WARDEN_FEDERATED_ASSERTION_ISSUER", "https://idp.example.com")
)
FEDERATED_ASSERTION_AUDIENCE = str(_get("WARDEN_FEDERATED_ASSERTION_AUDIENCE", "warden"))

FEDERATED_PRIVATE_KEY = _get("WARDEN_TEST_FEDERATED_ASSERTION_PRIVATE_KEY")
FEDERATED_PRIVATE_KEY_FILE = _get("WARDEN_TEST_FEDERATED_ASSERTION_PRIVATE_KEY_FILE")


def federated_private_key() -> bytes | None:
    """返回测试端联邦签名私钥（PEM），未配置返回 None。"""
    if FEDERATED_PRIVATE_KEY:
        return FEDERATED_PRIVATE_KEY.encode("utf-8")
    if FEDERATED_PRIVATE_KEY_FILE:
        path = Path(FEDERATED_PRIVATE_KEY_FILE).expanduser()
        if path.exists():
            return path.read_bytes()
    return None


# AI 助手：WARDEN_TEST_AI_ENABLED 为真时跑 AI mock 用例（此时控制面的
# WARDEN_AI_BASE_URL 应已指向 mock 服务）。mock 端口需与控制面 BASE_URL 一致。
AI_MOCK_ENABLED = str(_get("WARDEN_TEST_AI_ENABLED", "false")).lower() in {
    "1", "true", "yes", "on",
}
AI_MOCK_PORT = int(_get("WARDEN_TEST_AI_MOCK_PORT", "9100"))

# OIDC：WARDEN_TEST_OIDC_ENABLED 为真时跑假 IdP 用例（控制面 WARDEN_OIDC_ISSUER
# 应已指向假 IdP）。mock 端口需与控制面 ISSUER 一致。
OIDC_MOCK_ENABLED = str(_get("WARDEN_TEST_OIDC_ENABLED", "false")).lower() in {
    "1", "true", "yes", "on",
}
OIDC_MOCK_PORT = int(_get("WARDEN_TEST_OIDC_MOCK_PORT", "9200"))


def require_admin_password() -> str:
    if not ADMIN_PASSWORD:
        raise RuntimeError(
            "缺少管理员密码：请设置 WARDEN_ADMIN_PASSWORD，"
            "或在 warden 仓库 .env 中配置后重试。"
        )
    return str(ADMIN_PASSWORD)


def require_admin_api_key() -> str:
    if not ADMIN_API_KEY:
        raise RuntimeError(
            "缺少管理员 API Key：请设置 WARDEN_ADMIN_API_KEY，"
            "或确保 warden 仓库已执行 scripts/init-local-secrets.sh。"
        )
    return str(ADMIN_API_KEY)


def base_url_with_prefix() -> str:
    return WARDEN_BASE_URL + API_PREFIX