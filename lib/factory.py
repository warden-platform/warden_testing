# -*- coding = utf-8 -*-
"""测试数据工厂：租户、项目、Agent、Connector。"""
from __future__ import annotations

from config import environment
from lib.connector.simulator import TestConnector
from lib.control.client import WardenClient
from tools.ids import unique_name, unique_slug

TENANT_ADMIN_PASSWORD = "E2e-Passw0rd-123"


def new_tenant_payload(prefix: str | None = None) -> dict:
    slug = unique_slug(prefix or environment.TEST_TENANT_PREFIX)
    return {
        "slug": slug,
        "name": f"E2E {slug}",
        "admin_name": environment.TEST_TENANT_ADMIN_NAME,
        "admin_password": TENANT_ADMIN_PASSWORD,
    }


def bootstrap_tenant(platform_admin: WardenClient, prefix: str | None = None) -> dict:
    payload = new_tenant_payload(prefix)
    created = platform_admin.bootstrap_tenant(**payload)
    return {**payload, "tenant": created["tenant"], "administrator": created["administrator"]}


def tenant_admin_client(tenant: dict) -> WardenClient:
    client = WardenClient()
    client.login(
        f"{tenant['admin_name']}@{tenant['slug']}",
        tenant["admin_password"],
    )
    return client


def default_project(tenant_admin: WardenClient) -> dict:
    for project in tenant_admin.list_projects():
        if project.get("is_default"):
            return project
    raise AssertionError("租户缺少默认项目")


def create_agent(tenant_admin: WardenClient) -> dict:
    name = unique_name("agent")
    principal = tenant_admin.create_principal(
        name, kind="agent_instance", metadata={"external_agent_id": name}
    )
    credential = tenant_admin.create_api_key(principal["id"], unique_name("key"))
    client = WardenClient(api_key=credential["apiKey"])
    return {
        "principal": principal,
        "api_key": credential["apiKey"],
        "credential": credential["credential"],
        "client": client,
    }


def create_connector(tenant_admin: WardenClient, project: dict) -> dict:
    name = unique_name("connector")
    created = tenant_admin.create_network_connector(name, project_id=project["id"])
    simulator = TestConnector(
        connector_id=created["id"],
        name=name,
        signing_key=created["taskSigningKey"],
        base_url=environment.WARDEN_BASE_URL,
    )
    simulator.register()
    simulator.heartbeat()
    return {"id": created["id"], "name": name, "client": simulator, "created": created}


def build_stack(tenant: dict) -> dict:
    """为一个已存在的租户搭建管理员、默认项目、Agent 与 Connector。"""
    admin = tenant_admin_client(tenant)
    project = default_project(admin)
    agent = create_agent(admin)
    connector = create_connector(admin, project)
    return {
        "tenant": tenant,
        "admin": admin,
        "project": project,
        "agent": agent,
        "connector": connector,
    }


def create_tenant_stack(platform_admin: WardenClient, prefix: str | None = None) -> dict:
    """创建一个完整隔离的测试栈：租户 + 管理员 + 默认项目 + Agent + Connector。"""
    return build_stack(bootstrap_tenant(platform_admin, prefix))