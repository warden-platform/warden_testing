# -*- coding = utf-8 -*-
"""测试 Connector 驱动的完整执行链路。

覆盖：
- 只读动作：QUEUED -> DISPATCHED -> SUCCEEDED
- 失败回传：FAILED + EXECUTION_ERROR
- 变更动作：WAITING_APPROVAL -> approve -> QUEUED -> SUCCEEDED
- 幂等键与取消
"""
from __future__ import annotations

import pytest

from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_contains_item, assert_json
from tools.ids import unique_name
from tools.waitTool import wait_until

pytestmark = [pytest.mark.connector]


def _assert_action_available(actions: list[dict], name: str, version: int = 1) -> dict:
    for item in actions:
        if item.get("name") == name and item.get("version") == version:
            assert_condition(
                item.get("available") is True,
                f"动作 {name}@{version} 不可用: {item}",
            )
            return item
    raise AssertionError(f"资源动作列表缺少 {name}@{version}: {[i.get('name') for i in actions]}")


def _find_pending_request(tenant_admin: WardenClient, execution_id: str) -> dict:
    requests = tenant_admin.list_access_requests(status="PENDING")
    for item in requests:
        if item.get("execution_id") == execution_id:
            return item
    raise AssertionError(f"未找到执行 {execution_id} 的待审批请求: {requests}")


def _poll_task(connector: dict, execution_id: str) -> dict:
    return wait_until(
        lambda: connector["client"].find_task(execution_id),
        timeout=20,
        interval=0.5,
        description=f"Connector 领取执行 {execution_id}",
    )


@pytest.mark.smoke
def test_readonly_execution_end_to_end(connector: dict, agent: dict, tenant_admin: WardenClient):
    device_name = unique_name("device")
    sync_result = connector["client"].sync_network_device(device_name)
    assert_json(sync_result, synced=1, total=1)

    resource = wait_until(
        lambda: agent["client"].find_resource(device_name, "network_device"),
        timeout=15,
        description=f"资源目录出现 {device_name}",
    )
    assert_json(resource, name=device_name, resource_type="network_device", status="ACTIVE")

    actions = agent["client"].resource_actions(resource["id"])
    _assert_action_available(actions, "network.device.get", 1)

    execution = agent["client"].create_execution(
        resource_id=resource["id"],
        action="network.device.get",
        action_version=1,
        parameters={},
        reason="e2e readonly execution",
    )
    # 创建响应里的 actionName 尚未 enrich，终态查询时再断言动作名
    assert_json(execution, status="QUEUED", resourceId=resource["id"])

    task = _poll_task(connector, execution["id"])
    assert_condition(task.get("dispatchToken"), f"TaskEnvelope 缺少 dispatchToken: {task}")
    assert_condition(
        str(task.get("signature", "")).startswith("hmac-sha256:"),
        f"TaskEnvelope 签名格式异常: {task}",
    )
    assert_json(task, resource={"id": resource["id"]}, action={"name": "network.device.get", "version": 1})

    result = connector["client"].submit_result(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="SUCCEEDED",
        result={"device": device_name, "reachable": True},
    )
    assert_json(result, status="accepted")

    final = agent["client"].wait_execution(
        execution["id"], statuses=("SUCCEEDED",), timeout=15
    )
    assert_json(
        final,
        status="SUCCEEDED",
        actionName="network.device.get",
        result={"device": device_name, "reachable": True},
    )

    events = tenant_admin.list_audit_events(executionId=execution["id"])
    actions_seen = [event.get("action") for event in events]
    assert_condition("execution.queued" in actions_seen, f"缺少 execution.queued 审计: {actions_seen}")
    assert_condition(
        "execution.completed" in actions_seen, f"缺少 execution.completed 审计: {actions_seen}"
    )


def test_failed_execution_result(connector: dict, agent: dict):
    device_name = unique_name("device-fail")
    connector["client"].sync_network_device(device_name)
    resource = wait_until(
        lambda: agent["client"].find_resource(device_name, "network_device"),
        timeout=15,
        description=f"资源目录出现 {device_name}",
    )
    execution = agent["client"].create_execution(
        resource["id"], "network.device.get", 1, {}, "e2e failure"
    )
    task = _poll_task(connector, execution["id"])
    connector["client"].submit_result(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="FAILED",
        result={},
        error="SIMULATED_FAILURE",
    )
    final = agent["client"].wait_execution(execution["id"], statuses=("FAILED",), timeout=15)
    assert_json(final, status="FAILED")
    assert_condition(
        final.get("errorCode") == "EXECUTION_ERROR",
        f"失败错误码应为 EXECUTION_ERROR: {final}",
    )


@pytest.mark.approval
def test_network_change_requires_approval(
    connector: dict, agent: dict, tenant_admin: WardenClient
):
    device_name = unique_name("device-change")
    interface_name = unique_name("iface")
    connector["client"].sync_network_device(device_name)
    connector["client"].sync_network_interface(interface_name, device_name)

    resource = wait_until(
        lambda: agent["client"].find_resource(interface_name, "network_interface"),
        timeout=15,
        description=f"资源目录出现 {interface_name}",
    )
    _assert_action_available(
        agent["client"].resource_actions(resource["id"]),
        "network.interface.description.update",
        1,
    )

    execution = agent["client"].create_execution(
        resource_id=resource["id"],
        action="network.interface.description.update",
        action_version=1,
        parameters={"description": "e2e-updated", "previewHash": "a" * 64},
        reason="e2e change approval",
    )
    assert_json(execution, status="WAITING_APPROVAL")

    access_request = _find_pending_request(tenant_admin, execution["id"])
    assert_json(access_request, status="PENDING", execution_id=execution["id"])

    approved = tenant_admin.approve_access_request(access_request["id"])
    assert_json(approved, status="APPROVED")

    queued = wait_until(
        lambda: agent["client"].get_execution(execution["id"]),
        lambda item: item.get("status") == "QUEUED",
        timeout=15,
        description="审批通过后执行进入 QUEUED",
    )
    assert_json(queued, status="QUEUED")

    task = _poll_task(connector, execution["id"])
    connector["client"].submit_result(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="SUCCEEDED",
        result={"description": "e2e-updated"},
    )
    final = agent["client"].wait_execution(execution["id"], statuses=("SUCCEEDED",), timeout=15)
    assert_json(final, status="SUCCEEDED", result={"description": "e2e-updated"})


def test_idempotency_key_returns_same_execution(connector: dict, agent: dict):
    device_name = unique_name("device-idem")
    connector["client"].sync_network_device(device_name)
    resource = wait_until(
        lambda: agent["client"].find_resource(device_name, "network_device"),
        timeout=15,
        description=f"资源目录出现 {device_name}",
    )
    idempotency_key = unique_name("idem")
    first = agent["client"].create_execution(
        resource["id"],
        "network.device.get",
        1,
        {},
        "e2e idempotency",
        idempotency_key=idempotency_key,
    )
    second = agent["client"].create_execution(
        resource["id"],
        "network.device.get",
        1,
        {},
        "e2e idempotency",
        idempotency_key=idempotency_key,
    )
    assert_condition(
        first["id"] == second["id"],
        f"相同 Idempotency-Key 应复用执行: {first['id']} != {second['id']}",
    )

    cancelled = agent["client"].cancel_execution(first["id"])
    assert_json(cancelled, status="CANCELLED")
    final = agent["client"].wait_execution(first["id"], statuses=("CANCELLED",), timeout=10)
    assert_json(final, status="CANCELLED")