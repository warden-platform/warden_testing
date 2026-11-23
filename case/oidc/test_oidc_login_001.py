# -*- coding = utf-8 -*-
"""OIDC（假 IdP）登录。"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from lib.control.client import WardenClient
from tools.assertTool import assert_condition

pytestmark = pytest.mark.oidc


def _start_flow(client: WardenClient) -> tuple[str, str]:
    start = client.oidc_start()
    assert_condition(start.status_code == 302, f"OIDC start 应 302，实际 {start.status_code}")
    qs = parse_qs(urlparse(start.headers.get("Location", "")).query)
    assert_condition("state" in qs and "nonce" in qs, f"authorize URL 缺少 state/nonce: {start.headers.get('Location')}")
    return qs["state"][0], qs["nonce"][0]


def test_oidc_login_roundtrip(fake_oidc):
    """假 IdP 应驱动 OIDC 授权码流程签出 warden session。"""
    client = WardenClient()
    try:
        state, nonce = _start_flow(client)
        code = fake_oidc.issue_code(nonce)

        cb = client.oidc_callback(code, state)
        assert_condition(cb.status_code == 302, f"回调应 302，实际 {cb.status_code}: {cb.text[:500]}")

        # 同一 session 已带 warden_session cookie，应能读到身份
        me = client.me()
        assert_condition(me.get("id"), f"OIDC 登录后应能 /auth/me 拿到身份: {me}")
    finally:
        client.close()


def test_oidc_callback_rejects_invalid_state(fake_oidc):
    """state 不匹配必须被拒（400 INVALID_OIDC_STATE）。"""
    client = WardenClient()
    try:
        state, nonce = _start_flow(client)
        code = fake_oidc.issue_code(nonce)
        cb = client.oidc_callback(code, state + "tampered")
        assert_condition(cb.status_code == 400, f"期望 400，实际 {cb.status_code}: {cb.text[:300]}")
        assert_condition(
            "INVALID_OIDC_STATE" in (cb.text or ""),
            f"错误码应含 INVALID_OIDC_STATE: {cb.text[:300]}",
        )
    finally:
        client.close()