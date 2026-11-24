# -*- coding = utf-8 -*-
"""租户并发保护阈值（maxConcurrentTasks）黑盒验证。

覆盖：
- 平台管理员调整阈值；非法阈值与非平台身份更新被拒绝；
- 在途执行达到阈值后新执行返回 429 CONCURRENCY_LIMIT_REACHED；
- 取消在途执行后额度释放，可再次提交。
"""
from __future__ import annotations

import pytest

from lib import factory
from lib.control.client import WardenClient
from tools.assertTool import assert_error, assert_json
from tools.ids import unique_name
from tools.waitTool import wait_until

pytestmark = pytest.mark.smoke


def test_concurrency_quota_limits_in_flight(
    platform_admin: WardenClient, tenant: dict
):
    stack = factory.build_stack(tenant)
    admin: WardenClient = stack["admin"]
    agent: dict = stack["agent"]
    connector: dict = stack["connector"]
    try:
        updated = platform_admin.update_tenant_quota(tenant["slug"], 1)
        assert_json(updated, maxConcurrentTasks=1)

        invalid = platform_admin.request(
            "PUT",
            f"/api/v1/tenants/{tenant['slug']}/quota",
            json_body={"maxConcurrentTasks": 0},
            allow_error=True,
        )
        assert_error(invalid, status=400, code="INVALID_CONCURRENCY_LIMIT")

        forbidden = admin.request(
            "PUT",
            f"/api/v1/tenants/{tenant['slug']}/quota",
            json_body={"maxConcurrentTasks": 2},
            allow_error=True,
        )
        assert_error(forbidden, status=403, code="INSUFFICIENT_SCOPE")

        device = unique_name("device-quota")
        connector["client"].sync_network_device(device)
        resource = wait_until(
            lambda: agent["client"].find_resource(device, "network_device"),
            timeout=15,
            description=f"资源目录出现 {device}",
        )

        first = agent["client"].create_execution(
            resource_id=resource["id"],
            action="network.device.get",
            action_version=1,
            parameters={},
            reason="e2e quota first",
        )
        assert_json(first, status="QUEUED")

        second = agent["client"].request(
            "POST",
            "/api/v1/executions",
            json_body={
                "resourceId": resource["id"],
                "action": "network.device.get",
                "actionVersion": 1,
                "parameters": {},
                "reason": "e2e quota second",
            },
            allow_error=True,
        )
        assert_error(second, status=429, code="CONCURRENCY_LIMIT_REACHED")

        agent["client"].cancel_execution(first["id"])
        agent["client"].wait_execution(first["id"], statuses=("CANCELLED",), timeout=10)

        third = agent["client"].create_execution(
            resource_id=resource["id"],
            action="network.device.get",
            action_version=1,
            parameters={},
            reason="e2e quota third",
        )
        assert_json(third, status="QUEUED")
        agent["client"].cancel_execution(third["id"])
    finally:
        connector["client"].close()
        agent["client"].close()
        admin.close()
