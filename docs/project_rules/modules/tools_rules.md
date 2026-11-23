# 工具规则（日志 / 断言 / 轮询 / 脱敏 / ID）

## 日志

统一 `from tools.printTool import zPrint`，禁止裸 `print()`。

```python
zPrint(f"执行已提交: {execution_id}")
```

- `zPrint` 可被 `WARDEN_TEST_VERBOSE=0` 全局关闭。
- 关键节点（提交、审批、状态迁移、失败）都要有日志，方便排查。

## 断言

统一 `from tools.assertTool import ...`，禁止用正则解析 `str(response)`，禁止裸 `assert`。

| 函数 | 用途 |
|------|------|
| `assert_condition(cond, msg)` | 布尔断言 |
| `assert_json(response, **expected)` | 断言字段子集（递归） |
| `assert_subset(actual, expected, path)` | 递归校验子集 |
| `assert_error(response, status=None, code=None, message_contains=None)` | 负向用例断言状态码/错误码/信息 |
| `assert_schema(data, schema)` | jsonschema 校验 |
| `assert_contains_item(items, message=None, **fields)` | 列表中找匹配项并返回 |

```python
# 正向
assert_json(projects[0], is_default=True)

# 负向：allow_error=True 拿到响应后
assert_error(resp, status=404, code="NOT_FOUND")
```

## 轮询

统一 `from tools.waitTool import wait_until`，禁止固定 `time.sleep()` 等状态。

```python
from tools.waitTool import wait_until

wait_until(
    lambda: client.get_execution(execution_id),
    lambda e: e["status"] in ("SUCCEEDED", "FAILED"),
    timeout=30,
    interval=0.5,
    description="等待执行结束",
)
```

- `func` 抛 `AssertionError` 视为「尚未就绪」；其他异常直接抛。
- 客户端已封装 `WardenClient.wait_execution(...)`，执行状态优先用它。

## HTTP 与脱敏

统一 `tools/request.py`，注意：

- `HttpClient.request` 返回 `ApiResponse`（有 `.ok` `.json` `.body` `.status` `.text`）。
- `allow_error=True` 时不因非 2xx 抛错，交给 `assert_error` 断言；否则非 2xx 抛 `ApiError`。
- 写 allure 的请求/响应已自动脱敏（密码、API Key 等），不要另写裸的 `requests`。

## 唯一 ID

统一 `from tools.ids import unique_slug, unique_name`，保证测试数据唯一、可重复运行。

- `unique_slug(prefix="e2e")` → 租户 slug。
- `unique_name(prefix="e2e")` → 资源名。
- 不要手写固定 slug / 手机号，避免并行或重复运行互撞。