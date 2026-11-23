# -*- coding = utf-8 -*-
"""UI 冒烟：登录链路。"""
from __future__ import annotations

import pytest

from config import environment

pytestmark = pytest.mark.ui


def test_platform_admin_login(page):
    """平台管理员应能从 /platform/login 成功登录并离开登录页。"""
    page.goto(f"{environment.UI_BASE_URL}/platform/login")
    page.fill('input[autocomplete="username"]', environment.ADMIN_USERNAME)
    page.fill('input[autocomplete="current-password"]', environment.require_admin_password())
    page.click("button.login-submit")
    # 登录成功后 URL 应离开 /platform/login（跳转到控制台）。
    page.wait_for_url(lambda url: "/login" not in url, timeout=15000)


def test_unauthenticated_login_rejected(page):
    """错误密码应留在登录页并给出错误提示。"""
    page.goto(f"{environment.UI_BASE_URL}/platform/login")
    page.fill('input[autocomplete="username"]', environment.ADMIN_USERNAME)
    page.fill('input[autocomplete="current-password"]', "wrong-password-123")
    page.click("button.login-submit")
    # 仍停留在登录页，且出现错误提示（用户名或密码错误）。
    page.wait_for_selector("text=用户名或密码错误", timeout=15000)