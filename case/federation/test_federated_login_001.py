# -*- coding = utf-8 -*-
"""联邦断言登录（与 warden federated_auth.go 对齐）。"""
from __future__ import annotations

import time

import pytest

from lib.control.client import WardenClient
from tools import federation
from tools.assertTool import assert_condition, assert_error
from tools.ids import unique_name

pytestmark = pytest.mark.federated


def _bind_and_assertion_args(tenant_admin: WardenClient) -> dict:
    """绑定企业/Workspace 到当前租户，返回签断言所需参数。"""
    enterprise_id = unique_name("ent")
    workspace_id = unique_name("ws")
    subject = unique_name("user")
    tenant_admin.bind_federated_tenant(enterprise_id, workspace_id)
    return {
        "subject": subject,
        "enterprise_id": enterprise_id,
        "workspace_id": workspace_id,
        "email": f"{subject}@example.com",
        "display_name": subject,
    }


def test_federated_login_roundtrip(tenant_admin: WardenClient, federated_signer):
    """绑定后，合法断言应签发短效 Bearer token 并返回联邦用户主体。"""
    assertion = federated_signer(**_bind_and_assertion_args(tenant_admin))

    client = WardenClient()
    try:
        resp = client.federated_login(assertion)
    finally:
        client.close()

    assert_condition(resp.get("accessToken"), f"缺少 accessToken: {resp}")
    assert_condition(resp.get("tokenType") == "Bearer", "tokenType 应为 Bearer")
    assert_condition(resp.get("user", {}).get("id"), "应返回用户 Principal")
    assert_condition(
        resp.get("user", {}).get("metadata", {}).get("federated") is True,
        f"联邦用户 metadata.federated 应为 true: {resp.get('user')}",
    )


def test_federated_login_rejects_unbound_tenant(federated_signer):
    """未绑定的 enterprise/workspace 必须返回 403 FEDERATED_TENANT_NOT_BOUND。"""
    assertion = federated_signer(
        subject=unique_name("unbound-user"),
        enterprise_id=unique_name("unbound-ent"),
        workspace_id=unique_name("unbound-ws"),
    )
    client = WardenClient()
    try:
        response = client.request(
            "POST",
            "/api/v1/auth/federated/login",
            json_body={"assertion": assertion},
            allow_error=True,
        )
    finally:
        client.close()
    assert_error(response, status=403, code="FEDERATED_TENANT_NOT_BOUND")


def test_federated_login_rejects_replay(tenant_admin: WardenClient, federated_signer):
    """同一 jti 的断言只能使用一次，重放必须 401 ASSERTION_REPLAYED。"""
    assertion = federated_signer(**_bind_and_assertion_args(tenant_admin))

    client = WardenClient()
    try:
        first = client.federated_login(assertion)
        assert_condition(first.get("accessToken"), "首次登录应成功")

        response = client.request(
            "POST",
            "/api/v1/auth/federated/login",
            json_body={"assertion": assertion},
            allow_error=True,
        )
    finally:
        client.close()
    assert_error(response, status=401, code="ASSERTION_REPLAYED")


def test_federated_login_rejects_invalid_signature(federated_signer):
    """用不配对私钥签名的断言必须被拒（401 INVALID_ASSERTION）。"""
    rogue_private, _ = federation.generate_rsa_key_pair()
    rogue = federation.build_assertion(
        rogue_private,
        issuer="https://idp.example.com",
        audience="warden",
        subject=unique_name("rogue"),
        enterprise_id=unique_name("rogue-ent"),
        workspace_id=unique_name("rogue-ws"),
    )
    client = WardenClient()
    try:
        response = client.request(
            "POST",
            "/api/v1/auth/federated/login",
            json_body={"assertion": rogue},
            allow_error=True,
        )
    finally:
        client.close()
    assert_error(response, status=401, code="INVALID_ASSERTION")


def test_federated_login_rejects_expired_assertion(federated_signer):
    """过期断言必须被拒（401 INVALID_ASSERTION）。"""
    now = int(time.time())
    expired = federated_signer(
        subject=unique_name("expired-user"),
        enterprise_id=unique_name("expired-ent"),
        workspace_id=unique_name("expired-ws"),
        now=now - 400,  # exp 已过
    )
    client = WardenClient()
    try:
        response = client.request(
            "POST",
            "/api/v1/auth/federated/login",
            json_body={"assertion": expired},
            allow_error=True,
        )
    finally:
        client.close()
    assert_error(response, status=401, code="INVALID_ASSERTION")