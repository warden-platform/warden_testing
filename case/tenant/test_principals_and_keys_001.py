# -*- coding = utf-8 -*-
"""Agent Principal 与 API Key 生命周期。"""
from __future__ import annotations

import pytest

from lib import factory
from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_contains_item, assert_error
from tools.ids import unique_name

pytestmark = pytest.mark.smoke


def test_agent_principal_and_key(tenant_admin: WardenClient, agent: dict):
    principal = agent["principal"]
    principals = tenant_admin.list_principals(kind="agent_instance")
    assert_contains_item(principals, id=principal["id"], name=principal["name"])

    response = agent["client"].request("GET", "/api/v1/resources")
    assert_condition(response.status == 200, f"Agent Key 调用失败: {response.status}")


def test_api_key_plaintext_is_not_listed(tenant_admin: WardenClient, agent: dict):
    keys = tenant_admin.list_api_keys(agent["principal"]["id"])
    assert_condition(len(keys) >= 1, "应至少有一个 API Key")
    for key in keys:
        assert_condition("apiKey" not in key, f"列表不应返回明文 Key: {key}")
        assert_condition("key_hash" not in key, f"列表不应返回 Key Hash: {key}")


def test_revoke_key_takes_effect_immediately(tenant_admin: WardenClient):
    created = factory.create_agent(tenant_admin)
    try:
        assert created["client"].request("GET", "/api/v1/resources").status == 200
        tenant_admin.revoke_api_key(created["credential"]["id"])
        response = created["client"].request("GET", "/api/v1/resources", allow_error=True)
        assert_error(response, status=401)
    finally:
        created["client"].close()
        try:
            tenant_admin.delete_principal(created["principal"]["id"])
        except Exception:
            pass


def test_rotate_key_invalidates_old_key(tenant_admin: WardenClient):
    created = factory.create_agent(tenant_admin)
    try:
        rotated = tenant_admin.rotate_api_key(created["credential"]["id"])
        assert_condition(rotated.get("apiKey"), f"轮换应返回新 Key: {rotated}")
        new_client = WardenClient(api_key=rotated["apiKey"])
        try:
            assert new_client.request("GET", "/api/v1/resources").status == 200
        finally:
            new_client.close()
        old_response = created["client"].request("GET", "/api/v1/resources", allow_error=True)
        assert_error(old_response, status=401)
    finally:
        created["client"].close()
        try:
            tenant_admin.delete_principal(created["principal"]["id"])
        except Exception:
            pass


def test_invalid_scope_rejected(tenant_admin: WardenClient):
    principal = tenant_admin.create_principal(unique_name("agent"))
    try:
        response = tenant_admin.request(
            "POST",
            f"/api/v1/principals/{principal['id']}/api-keys",
            json_body={"name": unique_name("key"), "scopes": ["warden:admin"]},
            allow_error=True,
        )
        assert_error(response, status=400)
    finally:
        try:
            tenant_admin.delete_principal(principal["id"])
        except Exception:
            pass


def test_principal_metadata_cannot_escalate_role(tenant_admin: WardenClient):
    principal = tenant_admin.create_principal(
        unique_name("agent"), metadata={"role": "platform_admin"}
    )
    try:
        metadata = principal.get("metadata") or {}
        assert_condition("role" not in metadata, f"metadata.role 应被剥离: {principal}")
    finally:
        try:
            tenant_admin.delete_principal(principal["id"])
        except Exception:
            pass