# -*- coding = utf-8 -*-
"""统一断言工具。用例中不直接写原生 assert。"""
from __future__ import annotations

from typing import Any

import jsonschema

from tools.request import ApiResponse


def assert_condition(condition: Any, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_subset(actual: Any, expected: Any, path: str = "response") -> None:
    """递归校验 expected 是 actual 的子集。"""
    if isinstance(expected, dict):
        assert_condition(isinstance(actual, dict), f"{path} 应为 dict，实际为 {type(actual).__name__}")
        for key, value in expected.items():
            assert_condition(key in actual, f"{path} 缺少字段 {key!r}，实际字段: {sorted(actual)}")
            assert_subset(actual[key], value, f"{path}.{key}")
        return
    if isinstance(expected, list):
        assert_condition(isinstance(actual, list), f"{path} 应为 list，实际为 {type(actual).__name__}")
        assert_condition(
            len(actual) >= len(expected),
            f"{path} 长度不足：期望至少 {len(expected)}，实际 {len(actual)}",
        )
        for index, value in enumerate(expected):
            assert_subset(actual[index], value, f"{path}[{index}]")
        return
    assert_condition(actual == expected, f"{path} 期望 {expected!r}，实际 {actual!r}")


def assert_json(response: ApiResponse | dict, **expected: Any) -> None:
    body = response.body if isinstance(response, ApiResponse) else response
    assert_subset(body, expected)


def assert_error(
    response: ApiResponse,
    status: int | None = None,
    code: str | None = None,
    message_contains: str | None = None,
) -> None:
    if status is not None:
        assert_condition(
            response.status == status,
            f"期望 HTTP {status}，实际 {response.status}: {response.text[:1000]}",
        )
    body = response.body if isinstance(response.body, dict) else {}
    if code is not None:
        assert_condition(
            body.get("error") == code,
            f"期望错误码 {code}，实际 {body.get('error')!r}: {response.text[:1000]}",
        )
    if message_contains is not None:
        actual_message = str(body.get("message") or "")
        assert_condition(
            message_contains in actual_message,
            f"期望错误信息包含 {message_contains!r}，实际 {actual_message!r}",
        )


def assert_schema(data: Any, schema: dict) -> None:
    jsonschema.validate(instance=data, schema=schema)


def assert_contains_item(items: list[dict], message: str | None = None, **fields: Any) -> dict:
    for item in items:
        if all(item.get(key) == value for key, value in fields.items()):
            return item
    target = message or f"未找到匹配项: {fields}"
    raise AssertionError(f"{target}，实际数量 {len(items)}")