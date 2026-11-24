# -*- coding = utf-8 -*-
"""Connector 任务分发租约与结果回传边界。

覆盖：
- 错误 dispatchToken 被拒绝，执行保持 DISPATCHED，随后正确回传仍可成功；
- UNKNOWN 结果落 UNKNOWN/UNKNOWN_RESULT，且不会被自动重试；
- 终态结果重复回传幂等接受；
- 其他 Connector 冒领结果被拒绝（租户内通道绑定）。
"""
from __future__ import annotations

import pytest

from lib import factory
from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_error, assert_json
from tools.ids import unique_name
from tools.waitTool import wait_until

pytestmark = pytest.mark.connector


def _queued_execution(connector: dict, agent: dict, reason: str) -> tuple[dict, dict]:
    device = unique_name("device-dispatch")
    connector["client"].sync_network_device(device)
    resource = wait_until(
        lambda: agent["client"].find_resource(device, "network_device"),
        timeout=15,
        description=f"资源目录出现 {device}",
    )
    execution = agent["client"].create_execution(
        resource_id=resource["id"],
        action="network.device.get",
        action_version=1,
        parameters={},
        reason=reason,
    )
    assert_json(execution, status="QUEUED")
    task = wait_until(
        lambda: connector["client"].find_task(execution["id"]),
        timeout=20,
        description=f"Connector 领取执行 {execution['id']}",
    )
    assert_condition(task.get("dispatchToken"), f"TaskEnvelope 缺少 dispatchToken: {task}")
    return execution, task


def test_wrong_dispatch_token_keeps_execution_dispatched(connector: dict, agent: dict):
    execution, task = _queued_execution(connector, agent, "e2e wrong dispatch token")

    response = connector["client"].submit_result_response(
        execution_id=execution["id"],
        dispatch_token="00000000-0000-4000-8000-000000000000",
        status="SUCCEEDED",
        result={"ok": True},
    )
    assert_error(response, status=409, code="EXECUTION_STATE_CHANGED")
    assert_json(agent["client"].get_execution(execution["id"]), status="DISPATCHED")

    accepted = connector["client"].submit_result(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="SUCCEEDED",
        result={"ok": True},
    )
    assert_json(accepted, status="accepted")

    final = agent["client"].wait_execution(execution["id"], statuses=("SUCCEEDED",), timeout=15)
    assert_json(final, status="SUCCEEDED", result={"ok": True})


def test_unknown_result_marks_execution_unknown(connector: dict, agent: dict, tenant_admin: WardenClient):
    execution, task = _queued_execution(connector, agent, "e2e unknown result")

    connector["client"].submit_result(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="UNKNOWN",
        result={"replayed": False},
        error="目标连接中断，结果未知",
    )
    final = agent["client"].wait_execution(execution["id"], statuses=("UNKNOWN",), timeout=15)
    assert_json(final, status="UNKNOWN", errorCode="UNKNOWN_RESULT")
    assert_condition(final.get("errorMessage"), f"UNKNOWN 结果应带错误说明: {final}")

    # 终态后不再重新下发，禁止自动重试。
    task_ids = [item.get("executionId") for item in connector["client"].poll_tasks()]
    assert_condition(
        execution["id"] not in task_ids,
        f"UNKNOWN 终态不应再次下发任务: {task_ids}",
    )

    events = tenant_admin.list_audit_events(executionId=execution["id"])
    assert_condition(
        any(event.get("action") == "execution.failed" for event in events),
        f"UNKNOWN 结果缺少 execution.failed 审计: {events}",
    )


def test_duplicate_terminal_result_is_idempotent(connector: dict, agent: dict):
    execution, task = _queued_execution(connector, agent, "e2e duplicate result")

    first = connector["client"].submit_result_response(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="SUCCEEDED",
        result={"attempt": 1},
    )
    assert_json(first.body, status="accepted")

    second = connector["client"].submit_result_response(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="SUCCEEDED",
        result={"attempt": 2},
    )
    assert_json(second.body, status="accepted")

    final = agent["client"].get_execution(execution["id"])
    assert_json(final, status="SUCCEEDED", result={"attempt": 1})


def test_other_connector_cannot_submit_result(
    connector: dict, agent: dict, tenant_admin: WardenClient, default_project: dict
):
    execution, task = _queued_execution(connector, agent, "e2e cross connector result")

    other = factory.create_connector(tenant_admin, default_project)
    try:
        response = other["client"].submit_result_response(
            execution_id=execution["id"],
            dispatch_token=task["dispatchToken"],
            status="SUCCEEDED",
            result={"ok": True},
        )
        assert_error(response, status=409, code="INVALID_EXECUTION_STATE")
    finally:
        other["client"].close()
        tenant_admin.delete_connector(other["id"])

    assert_json(agent["client"].get_execution(execution["id"]), status="DISPATCHED")

    connector["client"].submit_result(
        execution_id=execution["id"],
        dispatch_token=task["dispatchToken"],
        status="SUCCEEDED",
        result={"ok": True},
    )
    final = agent["client"].wait_execution(execution["id"], statuses=("SUCCEEDED",), timeout=15)
    assert_json(final, status="SUCCEEDED")
