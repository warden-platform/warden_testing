# 一句话硬规则

本文件是最小规则集，任何任务开始时若只读一个模块，读这个。

## 不可违反

1. **凭据不出库**：真实凭据只从进程环境变量、本仓库 `.env`、warden 仓库 `.env` / `var/warden/secrets.json` 读取；仓库内禁止硬编码地址、密码、Key、DSN。
2. **case/ 只编排**：禁止在 `case/` 层直接 `requests.get/post`，统一走 `WardenClient` / `TestConnector`。
3. **日志走 `zPrint`**：禁止裸 `print()`。
4. **断言走 `assertTool`**：禁止用正则解析 `str(response)`，禁止在用例里裸写 `assert`。
5. **异步用 `wait_until`**：禁止固定 `time.sleep()` 等待状态。
6. **每用例独立租户**：用 `tenant_factory()` 建唯一 `e2e-*` 租户，不复用共享账号、不删全局数据。
7. **CSRF Origin**：Cookie 会话的 POST/PUT/DELETE 必须带 `Origin`（`tools/request.py` 已统一处理），不要移除。
8. **allure 前脱敏**：请求/响应写入 allure 前必须脱敏（`tools/request.py` 已统一处理）。
9. **命名 snake_case**：测试函数以 `test_` 开头，文件命名 `test_<module>_<number>.py`。
10. **不伪造结果**：新增用例必须实际跑通；连不上环境就明确说明，不编造。