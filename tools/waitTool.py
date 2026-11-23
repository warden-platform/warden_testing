# -*- coding = utf-8 -*-
"""条件轮询工具。禁止用固定 sleep 等待异步状态。"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from tools.printTool import zPrint


def wait_until(
    func: Callable[[], Any],
    predicate: Callable[[Any], bool] | None = None,
    timeout: float = 30,
    interval: float = 0.5,
    description: str = "condition",
) -> Any:
    """轮询执行 func，直到 predicate 返回 True 或超时。

    func 抛出的 AssertionError 会被视为“尚未就绪”，其他异常直接向上抛。
    """
    deadline = time.monotonic() + timeout
    last_value: Any = None
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            last_value = func()
            if predicate is None or predicate(last_value):
                return last_value
        except AssertionError as exc:  # 典型的“还没到目标状态”
            last_error = exc
        time.sleep(interval)
    detail = f"last_value={last_value!r}"
    if last_error is not None:
        detail += f", last_error={last_error}"
    zPrint(f"等待超时: {description}, {detail}")
    raise AssertionError(f"等待超时: {description}; {detail}")