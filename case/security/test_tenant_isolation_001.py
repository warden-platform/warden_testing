# -*- coding = utf-8 -*-
"""跨租户隔离：资源、执行、Project、Principal 都不能越界。"""
from __future__ import annotations

import pytest

from lib import factory
from tools.assertTool import assert_condition, assert_error
from tools.ids import unique_name
from tools.waitTool import wait_until

pytestmark = [pytest.mark.security]


def test_cross_tenant_access_is_denied(tenant_factory):
    tenant_a = tenant_factory("iso-a")
    tenant_b = tenant_factory("iso-b")
    stack_a = factory.build_stack(tenant_a)
    stack_b = factory.build_stack(tenant_b)

    try:
        device_b = unique_name("device-b")
        stack_b["connector"]["client"].sync_network_device(device_b)
        resource_b = wait_until(
            lambda: stack_b["agent"]["client"].find_resource(device_b, "network_device"),
            timeout=15,
            description=f"B 租户资源出现: {device_b}",
        )
        execution_b = stack_b["agent"]["client"].create_execution(
            resource_b["id"], "network.device.get", 1, {}, "isolation"
        )

        # A 的 Agent 不能读取 B 的资源动作
        response = stack_a["agent"]["client"].request(
            "GET", f"/api/v1/resources/{resource_b['id']}/actions", allow_error=True
        )
        assert_error(response, status=404)

        # A 的 Agent 不能读取 B 的执行
        response = stack_a["agent"]["client"].request(
            "GET", f"/api/v1/executions/{execution_b['id']}", allow_error=True
        )
        assert_error(response, status=404)

        # A 的资源列表不包含 B 的资源
        resources_a = stack_a["agent"]["client"].list_resources()
        assert_condition(
            all(item.get("id") != resource_b["id"] for item in resources_a),
            f"A 租户资源列表泄露了 B 的资源: {resource_b['id']}",
        )

        # A 的租户管理员看不到 B 的 Principal
        principals_a = stack_a["admin"].list_principals()
        assert_condition(
            all(
                item.get("id") != stack_b["agent"]["principal"]["id"]
                for item in principals_a
            ),
            "A 租户 Principal 列表泄露了 B 的 Agent",
        )

        # A 的租户管理员不能读取 B 的项目成员
        response = stack_a["admin"].request(
            "GET",
            f"/api/v1/projects/{stack_b['project']['id']}/members",
            allow_error=True,
        )
        # 既可能直接 403/404，也可能在“按当前租户过滤”的语义下返回空列表；
        # 关键是不能返回 B 租户的任何成员数据。
        assert_condition(
            response.status in {403, 404}
            or (response.status == 200 and response.body == []),
            f"跨租户读取项目成员泄露了数据，实际 HTTP {response.status}: {response.text[:500]}",
        )
    finally:
        for stack in (stack_a, stack_b):
            stack["agent"]["client"].close()
            stack["connector"]["client"].close()
            stack["admin"].close()