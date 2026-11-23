# -*- coding = utf-8 -*-
"""健康检查与认证主链路。"""
from __future__ import annotations

import pytest

from config import environment
from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_error, assert_json

pytestmark = pytest.mark.smoke


def test_health_endpoints():
    """公开健康检查必须始终可用。"""
    client = WardenClient()
    assert_json(client.health(), status="ready")
    assert_condition(client.livez().status == 200, "livez 应返回 200")
    assert_condition(client.readyz().status == 200, "readyz 应返回 200")
    client.close()


def test_unauthenticated_me_returns_401():
    """未登录访问 /auth/me 必须返回 401。"""
    client = WardenClient()
    response = client.request("GET", "/api/v1/auth/me", allow_error=True)
    assert_error(response, status=401)
    client.close()


def test_platform_admin_login_and_me(platform_admin: WardenClient):
    """平台管理员登录后应获得 platform_admin 与 warden:admin 能力。"""
    identity = platform_admin.me()
    assert_condition(identity.get("is_platform_admin") is True, f"应为平台管理员: {identity}")
    assert_condition("warden:admin" in (identity.get("scopes") or []), "缺少 warden:admin scope")
    assert_condition("warden:admin" in (identity.get("capabilities") or []), "缺少 warden:admin capability")


def test_tenant_admin_login_and_me(tenant_admin: WardenClient, tenant: dict):
    """租户管理员登录后应被绑定到本租户，并拥有审批能力。"""
    identity = tenant_admin.me()
    assert_condition(
        identity.get("tenant", {}).get("slug") == tenant["slug"],
        f"租户归属不正确: {identity}",
    )
    assert_condition("warden:tenant:admin" in (identity.get("scopes") or []), "缺少租户管理员 scope")
    assert_condition("warden:approve" in (identity.get("capabilities") or []), "缺少审批能力")


def test_admin_api_key_can_read_resources(admin_api: WardenClient):
    """WARDEN_ADMIN_API_KEY 应可作为平台管理员 Bearer Key 使用。"""
    response = admin_api.request("GET", "/api/v1/resources")
    assert_condition(response.status == 200, f"管理员 Key 调用失败: {response.status}")
    assert_condition(isinstance(response.body, list), f"资源列表应为数组: {response.body}")


def test_logout_revokes_session():
    """登出后同一会话不能再访问 /auth/me。"""
    client = WardenClient()
    client.login(
        environment.ADMIN_USERNAME,
        environment.require_admin_password(),
        tenant="platform",
    )
    assert_condition(client.me().get("id"), "登录后 /auth/me 应返回身份")
    client.logout()
    response = client.request("GET", "/api/v1/auth/me", allow_error=True)
    assert_error(response, status=401)
    client.close()