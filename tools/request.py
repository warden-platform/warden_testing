# -*- coding = utf-8 -*-
"""统一 HTTP 客户端。

- 自动拼接 base_url
- 默认把请求/响应脱敏后写入 allure，避免密码、Cookie、API Key 进入报告
- 非 2xx 默认抛 ApiError，负向用例可传 allow_error=True
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import allure
import requests

from config import environment
from tools.printTool import zPrint

_REDACT_KEYS = {
    "password",
    "apikey",
    "api_key",
    "tasksigningkey",
    "token",
    "secret",
    "clientsecret",
    "client_secret",
    "authorization",
    "cookie",
    "set-cookie",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if str(key).lower() in _REDACT_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _display_body(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            return "<binary body>"
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return body[:4000]
    try:
        return json.dumps(_redact(body), ensure_ascii=False, default=str)[:8000]
    except (TypeError, ValueError):
        return str(body)[:4000]


@dataclass
class ApiResponse:
    method: str
    url: str
    status: int
    headers: dict[str, str]
    body: Any
    text: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> Any:
        return self.body


class ApiError(AssertionError):
    """非 2xx 响应，携带完整 ApiResponse 便于断言与排查。"""

    def __init__(self, response: ApiResponse):
        self.response = response
        error_code = ""
        message = ""
        if isinstance(response.body, dict):
            error_code = str(response.body.get("error") or "")
            message = str(response.body.get("message") or "")
        super().__init__(
            f"{response.method} {response.url} -> HTTP {response.status} "
            f"{error_code} {message}".strip()
        )


class HttpClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        session: requests.Session | None = None,
    ):
        self.base_url = (base_url or environment.WARDEN_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else environment.HTTP_TIMEOUT
        self.session = session or requests.Session()
        self.headers = {
            "Accept": "application/json",
            # Cookie 会话的 POST/PUT/DELETE 必须与 WARDEN_CORS_ORIGIN 完全一致，
            # 否则服务端 CSRF 中间件会返回 403。Bearer Key 请求带该头无副作用。
            "Origin": environment.CORS_ORIGIN,
            **(headers or {}),
        }

    def close(self) -> None:
        self.session.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        data: bytes | str | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        allow_error: bool = False,
        attach: bool = True,
    ) -> ApiResponse:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        if json_body is not None and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"

        request_body: Any = data if data is not None else json_body
        kwargs: dict[str, Any] = {
            "headers": request_headers,
            "params": params,
            "timeout": self.timeout,
            "verify": environment.VERIFY_TLS,
        }
        if data is not None:
            kwargs["data"] = data
        elif json_body is not None:
            kwargs["json"] = json_body

        zPrint(f"-> {method.upper()} {url}")
        try:
            raw = self.session.request(method.upper(), url, **kwargs)
        except requests.RequestException as exc:
            raise AssertionError(f"请求失败: {method.upper()} {url}: {exc}") from exc

        text = raw.text or ""
        try:
            body = raw.json()
        except ValueError:
            body = None

        response = ApiResponse(
            method=method.upper(),
            url=url,
            status=raw.status_code,
            headers=dict(raw.headers),
            body=body,
            text=text,
        )
        zPrint(f"<- {response.status} {method.upper()} {url}")
        if attach:
            self._attach(response, request_body)
        if not response.ok and not allow_error:
            raise ApiError(response)
        return response

    @staticmethod
    def _attach(response: ApiResponse, request_body: Any) -> None:
        try:
            info = [
                f"{response.method} {response.url}",
                f"status: {response.status}",
                "request body:\n" + (_display_body(request_body) or "<empty>"),
                "response body:\n" + (_display_body(response.body) or response.text[:4000] or "<empty>"),
            ]
            allure.attach(
                "\n\n".join(info),
                "Request&Response",
                allure.attachment_type.TEXT,
            )
        except Exception:  # allure 未启用时不影响用例
            pass