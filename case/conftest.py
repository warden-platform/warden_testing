# -*- coding = utf-8 -*-
"""全局 fixture：控制面健康检查、平台管理员、隔离租户、Agent、测试 Connector。"""
from __future__ import annotations

import pytest

from config import environment
from lib import factory
from lib.control.client import WardenClient
from tools.assertTool import assert_condition, assert_json
from tools.printTool import zPrint
from tools.request import ApiError
from tools.waitTool import wait_until


@pytest.fixture(scope="session", autouse=True)
def control_plane_ready():
    """启动前确认控制面可访问，避免每个用例给出晦涩的连接错误。"""
    client = WardenClient()
    try:
        wait_until(
            lambda: client.request("GET", "/api/v1/health", allow_error=True),
            lambda response: response.status == 200,
            timeout=10,
            interval=0.5,
            description=f"warden 控制面 {environment.WARDEN_BASE_URL}/api/v1/health",
        )
    except AssertionError as exc:
        pytest.exit(
            f"warden 控制面不可用: {environment.WARDEN_BASE_URL}\n"
            f"请先执行 scripts/stack_up.sh，或设置 WARDEN_BASE_URL。\n{exc}",
            returncode=2,
        )
    finally:
        client.close()
    zPrint(f"控制面就绪: {environment.WARDEN_BASE_URL}")


@pytest.fixture(scope="session")
def platform_admin() -> WardenClient:
    """平台管理员会话，用于租户生命周期。"""
    client = WardenClient()
    client.login(
        environment.ADMIN_USERNAME,
        environment.require_admin_password(),
        tenant="platform",
    )
    identity = client.me()
    assert_condition(
        identity.get("is_platform_admin") is True or identity.get("role") == "platform_admin",
        f"平台管理员登录身份异常: {identity}",
    )
    yield client
    try:
        client.logout()
    except Exception:
        pass
    client.close()


@pytest.fixture(scope="session")
def admin_api() -> WardenClient:
    """使用 WARDEN_ADMIN_API_KEY 的平台管理员客户端。"""
    client = WardenClient(api_key=environment.require_admin_api_key())
    response = client.request("GET", "/api/v1/resources", allow_error=True)
    assert_condition(
        response.status == 200,
        f"管理员 API Key 不可用: HTTP {response.status} {response.text[:500]}",
    )
    yield client
    client.close()


@pytest.fixture
def tenant_factory(platform_admin: WardenClient):
    """创建并在用例结束后停用隔离租户。"""
    created: list[dict] = []

    def create(prefix: str | None = None) -> dict:
        tenant = factory.bootstrap_tenant(platform_admin, prefix)
        created.append(tenant)
        return tenant

    yield create

    for tenant in reversed(created):
        try:
            platform_admin.disable_tenant(tenant["slug"])
        except Exception as exc:  # 清理失败不掩盖用例本身的失败
            zPrint(f"停用测试租户失败（可忽略）: {tenant['slug']}: {exc}")


@pytest.fixture
def tenant(tenant_factory) -> dict:
    return tenant_factory()


@pytest.fixture
def tenant_admin(tenant) -> WardenClient:
    client = factory.tenant_admin_client(tenant)
    identity = client.me()
    assert_json({"tenant": identity.get("tenant")}, tenant={"slug": tenant["slug"]})
    yield client
    client.close()


@pytest.fixture
def default_project(tenant_admin: WardenClient) -> dict:
    return factory.default_project(tenant_admin)


@pytest.fixture
def agent(tenant_admin: WardenClient, default_project: dict) -> dict:
    agent = factory.create_agent(tenant_admin)
    yield agent
    try:
        tenant_admin.revoke_api_key(agent["credential"]["id"])
    except Exception:
        pass
    try:
        tenant_admin.delete_principal(agent["principal"]["id"])
    except Exception:
        pass
    agent["client"].close()


@pytest.fixture
def connector(tenant_admin: WardenClient, default_project: dict) -> dict:
    connector = factory.create_connector(tenant_admin, default_project)
    yield connector
    connector["client"].close()
    try:
        tenant_admin.delete_connector(connector["id"])
    except Exception:
        pass


@pytest.fixture(scope="session")
def federated_signer():
    """联邦断言签名器。未配置测试端私钥时 Skip（联邦未启用）。"""
    private_key = environment.federated_private_key()
    if not private_key:
        pytest.skip(
            "联邦断言未配置：请设置 WARDEN_TEST_FEDERATED_ASSERTION_PRIVATE_KEY(_FILE)"
        )

    def sign(**kwargs: object) -> str:
        from tools import federation

        kwargs.setdefault("issuer", environment.FEDERATED_ASSERTION_ISSUER)
        kwargs.setdefault("audience", environment.FEDERATED_ASSERTION_AUDIENCE)
        return federation.build_assertion(private_key, **kwargs)

    return sign


@pytest.fixture(scope="session")
def mock_llm():
    """启动 mock OpenAI 兼容 LLM 服务。AI 未启用时 Skip。"""
    if not environment.AI_MOCK_ENABLED:
        pytest.skip("AI 助手未启用（未设置 WARDEN_TEST_AI_ENABLED）")
    from tools.mock_llm import MockLLMServer

    server = MockLLMServer(port=environment.AI_MOCK_PORT)
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def fake_oidc():
    """启动假 OIDC IdP。OIDC 未启用时 Skip。"""
    if not environment.OIDC_MOCK_ENABLED:
        pytest.skip("OIDC 未启用（未设置 WARDEN_TEST_OIDC_ENABLED）")
    from tools.fake_oidc import FakeOIDCProvider

    provider = FakeOIDCProvider(port=environment.OIDC_MOCK_PORT)
    provider.start()
    yield provider
    provider.stop()