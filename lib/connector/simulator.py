# -*- coding = utf-8 -*-
"""测试 Connector：复刻 warden Connector Runtime 的 HMAC 签名协议。

用途：
- 通过 POST /api/v1/connectors/network 获取一次性 taskSigningKey
- 签名注册、心跳、资源同步、任务轮询、结果回传
- 不依赖真实 Kubernetes / Jenkins / 网络设备，即可覆盖完整执行状态机
"""
from __future__ import annotations

import json
from typing import Any

from tools.crypto import build_path, connector_signature_headers
from tools.request import ApiResponse, HttpClient


NETWORK_CAPABILITIES = [
    "warden.change-safety@v1",
    "network.device.get@v1",
    "network.device.audit@v1",
    "network.device.health@v1",
    "network.interface.list@v1",
    "network.vlan.list@v1",
    "network.topology.lldp@v1",
    "network.link_aggregation.status@v1",
    "network.stp.status@v1",
    "network.port.health@v1",
    "network.mac.lookup@v1",
    "network.arp.lookup@v1",
    "network.interface.description.preview@v1",
    "network.interface.description.update@v1",
    "network.interface.access_vlan.preview@v1",
    "network.interface.access_vlan.update@v1",
    "network.interface.trunk_vlan.preview@v1",
    "network.interface.trunk_vlan.add@v1",
    "network.interface.trunk_vlan.remove@v1",
]


class TestConnector:
    # 避免 pytest 把该类当作测试类收集
    __test__ = False

    def __init__(
        self,
        connector_id: str,
        name: str,
        signing_key: str,
        base_url: str | None = None,
        environment: str = "testing",
        connector_type: str = "network",
        version: str = "0.1.0-e2e",
    ):
        self.connector_id = connector_id
        self.name = name
        self.signing_key = signing_key
        self.environment = environment
        self.connector_type = connector_type
        self.version = version
        self.http = HttpClient(base_url=base_url)
        self._sync_seq = 0

    def close(self) -> None:
        self.http.close()

    # ---------------------------------------------------------------- signing
    @staticmethod
    def _encode(payload: Any) -> bytes:
        if payload is None:
            return b""
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def send_signed(
        self,
        method: str,
        path: str,
        payload: Any = None,
        *,
        body: bytes | None = None,
        key: str | None = None,
        timestamp: int | float | None = None,
        nonce: str | None = None,
        params: dict | None = None,
        allow_error: bool = False,
    ) -> ApiResponse:
        signed_path = build_path(path, params)
        body_bytes = body if body is not None else self._encode(payload)
        headers = connector_signature_headers(
            method=method,
            path=signed_path,
            body=body_bytes,
            key=key if key is not None else self.signing_key,
            timestamp=timestamp,
            nonce=nonce,
        )
        headers["Content-Type"] = "application/json"
        return self.http.request(
            method,
            signed_path,
            data=body_bytes,
            headers=headers,
            allow_error=allow_error,
        )

    # ------------------------------------------------------------- lifecycle
    def register(self) -> dict:
        payload = {
            "name": self.name,
            "connectorType": self.connector_type,
            "environment": self.environment,
            "version": self.version,
            "capabilities": NETWORK_CAPABILITIES,
            "config": {"source": "warden_testing"},
        }
        return self.send_signed(
            "POST", "/api/v1/connectors/register", payload
        ).body

    def heartbeat(self) -> dict:
        return self.send_signed(
            "POST", f"/api/v1/connectors/{self.connector_id}/heartbeat"
        ).body

    def sync_resources(
        self, resources: list[dict], complete: bool = True, sync_id: str | None = None
    ) -> dict:
        self._sync_seq += 1
        payload = {
            "connectorId": self.connector_id,
            "syncId": sync_id or f"sync-{self.connector_id}-{self._sync_seq}",
            "complete": complete,
            "resources": resources,
        }
        return self.send_signed("POST", "/api/v1/resources/sync", payload).body

    def sync_network_device(self, name: str, external_id: str | None = None, **metadata: Any) -> dict:
        return self.sync_resources(
            [
                {
                    "externalId": external_id or name,
                    "name": name,
                    "namespace": "network",
                    "resourceType": "network_device",
                    "labels": {"vendor": "h3c", "source": "warden_testing"},
                    "annotations": {},
                    "metadata": metadata,
                }
            ]
        )

    def sync_network_interface(
        self, name: str, device_name: str, external_id: str | None = None, **metadata: Any
    ) -> dict:
        return self.sync_resources(
            [
                {
                    "externalId": external_id or f"{device_name}:{name}",
                    "name": name,
                    "namespace": device_name,
                    "resourceType": "network_interface",
                    "labels": {"vendor": "h3c", "source": "warden_testing"},
                    "annotations": {},
                    "metadata": metadata,
                }
            ]
        )

    # ---------------------------------------------------------------- tasks
    def poll_tasks(self) -> list[dict]:
        # 服务端没有待领取任务时返回 JSON null，这里统一归一为空列表。
        return self.send_signed(
            "GET", f"/api/v1/connectors/{self.connector_id}/tasks"
        ).body or []

    def submit_result(
        self,
        execution_id: str,
        dispatch_token: str,
        status: str = "SUCCEEDED",
        result: dict | None = None,
        error: str = "",
    ) -> dict:
        return self.submit_result_response(
            execution_id, dispatch_token, status, result, error
        ).body

    def submit_result_response(
        self,
        execution_id: str,
        dispatch_token: str,
        status: str = "SUCCEEDED",
        result: dict | None = None,
        error: str = "",
    ) -> ApiResponse:
        """回传执行结果并返回原始响应，供负向用例断言状态码与错误码。"""
        payload = {
            "dispatchToken": dispatch_token,
            "status": status,
            "result": result or {},
            "error": error,
        }
        return self.send_signed(
            "POST",
            f"/api/v1/connectors/{self.connector_id}/tasks/{execution_id}/result",
            payload,
            allow_error=True,
        )

    def find_task(self, execution_id: str) -> dict:
        for task in self.poll_tasks():
            if task.get("executionId") == execution_id:
                return task
        raise AssertionError(f"Connector 未领取到执行任务: {execution_id}")