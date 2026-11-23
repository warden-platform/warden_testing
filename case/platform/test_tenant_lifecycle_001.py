# -*- coding = utf-8 -*-
"""平台租户生命周期。"""
from __future__ import annotations

import pytest

from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_error, assert_json, assert_contains_item

pytestmark = pytest.mark.smoke


def test_bootstrap_creates_tenant(platform_admin: WardenClient, tenant: dict):
    """bootstrap 应原子创建租户、默认项目和首个管理员。"""
    tenant_detail = platform_admin.get_tenant(tenant["slug"])
    assert_json(tenant_detail, slug=tenant["slug"], status="ACTIVE")
    assert_condition(tenant_detail.get("id"), "租户应返回 id")

    tenants = platform_admin.list_tenants()
    assert_contains_item(tenants, slug=tenant["slug"])

    assert_condition(tenant["administrator"].get("id"), "应返回管理员 Principal")
    assert_condition(
        tenant["administrator"].get("metadata", {}).get("role") == "tenant_admin",
        f"管理员角色不正确: {tenant['administrator']}",
    )


def test_duplicate_slug_rejected(platform_admin: WardenClient, tenant: dict):
    """重复 slug 必须返回 409。"""
    response = platform_admin.request(
        "POST",
        "/api/v1/tenants/bootstrap",
        json_body={
            "slug": tenant["slug"],
            "name": "Duplicate",
            "adminName": "another-admin",
            "adminPassword": "Another-Passw0rd-123",
        },
        allow_error=True,
    )
    assert_error(response, status=409, code="TENANT_CREATE_FAILED")


def test_invalid_slug_rejected(platform_admin: WardenClient):
    """非法 slug 必须返回 400。"""
    response = platform_admin.request(
        "POST",
        "/api/v1/tenants/bootstrap",
        json_body={
            "slug": "BAD SLUG",
            "name": "Bad",
            "adminName": "bad-admin",
            "adminPassword": "Bad-Passw0rd-123",
        },
        allow_error=True,
    )
    assert_error(response, status=400, code="INVALID_TENANT_BOOTSTRAP")


def test_disable_tenant_blocks_login(platform_admin: WardenClient, tenant_factory):
    """停用租户后，其管理员不能再登录。"""
    target = tenant_factory("disable")
    platform_admin.disable_tenant(target["slug"])
    detail = platform_admin.get_tenant(target["slug"])
    assert_json(detail, status="DISABLED")

    client = WardenClient()
    response = client.request(
        "POST",
        "/api/v1/auth/login",
        json_body={
            "username": f"{target['admin_name']}@{target['slug']}",
            "password": target["admin_password"],
        },
        allow_error=True,
    )
    assert_error(response, status=401, code="INVALID_CREDENTIALS")
    client.close()


def test_bootstrap_requires_platform_admin(tenant_admin: WardenClient):
    """普通租户管理员不能创建新租户。"""
    response = tenant_admin.request(
        "POST",
        "/api/v1/tenants/bootstrap",
        json_body={
            "slug": "should-not-exist",
            "name": "Nope",
            "adminName": "nope-admin",
            "adminPassword": "Nope-Passw0rd-123",
        },
        allow_error=True,
    )
    assert_error(response, status=403)