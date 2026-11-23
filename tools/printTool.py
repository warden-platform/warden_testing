# -*- coding = utf-8 -*-
"""统一日志输出。用例中禁止直接 print()。"""
from __future__ import annotations

import os
import time


def zPrint(*args, **kwargs) -> None:
    """可全局关闭的调试输出。"""
    if os.environ.get("WARDEN_TEST_VERBOSE", "1").lower() in {"0", "false", "no", "off"}:
        return
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}]", *args, **kwargs)