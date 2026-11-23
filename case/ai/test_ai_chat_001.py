# -*- coding = utf-8 -*-
"""AI 助手（mock LLM 后端）。"""
from __future__ import annotations

import pytest

from lib.control.client import WardenClient
from tools.assertTool import assert_condition

pytestmark = pytest.mark.ai


def test_ai_chat_roundtrip(tenant_admin: WardenClient, mock_llm):
    """mock LLM 应驱动 AI 助手返回 delta + done 事件。"""
    resp = tenant_admin.ai_chat("列出我的资源")
    assert_condition(
        resp.status_code == 200, f"期望 200，实际 {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.text or ""
    assert_condition("event: delta" in body, f"SSE 应包含 delta 事件: {body[:2000]}")
    assert_condition("event: done" in body, f"SSE 应包含 done 事件: {body[:2000]}")


def test_ai_chat_requires_auth(mock_llm):
    """未认证调用 AI 助手应被拒。"""
    client = WardenClient()
    try:
        resp = client.ai_chat("hi")
    finally:
        client.close()
    assert_condition(resp.status_code == 401, f"期望 401，实际 {resp.status_code}")