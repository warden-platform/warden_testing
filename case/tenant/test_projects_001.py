# -*- coding = utf-8 -*-
"""项目 CRUD 与默认项目保护。"""
from __future__ import annotations

import pytest

from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_contains_item, assert_error, assert_json
from tools.ids import unique_name

pytestmark = pytest.mark.smoke


def test_default_project_exists(default_project: dict):
    assert_condition(default_project.get("is_default") is True, f"默认项目标记缺失: {default_project}")
    assert_condition(default_project.get("id"), "默认项目缺少 id")


def test_project_crud(tenant_admin: WardenClient, default_project: dict):
    name = unique_name("project")
    created = tenant_admin.create_project(name, "e2e project")
    assert_json(created, name=name, description="e2e project")
    assert_condition(created.get("is_default") is False, "新建项目不应是默认项目")

    projects = tenant_admin.list_projects()
    assert_contains_item(projects, id=created["id"], name=name)

    updated_name = f"{name}-updated"
    updated = tenant_admin.update_project(created["id"], updated_name, "updated")
    assert_json(updated, id=created["id"], name=updated_name)

    response = tenant_admin.delete_project(created["id"])
    assert_condition(response.status == 204, f"删除项目应返回 204，实际 {response.status}")
    remaining = tenant_admin.list_projects()
    assert_condition(
        all(item.get("id") != created["id"] for item in remaining),
        "删除后项目仍在列表中",
    )


def test_default_project_cannot_be_deleted(tenant_admin: WardenClient, default_project: dict):
    response = tenant_admin.request(
        "DELETE", f"/api/v1/projects/{default_project['id']}", allow_error=True
    )
    assert_error(response, status=409, code="PROJECT_PROTECTED")


def test_duplicate_project_name_rejected(tenant_admin: WardenClient):
    name = unique_name("project")
    tenant_admin.create_project(name)
    response = tenant_admin.request(
        "POST",
        "/api/v1/projects",
        json_body={"name": name, "description": ""},
        allow_error=True,
    )
    assert_error(response, status=409, code="PROJECT_NAME_CONFLICT")