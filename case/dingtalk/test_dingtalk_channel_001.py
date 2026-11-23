# -*- coding = utf-8 -*-
"""钉钉通知渠道（CRUD / 错误码 / 租户隔离）。"""
from __future__ import annotations

import pytest

from lib import factory
from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_error, assert_json
from tools.ids import unique_name

pytestmark = pytest.mark.dingtalk


def _channel_payload(**overrides) -> dict:
    payload = {
        "name": unique_name("dingtalk-channel"),
        "enabled": False,
        "events": ["access_request.created"],
        "open_conversation_id": unique_name("conv"),
    }
    payload.update(overrides)
    return payload


def test_dingtalk_channel_defaults_not_configured(tenant_admin: WardenClient):
    """未配置钉钉时，GET 返回默认渠道且 configured=false。"""
    channel = tenant_admin.get_dingtalk_channel()
    assert_json(channel, type="dingtalk", configured=False)


def test_dingtalk_enable_requires_config(tenant_admin: WardenClient):
    """未配置钉钉时启用渠道必须 409 DINGTALK_NOT_CONFIGURED。"""
    resp = tenant_admin.request(
        "PUT",
        "/api/v1/notification-channels/dingtalk",
        json_body=_channel_payload(enabled=True),
        allow_error=True,
    )
    assert_error(resp, status=409, code="DINGTALK_NOT_CONFIGURED")


def test_dingtalk_update_without_dingtalk_ok(tenant_admin: WardenClient):
    """未配置钉钉时 enabled=false 的更新应能成功（不触发真实推送）。"""
    payload = _channel_payload()
    channel = tenant_admin.update_dingtalk_channel(
        name=payload["name"],
        enabled=False,
        events=payload["events"],
        open_conversation_id=payload["open_conversation_id"],
    )
    assert_json(channel, type="dingtalk", enabled=False)


def test_dingtalk_update_invalid_name(tenant_admin: WardenClient):
    """空名称必须 400 INVALID_CHANNEL。"""
    resp = tenant_admin.request(
        "PUT",
        "/api/v1/notification-channels/dingtalk",
        json_body=_channel_payload(name="  "),
        allow_error=True,
    )
    assert_error(resp, status=400, code="INVALID_CHANNEL")


def test_dingtalk_update_invalid_event(tenant_admin: WardenClient):
    """不支持的事件必须 400 INVALID_CHANNEL。"""
    resp = tenant_admin.request(
        "PUT",
        "/api/v1/notification-channels/dingtalk",
        json_body=_channel_payload(events=["not.a.real.event"]),
        allow_error=True,
    )
    assert_error(resp, status=400, code="INVALID_CHANNEL")


def test_dingtalk_test_requires_config(tenant_admin: WardenClient):
    """未配置钉钉时 test 端点必须 409 DINGTALK_NOT_CONFIGURED。"""
    resp = tenant_admin.request(
        "POST", "/api/v1/notification-channels/dingtalk/test", allow_error=True
    )
    assert_error(resp, status=409, code="DINGTALK_NOT_CONFIGURED")


def test_dingtalk_requires_tenant_admin(agent: dict):
    """非租户管理员（Agent Key）不能读写渠道（403）。"""
    resp = agent["client"].request(
        "GET", "/api/v1/notification-channels/dingtalk", allow_error=True
    )
    assert_error(resp, status=403)


def test_dingtalk_group_tenant_isolation(tenant_factory):
    """同一审批群只能绑定一个租户，跨租户绑定必须 409 DINGTALK_GROUP_BOUND。"""
    tenant_a = tenant_factory("ding-a")
    tenant_b = tenant_factory("ding-b")
    admin_a = factory.tenant_admin_client(tenant_a)
    admin_b = factory.tenant_admin_client(tenant_b)
    group = unique_name("shared-conv")
    try:
        admin_a.update_dingtalk_channel(
            name=unique_name("ch-a"), enabled=False,
            events=["access_request.created"], open_conversation_id=group,
        )
        resp = admin_b.request(
            "PUT",
            "/api/v1/notification-channels/dingtalk",
            json_body=_channel_payload(open_conversation_id=group),
            allow_error=True,
        )
        assert_error(resp, status=409, code="DINGTALK_GROUP_BOUND")
    finally:
        admin_a.close()
        admin_b.close()