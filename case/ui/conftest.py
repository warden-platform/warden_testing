# -*- coding = utf-8 -*-
"""UI 冒烟：pytest-playwright 的 base_url 与启用门控。"""
from __future__ import annotations

import pytest

from config import environment


@pytest.fixture(scope="session")
def base_url() -> str:
    return environment.UI_BASE_URL


@pytest.fixture(scope="session", autouse=True)
def _require_ui_enabled():
    if not environment.UI_MOCK_ENABLED:
        pytest.skip("UI 冒烟未启用（未设置 WARDEN_TEST_UI_ENABLED）")