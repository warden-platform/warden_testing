# -*- coding = utf-8 -*-
"""策略矩阵对执行决策的黑盒验证。

覆盖：
- DENY：只读动作被矩阵拒绝，执行落 FAILED/POLICY_DENIED，不下发任务；
- ALLOW：测试环境的变更动作被矩阵放宽为自动执行，不再进入审批；
- REQUIRE_APPROVAL：只读动作被矩阵收紧为审批，批准后才入队执行。
"""
from __future__ import annotations

import pytest

from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_error, assert_json
from tools.ids import unique_name
from tools.waitTool import wait_until

pytestmark = pytest.mark.connector

CHANGE_ACTION = "network.interface.description.update"


def _sync_device(connector: dict, agent: dict, name: str) -> dict:
    connector["client"].sync_network_device(name)
    return wait_until(
        lambda: agent["client"].find_resource(name, "network_device"),
        timeout=15,
        description=f"资源目录出现 {name}",
    )


def _sync_interface(connector: dict, agent: dict, device: str, name: str) -> dict:
    connector["client"].sync_network_interface(name, device)
    return wait_until(
        lambda: agent["client"].find_resource(name, "network_interface"),
        timeout=15,
        description=f"资源目录出现 {name}",
    )


def _find_pending_request(tenant_admin: WardenClient, execution_id: str) -> dict:
    for item in tenant_admin.list_access_requests(status="PENDING") or []:
        if item.get("execution_id") == execution_id:
            return item
    raise AssertionError(f"未找到执行 {execution_id} 的待审批请求")


def _create_change_execution(agent: dict, resource: dict, description: str) -> dict:
    return agent["client"].create_execution(
        resource_id=resource["id"],
        action=CHANGE_ACTION,
        action_version=1,
        parameters={"description": description, "previewHash": "a" * 64},
        reason="e2e policy enforcement",
    )


def test_policy_deny_blocks_readonly_execution(
    connector: dict, agent: dict, tenant_admin: WardenClient, default_project: dict
):
    device = unique_name("device-deny")
    resource = _sync_device(connector, agent, device)

    rule = tenant_admin.create_policy_rule(
        project_id=default_project["id"],
        name=unique_name("deny-read"),
        decision="DENY",
        resource_type="network_device",
        action_name="network.device.get",
        environment="testing",
        priority=500,
    )

    response = agent["client"].request(
        "POST",
        "/api/v1/executions",
        json_body={
            "resourceId": resource["id"],
            "action": "network.device.get",
            "actionVersion": 1,
            "parameters": {},
            "reason": "e2e policy deny",
        },
        allow_error=True,
    )
    assert_error(response, status=403)
    execution = response.body
    assert_json(execution, status="FAILED", errorCode="POLICY_DENIED", resourceId=resource["id"])

    task_ids = [task.get("executionId") for task in connector["client"].poll_tasks()]
    assert_condition(
        execution["id"] not in task_ids,
        f"被策略拒绝的执行不应下发到 Connector: {task_ids}",
    )

    events = tenant_admin.list_audit_events(executionId=execution["id"])
    actions = [event.get("action") for event in events]
    assert_condition("execution.failed" in actions, f"缺少 execution.failed 审计: {actions}")
    assert_condition(
        rule["name"] in (execution.get("errorMessage") or ""),
        f"拒绝原因应指明命中的策略规则: {execution}",
    )


@pytest.mark.approval
def test_policy_allow_skips_approval_for_change(
    connector: dict, agent: dict, tenant_admin: WardenClient, default_project: dict
):
    device = unique_name("device-allow")
    interface = unique_name("iface-allow")
    resource = _sync_interface(connector, agent, device, interface)

    # 基线：测试环境的变更动作默认 REQUIRE_APPROVAL。
    baseline = _create_change_execution(agent, resource, "e2e-baseline")
    assert_json(baseline, status="WAITING_APPROVAL")
    tenant_admin.reject_access_request(_find_pending_request(tenant_admin, baseline["id"])["id"])

    tenant_admin.create_policy_rule(
        project_id=default_project["id"],
        name=unique_name("allow-change"),
        decision="ALLOW",
        resource_type="network_interface",
        action_name=CHANGE_ACTION,
        environment="testing",
        priority=500,
    )

    execution = _create_change_execution(agent, resource, "e2e-auto")
    assert_json(execution, status="QUEUED")

    pending = [
        item
        for item in tenant_admin.list_access_requests(status="PENDING") or []
        if item.get("execution_id") == execution["id"]
    ]
    assert_condition(not pending, f"矩阵 ALLOW 后不应再产生审批请求: {pending}")

    task = wait_until(
        lambda: connector["client"].find_task(execution["id"]),
        timeout=20,
        description="Connector 领取被放宽的执行",
    )
    connector["client"].submit_result(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="SUCCEEDED",
        result={"description": "e2e-auto"},
    )
    final = agent["client"].wait_execution(execution["id"], statuses=("SUCCEEDED",), timeout=15)
    assert_json(final, status="SUCCEEDED", result={"description": "e2e-auto"})


@pytest.mark.approval
def test_policy_require_approval_for_readonly(
    connector: dict, agent: dict, tenant_admin: WardenClient, default_project: dict
):
    device = unique_name("device-approval")
    resource = _sync_device(connector, agent, device)

    tenant_admin.create_policy_rule(
        project_id=default_project["id"],
        name=unique_name("approve-read"),
        decision="REQUIRE_APPROVAL",
        resource_type="network_device",
        action_name="network.device.get",
        environment="testing",
        priority=500,
    )

    execution = agent["client"].create_execution(
        resource_id=resource["id"],
        action="network.device.get",
        action_version=1,
        parameters={},
        reason="e2e policy approval",
    )
    assert_json(execution, status="WAITING_APPROVAL")

    access_request = _find_pending_request(tenant_admin, execution["id"])
    approved = tenant_admin.approve_access_request(access_request["id"])
    assert_json(approved, status="APPROVED")

    wait_until(
        lambda: agent["client"].get_execution(execution["id"]),
        lambda item: item.get("status") == "QUEUED",
        timeout=15,
        description="审批通过后只读执行进入 QUEUED",
    )

    task = wait_until(
        lambda: connector["client"].find_task(execution["id"]),
        timeout=20,
        description="Connector 领取被收紧的只读执行",
    )
    connector["client"].submit_result(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="SUCCEEDED",
        result={"device": device, "reachable": True},
    )
    final = agent["client"].wait_execution(execution["id"], statuses=("SUCCEEDED",), timeout=15)
    assert_json(final, status="SUCCEEDED", result={"device": device, "reachable": True})
