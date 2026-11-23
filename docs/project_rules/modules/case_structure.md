# 用例结构规范

## 结构模型

本仓库采用**标准 pytest 函数 + fixture + factory**（区别于「固定 `preset → case → reset` 三步结构」的写法）：

- 前置/后置由 `case/conftest.py` 的 fixture 托管，用例自己不写 setup/teardown。
- 数据由 `lib/factory.py` 创建，用例按需取。
- 每个用例（或每次 `tenant_factory()`）创建唯一 `e2e-*` 租户，结束自动停用。

## 新增用例步骤

1. 在对应目录新建 `case/<domain>/test_<module>_<number>.py`。
2. 从 `lib/factory.py` 或 `case/conftest.py` 取 fixture。
3. 接口调用只走 `WardenClient` / `TestConnector`。
4. 日志用 `zPrint()`，断言用 `tools/assertTool.py`。
5. 异步状态用 `wait_until()`，不要 `time.sleep()`。
6. 负向用例用 `allow_error=True` + `assert_error(...)`。

## 模板

```python
import pytest
from lib.control.client import WardenClient
from tools.assertTool import assert_error, assert_json

pytestmark = pytest.mark.smoke

def test_example(tenant_admin: WardenClient):
    projects = tenant_admin.list_projects()
    assert_json(projects[0], is_default=True)
```

## 命名

- 文件：`test_<模块>_<编号>.py`，如 `test_tenant_isolation_001.py`。
- 函数：`test_<描述>`，snake_case。
- 编号 `001` 起，新增时取同目录最大编号 +1。

## 测试标记

| 标记 | 含义 |
|------|------|
| `smoke` | 健康检查、登录、租户、项目、Principal |
| `connector` | 测试 Connector 与执行链路 |
| `security` | 越权、隔离、签名负向 |
| `approval` | 审批链路 |
| `slow` | 耗时较长 |