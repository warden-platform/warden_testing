# -*- coding = utf-8 -*-
"""Connector 请求签名负向用例：错误 Key、篡改、过期、重放、缺失。"""
from __future__ import annotations

import time
import uuid

import pytest

from lib.connector.simulator import TestConnector
from tools.assertTool import assert_error
from tools.crypto import connector_signature_headers

pytestmark = [pytest.mark.connector, pytest.mark.security]

HEARTBEAT_PATH = "/api/v1/connectors/{id}/heartbeat"


def _path(connector: dict) -> str:
    return HEARTBEAT_PATH.format(id=connector["id"])


def test_wrong_signing_key_rejected(connector: dict):
    response = connector["client"].send_signed(
        "POST", _path(connector), key="x" * 32, allow_error=True
    )
    assert_error(response, status=401, code="CONNECTOR_UNAUTHORIZED")


def test_tampered_body_rejected(connector: dict):
    path = _path(connector)
    headers = connector_signature_headers(
        "POST", path, b"", connector["client"].signing_key
    )
    headers["Content-Type"] = "application/json"
    response = connector["client"].http.request(
        "POST",
        path,
        data=b'{"tampered":true}',
        headers=headers,
        allow_error=True,
    )
    assert_error(response, status=401, code="CONNECTOR_UNAUTHORIZED")


def test_stale_timestamp_rejected(connector: dict):
    response = connector["client"].send_signed(
        "POST",
        _path(connector),
        timestamp=int(time.time()) - 3600,
        allow_error=True,
    )
    assert_error(response, status=401, code="CONNECTOR_UNAUTHORIZED")


def test_replayed_nonce_rejected(connector: dict):
    nonce = uuid.uuid4().hex
    first = connector["client"].send_signed("POST", _path(connector), nonce=nonce)
    assert first.status == 200, f"首次请求应成功: {first.status} {first.text}"
    second = connector["client"].send_signed(
        "POST", _path(connector), nonce=nonce, allow_error=True
    )
    assert_error(second, status=401, code="CONNECTOR_UNAUTHORIZED")


def test_missing_signature_headers_rejected(connector: dict):
    response = connector["client"].http.request(
        "POST", _path(connector), data=b"", allow_error=True
    )
    assert_error(response, status=401, code="CONNECTOR_UNAUTHORIZED")