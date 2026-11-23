# -*- coding = utf-8 -*-
"""测试数据唯一标识。"""
from __future__ import annotations

import uuid


def unique_suffix() -> str:
    return uuid.uuid4().hex[:12]


def unique_slug(prefix: str = "e2e") -> str:
    """生成符合 warden tenant slug 规则的唯一值。"""
    safe_prefix = "".join(ch if ch.isalnum() else "-" for ch in prefix.lower()).strip("-") or "e2e"
    return f"{safe_prefix}-{unique_suffix()}"


def unique_name(prefix: str = "e2e") -> str:
    """生成 Connector / Principal / Project 等业务对象的唯一名称。"""
    return f"{prefix}-{unique_suffix()}"