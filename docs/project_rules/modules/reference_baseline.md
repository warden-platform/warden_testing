# 参考基线

新增用例优先参考以下文件，不要从空白开始手写整套风格。

## 三级基线

| 关注点 | 参考文件 |
|--------|----------|
| 完整执行链路、审批、幂等 | `case/connector/test_connector_execution_001.py` |
| 认证与健康检查 | `case/platform/test_health_and_auth_001.py` |
| 跨租户安全 | `case/security/test_tenant_isolation_001.py` |
| 签名负向（错误 Key、篡改、重放、缺头） | `case/connector/test_connector_signature_negative_001.py` |
| Principal / API Key | `case/tenant/test_principals_and_keys_001.py` |

## 用法

- 写执行链路 → 先看 `test_connector_execution_001.py`，复用它的 `wait_execution` / 审批闭环写法。
- 写越权/隔离用例 → 先看 `test_tenant_isolation_001.py`，学习双租户对照与 404/空列表断言。
- 写签名负向 → 先看 `test_connector_signature_negative_001.py`，学习 `allow_error=True` + `assert_error` 的套路。

不要绕开基线去写单个超长测试函数，也不要复制使用已被 factory 提供的 fixture。