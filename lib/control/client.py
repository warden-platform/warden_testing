# -*- coding = utf-8 -*-
"""warden 控制面 API 封装。case 层只编排，不写裸请求。"""
from __future__ import annotations

from typing import Any

from config import environment
from tools.assertTool import assert_condition
from tools.request import ApiResponse, HttpClient
from tools.waitTool import wait_until


class WardenClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        api_key: str | None = None,
    ):
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.http = HttpClient(base_url=base_url, timeout=timeout, headers=headers)
        self.base_url = self.http.base_url
        self.api_key = api_key

    # ------------------------------------------------------------------ core
    def close(self) -> None:
        self.http.close()

    def request(self, method: str, path: str, **kwargs: Any) -> ApiResponse:
        return self.http.request(method, path, **kwargs)

    @staticmethod
    def _api(path: str) -> str:
        return path if path.startswith("/api/") else f"{environment.API_PREFIX}{path}"

    def as_api_key(self, api_key: str) -> "WardenClient":
        """使用另一个 API Key 发起独立会话（不继承当前 Cookie）。"""
        return WardenClient(base_url=self.base_url, timeout=self.http.timeout, api_key=api_key)

    def new_session(self) -> "WardenClient":
        """创建不携带任何凭据的新客户端，用于登录/未认证场景。"""
        return WardenClient(base_url=self.base_url, timeout=self.http.timeout)

    # -------------------------------------------------------------- health/auth
    def health(self) -> Any:
        return self.request("GET", self._api("/health")).body

    def livez(self) -> ApiResponse:
        return self.request("GET", "/livez")

    def readyz(self) -> ApiResponse:
        return self.request("GET", "/readyz")

    def login(self, username: str, password: str, tenant: str | None = None) -> dict:
        payload: dict[str, Any] = {"username": username, "password": password}
        if tenant:
            payload["tenant"] = tenant
        return self.request("POST", self._api("/auth/login"), json_body=payload).body

    def me(self) -> dict:
        return self.request("GET", self._api("/auth/me")).body

    def logout(self) -> dict:
        return self.request("POST", self._api("/auth/logout")).body

    def federated_login(self, assertion: str) -> dict:
        """联邦断言登录，返回 accessToken（短效 Bearer，不含 session cookie）。"""
        return self.request(
            "POST", self._api("/auth/federated/login"), json_body={"assertion": assertion}
        ).body

    # -------------------------------------------------------------- tenants
    def bootstrap_tenant(
        self,
        slug: str,
        name: str,
        admin_name: str,
        admin_password: str,
        max_concurrent_tasks: int | None = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "slug": slug,
            "name": name,
            "adminName": admin_name,
            "adminPassword": admin_password,
        }
        if max_concurrent_tasks is not None:
            payload["quota"] = {"maxConcurrentTasks": max_concurrent_tasks}
        return self.request("POST", self._api("/tenants/bootstrap"), json_body=payload).body

    def list_tenants(self) -> list[dict]:
        return self.request("GET", self._api("/tenants")).body

    def get_tenant(self, slug: str) -> dict:
        return self.request("GET", self._api(f"/tenants/{slug}")).body

    def disable_tenant(self, slug: str) -> Any:
        return self.request("POST", self._api(f"/tenants/{slug}/disable")).body

    # -------------------------------------------------------------- projects
    def list_projects(self) -> list[dict]:
        return self.request("GET", self._api("/projects")).body

    def create_project(self, name: str, description: str = "") -> dict:
        return self.request(
            "POST", self._api("/projects"), json_body={"name": name, "description": description}
        ).body

    def update_project(self, project_id: str, name: str, description: str = "") -> dict:
        return self.request(
            "PUT",
            self._api(f"/projects/{project_id}"),
            json_body={"name": name, "description": description},
        ).body

    def delete_project(self, project_id: str) -> ApiResponse:
        return self.request("DELETE", self._api(f"/projects/{project_id}"))

    # --------------------------------------------------------------- federated
    def bind_federated_tenant(self, enterprise_id: str, workspace_id: str) -> dict:
        """把外部企业/Workspace 绑定到当前租户（供联邦断言登录路由）。"""
        return self.request(
            "POST",
            self._api("/federated/tenants"),
            json_body={
                "source": "federated",
                "externalEnterpriseId": enterprise_id,
                "externalWorkspaceId": workspace_id,
            },
        ).body

    def list_federated_tenants(self) -> list[dict]:
        return self.request("GET", self._api("/federated/tenants")).body

    def bind_federated_project(
        self, workspace_id: str, external_project_id: str, project_id: str, name: str = ""
    ) -> dict:
        return self.request(
            "POST",
            self._api("/federated/projects"),
            json_body={
                "source": "federated",
                "externalWorkspaceId": workspace_id,
                "externalProjectId": external_project_id,
                "externalProjectName": name,
                "projectId": project_id,
            },
        ).body

    def list_federated_projects(self) -> list[dict]:
        return self.request("GET", self._api("/federated/projects")).body

    def revoke_federated_project(self, binding_id: str) -> ApiResponse:
        return self.request("DELETE", self._api(f"/federated/projects/{binding_id}"))

    # ------------------------------------------------------------------ ai
    def ai_chat(self, message: str, conversation_id: str | None = None):
        """调用 AI 助手（SSE 流式响应）。返回 requests.Response，由用例解析 SSE 事件。

        不自动抛错：正向/负向都用 status_code + 文本断言。
        """
        import requests

        url = f"{self.base_url}{environment.API_PREFIX}/ai/chat"
        # 复用 HttpClient 的统一请求头（含 CSRF Origin、Accept），覆盖 Accept 为 SSE。
        headers = dict(self.http.headers)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "text/event-stream"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {"message": message}
        if conversation_id:
            payload["conversationId"] = conversation_id
        try:
            return self.http.session.request(
                "POST",
                url,
                json=payload,
                headers=headers,
                timeout=self.http.timeout,
                verify=environment.VERIFY_TLS,
            )
        except requests.RequestException as exc:  # pragma: no cover
            raise AssertionError(f"AI 请求失败: {exc}") from exc

    # ------------------------------------------------------------------ oidc
    def oidc_start(self):
        """发起 OIDC 登录，返回 302 响应（Location 指向 IdP authorize，不自动跳转）。

        调用方需用同一 Session 继续调用 oidc_callback，以保持 oidc_* cookie。
        """
        import requests

        url = f"{self.base_url}{environment.API_PREFIX}/auth/oidc/start"
        try:
            return self.http.session.get(
                url,
                allow_redirects=False,
                timeout=self.http.timeout,
                verify=environment.VERIFY_TLS,
            )
        except requests.RequestException as exc:  # pragma: no cover
            raise AssertionError(f"OIDC start 失败: {exc}") from exc

    def oidc_callback(self, code: str, state: str):
        """携带 code/state 回调，返回 302 响应（成功后 Set-Cookie warden_session）。"""
        import requests

        url = f"{self.base_url}{environment.API_PREFIX}/auth/oidc/callback"
        try:
            return self.http.session.get(
                url,
                params={"code": code, "state": state},
                allow_redirects=False,
                timeout=self.http.timeout,
                verify=environment.VERIFY_TLS,
            )
        except requests.RequestException as exc:  # pragma: no cover
            raise AssertionError(f"OIDC callback 失败: {exc}") from exc

    # ------------------------------------------------------------- principals
    def list_principals(self, kind: str | None = None) -> list[dict]:
        params = {"kind": kind} if kind else None
        return self.request("GET", self._api("/principals"), params=params).body

    def create_principal(
        self, name: str, kind: str = "agent_instance", metadata: dict | None = None
    ) -> dict:
        return self.request(
            "POST",
            self._api("/principals"),
            json_body={"name": name, "kind": kind, "metadata": metadata or {}},
        ).body

    def delete_principal(self, principal_id: str) -> Any:
        return self.request("DELETE", self._api(f"/principals/{principal_id}")).body

    # -------------------------------------------------------------- api keys
    def create_api_key(
        self,
        principal_id: str,
        name: str,
        scopes: list[str] | None = None,
        expires_at: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "name": name,
            "scopes": scopes or [
                "warden:resources:read",
                "warden:executions:create",
                "warden:executions:read:self",
                "warden:executions:cancel:self",
            ],
        }
        if expires_at:
            payload["expiresAt"] = expires_at
        return self.request(
            "POST", self._api(f"/principals/{principal_id}/api-keys"), json_body=payload
        ).body

    def list_api_keys(self, principal_id: str) -> list[dict]:
        return self.request("GET", self._api(f"/principals/{principal_id}/api-keys")).body

    def revoke_api_key(self, key_id: str) -> Any:
        return self.request("POST", self._api(f"/api-keys/{key_id}/revoke")).body

    def rotate_api_key(self, key_id: str) -> dict:
        return self.request("POST", self._api(f"/api-keys/{key_id}/rotate")).body

    # ------------------------------------------------------------- connectors
    def create_network_connector(
        self, name: str, environment: str = "testing", project_id: str | None = None
    ) -> dict:
        payload: dict[str, Any] = {"name": name, "environment": environment}
        if project_id:
            payload["projectId"] = project_id
        return self.request(
            "POST", self._api("/connectors/network"), json_body=payload
        ).body

    def list_connectors(self) -> list[dict]:
        return self.request("GET", self._api("/connectors")).body

    def archive_connector(self, connector_id: str) -> Any:
        return self.request("POST", self._api(f"/connectors/{connector_id}/archive")).body

    def delete_connector(self, connector_id: str) -> Any:
        return self.request("DELETE", self._api(f"/connectors/{connector_id}")).body

    # -------------------------------------------------------------- resources
    def list_resources(self, **params: Any) -> list[dict]:
        return self.request("GET", self._api("/resources"), params=params).body

    def find_resource(self, name: str, resource_type: str | None = None) -> dict:
        resources = self.list_resources()
        for item in resources:
            if item.get("name") != name:
                continue
            if resource_type and item.get("resource_type") != resource_type:
                continue
            return item
        raise AssertionError(f"未找到资源 name={name!r}, resource_type={resource_type!r}")

    def resource_actions(self, resource_id: str, include_unavailable: bool = False) -> list[dict]:
        params = {"includeUnavailable": "true"} if include_unavailable else None
        return self.request(
            "GET", self._api(f"/resources/{resource_id}/actions"), params=params
        ).body

    # ------------------------------------------------------------- executions
    def create_execution(
        self,
        resource_id: str,
        action: str,
        action_version: int = 1,
        parameters: dict | None = None,
        reason: str = "",
        idempotency_key: str | None = None,
        acting_project_id: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "resourceId": resource_id,
            "action": action,
            "actionVersion": action_version,
            "parameters": parameters or {},
            "reason": reason,
        }
        if acting_project_id:
            payload["actingProjectId"] = acting_project_id
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self.request(
            "POST", self._api("/executions"), json_body=payload, headers=headers
        ).body

    def get_execution(self, execution_id: str) -> dict:
        return self.request("GET", self._api(f"/executions/{execution_id}")).body

    def list_executions(self, **params: Any) -> list[dict]:
        return self.request("GET", self._api("/executions"), params=params).body

    def cancel_execution(self, execution_id: str) -> dict:
        return self.request("POST", self._api(f"/executions/{execution_id}/cancel")).body

    def wait_execution(
        self,
        execution_id: str,
        statuses: tuple[str, ...] = ("SUCCEEDED", "FAILED", "UNKNOWN", "CANCELLED"),
        timeout: float = 30,
    ) -> dict:
        return wait_until(
            lambda: self.get_execution(execution_id),
            lambda item: item.get("status") in statuses,
            timeout=timeout,
            description=f"execution {execution_id} terminal status",
        )

    # ---------------------------------------------------------- access requests
    def list_access_requests(self, status: str | None = None) -> list[dict]:
        params = {"status": status} if status else None
        return self.request("GET", self._api("/access-requests"), params=params).body

    def approve_access_request(self, request_id: str) -> dict:
        return self.request("POST", self._api(f"/access-requests/{request_id}/approve")).body

    def reject_access_request(self, request_id: str) -> dict:
        return self.request("POST", self._api(f"/access-requests/{request_id}/reject")).body

    # -------------------------------------------------------------- audit
    def list_audit_events(self, **params: Any) -> list[dict]:
        return self.request("GET", self._api("/audit-events"), params=params).body


def assert_client_is_tenant_admin(client: WardenClient, tenant_slug: str) -> dict:
    identity = client.me()
    assert_condition(
        isinstance(identity, dict) and identity.get("tenant", {}).get("slug") == tenant_slug,
        f"当前身份不属于租户 {tenant_slug}: {identity}",
    )
    capabilities = identity.get("capabilities") or []
    assert_condition("warden:approve" in capabilities, f"租户管理员缺少审批能力: {capabilities}")
    return identity