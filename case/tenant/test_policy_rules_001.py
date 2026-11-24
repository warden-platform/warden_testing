# -*- coding = utf-8 -*-
"""策略矩阵规则（/policy-rules）黑盒契约。

覆盖：
- 规则创建、列表、更新、复制为停用副本、删除与 404；
- 字段级负向校验（名称、决策、环境、优先级、动作、项目、资源类型）；
- 模拟接口：矩阵可收紧 Rego ALLOW，但 Rego DENY 是不可绕过的下限。
"""
from __future__ import annotations

import pytest

from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_contains_item, assert_error, assert_json
from tools.ids import unique_name

pytestmark = pytest.mark.smoke

READ_ACTION = "network.device.get"


def _rule(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "name": unique_name("rule"),
        "decision": "DENY",
        "resource_type": "network_device",
        "action_name": READ_ACTION,
        "environment": "testing",
        "priority": 100,
        "enabled": True,
        "description": "e2e policy rule",
    }
    payload.update(overrides)
    return payload


def test_policy_rule_crud(tenant_admin: WardenClient, default_project: dict):
    payload = _rule()
    created = tenant_admin.create_policy_rule(project_id=default_project["id"], **payload)
    assert_condition(bool(created.get("id")), f"创建策略规则未返回 id: {created}")
    assert_json(
        created,
        name=payload["name"],
        project_id=default_project["id"],
        resource_type="network_device",
        action_name=READ_ACTION,
        environment="testing",
        decision="DENY",
        priority=100,
        enabled=True,
    )

    listed = tenant_admin.list_policy_rules() or []
    rule = assert_contains_item(listed, id=created["id"])
    assert_json(rule, decision="DENY", conflict_ids=[])

    updated = tenant_admin.update_policy_rule(
        created["id"],
        **{**payload, "decision": "REQUIRE_APPROVAL", "priority": 200},
    )
    assert_json(updated, id=created["id"], decision="REQUIRE_APPROVAL", priority=200, enabled=True)

    copy = tenant_admin.copy_policy_rule(created["id"])
    assert_condition(copy.get("id") != created["id"], "复制规则不应复用原 id")
    assert_json(copy, enabled=False, decision="REQUIRE_APPROVAL", priority=200)

    tenant_admin.delete_policy_rule(copy["id"])
    missing = tenant_admin.request(
        "DELETE", f"/api/v1/policy-rules/{copy['id']}", allow_error=True
    )
    assert_error(missing, status=404, code="POLICY_RULE_NOT_FOUND")

    missing_update = tenant_admin.request(
        "PUT",
        "/api/v1/policy-rules/00000000-0000-4000-8000-000000000000",
        json_body={**payload, "decision": "ALLOW"},
        allow_error=True,
    )
    assert_error(missing_update, status=404, code="POLICY_RULE_NOT_FOUND")

    tenant_admin.delete_policy_rule(created["id"])
    remaining = tenant_admin.list_policy_rules() or []
    assert_condition(
        all(item.get("id") != created["id"] for item in remaining),
        "删除后策略规则仍在列表中",
    )


def test_policy_rule_validation_negative(tenant_admin: WardenClient, default_project: dict):
    cases = [
        ({"name": ""}, "规则名称为必填"),
        ({"decision": "MAYBE"}, "规则决策无效"),
        ({"environment": "staging"}, "环境必须是所有、测试或生产"),
        ({"priority": 10001}, "优先级必须在 0 到 10000 之间"),
        ({"resource_type": "bad type!"}, "资源类型格式无效"),
        ({"action_name": "network.device.not_exist"}, "所选动作不存在"),
        ({"project_id": "00000000-0000-4000-8000-000000000000"}, "所选项目不存在"),
    ]
    for overrides, fragment in cases:
        payload = {**_rule(), "project_id": default_project["id"], **overrides}
        response = tenant_admin.request(
            "POST", "/api/v1/policy-rules", json_body=payload, allow_error=True
        )
        assert_error(
            response,
            status=400,
            code="INVALID_POLICY_RULE",
            message_contains=fragment,
        )


def test_policy_rule_simulation(tenant_admin: WardenClient, default_project: dict):
    allow_rule = tenant_admin.create_policy_rule(
        project_id=default_project["id"],
        name=unique_name("allow"),
        decision="ALLOW",
        resource_type="network_device",
        action_name=READ_ACTION,
        environment="testing",
        priority=500,
    )
    simulate = {
        "project_id": default_project["id"],
        "resource_type": "network_device",
        "action_name": READ_ACTION,
        "environment": "testing",
        "risk_level": "low",
        "principal_kind": "agent_instance",
    }

    matched = tenant_admin.simulate_policy_rule(base_decision="ALLOW", **simulate)
    assert_json(matched, base_decision="ALLOW", effective_decision="ALLOW", rego_deny_protected=False)
    assert_json(matched.get("matched_rule"), id=allow_rule["id"])

    # Rego 已经 DENY 时，矩阵 ALLOW 不能放宽。
    deny_floor = tenant_admin.simulate_policy_rule(base_decision="DENY", **simulate)
    assert_json(deny_floor, base_decision="DENY", effective_decision="DENY", rego_deny_protected=True)

    # 更高优先级的矩阵 DENY 可以收紧 Rego ALLOW。
    tenant_admin.create_policy_rule(
        project_id=default_project["id"],
        name=unique_name("deny"),
        decision="DENY",
        resource_type="network_device",
        action_name=READ_ACTION,
        environment="testing",
        priority=600,
    )
    tightened = tenant_admin.simulate_policy_rule(base_decision="ALLOW", **simulate)
    assert_json(tightened, effective_decision="DENY")

    invalid = tenant_admin.request(
        "POST",
        "/api/v1/policy-rules/simulate",
        json_body={**simulate, "base_decision": "MAYBE"},
        allow_error=True,
    )
    assert_error(invalid, status=400, code="INVALID_BASE_DECISION")
