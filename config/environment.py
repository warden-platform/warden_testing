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