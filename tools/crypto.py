# -*- coding = utf-8 -*-
"""Connector 请求签名协议（与 warden server/internal/domain/connector_request.go 对齐）。"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from urllib.parse import quote, urlencode

CONNECTOR_REQUEST_VERSION = "warden-connector-request-v1"


def build_path(path: str, params: dict | None = None) -> str:
    """构造参与签名的 path?query。"""
    if not params:
        return path
    query = urlencode(params, doseq=True, quote_via=quote)
    return f"{path}?{query}"


def connector_signature_headers(
    method: str,
    path: str,
    body: bytes | str = b"",
    key: bytes | str = b"",
    timestamp: int | float | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    """生成 X-Warden-Timestamp / Nonce / Signature 三个请求头。

    canonical string:
        warden-connector-request-v1
        METHOD
        path?query
        timestamp
        nonce
        sha256(body) hex
    """
    if isinstance(body, str):
        body = body.encode("utf-8")
    if isinstance(key, str):
        key = key.encode("utf-8")
    if len(key) < 32:
        raise ValueError("connector signing key must be at least 32 bytes")

    ts = str(int(time.time() if timestamp is None else timestamp))
    nonce = nonce or uuid.uuid4().hex
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(
        [CONNECTOR_REQUEST_VERSION, method.upper(), path, ts, nonce, body_hash]
    )
    signature = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "X-Warden-Timestamp": ts,
        "X-Warden-Nonce": nonce,
        "X-Warden-Signature": f"hmac-sha256:{signature}",
    }