# -*- coding = utf-8 -*-
"""审批决策边界：拒绝、重复处理与审批能力校验。

覆盖：
- 拒绝后执行落 FAILED/APPROVAL_REJECTED，且不会下发任务；
- 已处理请求再次决策返回 409 ALREADY_PROCESSED；
- 无 warden:approve 能力的 Agent Key 不能审批。
"""
from __future__ import annotations

import pytest

from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_error, assert_json
from tools.ids import unique_name
from tools.waitTool import wait_until

pytestmark = pytest.mark.approval

CHANGE_ACTION = "network.interface.description.update"


def _find_pending_request(tenant_admin: WardenClient, execution_id: str) -> dict:
    for item in tenant_admin.list_access_requests(status="PENDING") or []:
        if item.get("execution_id") == execution_id:
            return item
    raise AssertionError(f"未找到执行 {execution_id} 的待审批请求")


def _waiting_change_execution(connector: dict, agent: dict, tenant_admin: WardenClient) -> tuple[dict, dict]:
    device = unique_name("device-approval")
    interface = unique_name("iface-approval")
    connector["client"].sync_network_device(device)
    connector["client"].sync_network_interface(interface, device)
    resource = wait_until(
        lambda: agent["client"].find_resource(interface, "network_interface"),
        timeout=15,
        description=f"资源目录出现 {interface}",
    )
    execution = agent["client"].create_execution(
        resource_id=resource["id"],
        action=CHANGE_ACTION,
        action_version=1,
        parameters={"description": "e2e-approval", "previewHash": "b" * 64},
        reason="e2e approval decision",
    )
    assert_json(execution, status="WAITING_APPROVAL")
    return execution, _find_pending_request(tenant_admin, execution["id"])


def test_reject_marks_execution_failed(
    connector: dict, agent: dict, tenant_admin: WardenClient
):
    execution, access_request = _waiting_change_execution(connector, agent, tenant_admin)

    rejected = tenant_admin.reject_access_request(access_request["id"])
    assert_json(rejected, status="REJECTED", id=access_request["id"])

    final = agent["client"].wait_execution(execution["id"], statuses=("FAILED",), timeout=10)
    assert_json(final, status="FAILED", errorCode="APPROVAL_REJECTED")

    task_ids = [item.get("executionId") for item in connector["client"].poll_tasks()]
    assert_condition(
        execution["id"] not in task_ids,
        f"被拒绝的执行不应下发到 Connector: {task_ids}",
    )

    repeated = tenant_admin.request(
        "POST",
        f"/api/v1/access-requests/{access_request['id']}/reject",
        allow_error=True,
    )
    assert_error(repeated, status=409, code="ALREADY_PROCESSED")


def test_agent_cannot_approve_request(
    connector: dict, agent: dict, tenant_admin: WardenClient
):
    _, access_request = _waiting_change_execution(connector, agent, tenant_admin)

    denied = agent["client"].request(
        "POST",
        f"/api/v1/access-requests/{access_request['id']}/approve",
        allow_error=True,
    )
    assert_error(denied, status=403, code="INSUFFICIENT_SCOPE")

    # 请求仍处于 PENDING，由有权限的租户管理员清理。
    still_pending = _find_pending_request(tenant_admin, access_request["execution_id"])
    assert_json(still_pending, id=access_request["id"], status="PENDING")
    tenant_admin.reject_access_request(access_request["id"])


def test_duplicate_approve_is_rejected(
    connector: dict, agent: dict, tenant_admin: WardenClient
):
    execution, access_request = _waiting_change_execution(connector, agent, tenant_admin)

    approved = tenant_admin.approve_access_request(access_request["id"])
    assert_json(approved, status="APPROVED")

    wait_until(
        lambda: agent["client"].get_execution(execution["id"]),
        lambda item: item.get("status") == "QUEUED",
        timeout=15,
        description="审批通过后执行进入 QUEUED",
    )

    repeated = tenant_admin.request(
        "POST",
        f"/api/v1/access-requests/{access_request['id']}/approve",
        allow_error=True,
    )
    assert_error(repeated, status=409, code="ALREADY_PROCESSED")

    cancelled = agent["client"].cancel_execution(execution["id"])
    assert_json(cancelled, status="CANCELLED")
