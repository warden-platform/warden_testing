# -*- coding = utf-8 -*-
"""UI 冒烟：资源目录 / 审批 / 审计三页。"""
from __future__ import annotations

import pytest

from case.ui.conftest import login_tenant
from config import environment

pytestmark = pytest.mark.ui

_PAGE_TITLES = {
    "/resources": "Resource Catalog · 资源目录",
    "/approvals": "Approval Queue · 待命队列",
    "/audit": "Audit Trail · 不可变审计时间线",
}


@pytest.mark.parametrize("path,title", list(_PAGE_TITLES.items()))
def test_page_renders(page, tenant_credentials, path, title):
    """租户管理员登录后，各页面应能导航到并渲染标题。"""
    login_tenant(page, tenant_credentials["login_name"], tenant_credentials["password"])
    page.goto(f"{environment.UI_BASE_URL}{path}")
    page.wait_for_selector(f"text={title}", timeout=15000)