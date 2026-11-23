# -*- coding = utf-8 -*-
"""UI 冒烟：pytest-playwright 的 base_url、启用门控、测试租户凭据。"""
from __future__ import annotations

import pytest

from config import environment


@pytest.fixture(scope="session")
def base_url() -> str:
    return environment.UI_BASE_URL


@pytest.fixture(scope="session", autouse=True)
def _require_ui_enabled():
    if not environment.UI_MOCK_ENABLED:
        pytest.skip("UI 冒烟未启用（未设置 WARDEN_TEST_UI_ENABLED）")


@pytest.fixture(scope="session")
def tenant_credentials() -> dict:
    """用平台管理员 API 创建一个业务测试租户，返回其管理员 UI 登录凭据。

    资源/审批/审计是业务租户侧页面，平台管理员登录只落在平台管理域。
    """
    from lib import factory
    from lib.control.client import WardenClient

    client = WardenClient()
    client.login(environment.ADMIN_USERNAME, environment.require_admin_password(), tenant="platform")
    tenant = factory.bootstrap_tenant(client, "ui")
    try:
        yield {
            "login_name": f"{tenant['admin_name']}@{tenant['slug']}",
            "password": tenant["admin_password"],
            "slug": tenant["slug"],
        }
    finally:
        try:
            client.disable_tenant(tenant["slug"])
        except Exception:
            pass
        client.close()


def login_tenant(page, login_name: str, password: str) -> None:
    """组织登录（用户名@组织标识 + 密码），等待离开登录页。"""
    page.goto(f"{environment.UI_BASE_URL}/login")
    page.fill('input[autocomplete="username"]', login_name)
    page.fill('input[autocomplete="current-password"]', password)
    page.click("button.login-submit")
    page.wait_for_url(lambda url: "/login" not in url, timeout=15000)