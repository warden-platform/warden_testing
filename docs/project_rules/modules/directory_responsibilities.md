# 目录职责

判断「这段代码该放哪」时先读本文件。

```text
warden_testing/
├── case/                       # 场景编排层
│   ├── conftest.py             # 全局 fixture
│   ├── platform/               # 健康检查、登录、租户生命周期
│   ├── tenant/                 # 项目、Principal、API Key
│   ├── connector/              # 测试 Connector 驱动的执行闭环与签名负向
│   └── security/               # 跨租户隔离
├── lib/
│   ├── control/client.py       # WardenClient：控制面 API 封装
│   ├── connector/simulator.py  # TestConnector：注册/心跳/同步/拉任务/回传
│   └── factory.py              # 租户、项目、Agent、Connector 工厂
├── tools/
│   ├── request.py              # 统一 HTTP，脱敏后写 allure；ApiResponse/ApiError
│   ├── assertTool.py           # assert_json / assert_error / assert_subset / assert_contains_item
│   ├── crypto.py               # Connector HMAC 签名
│   ├── waitTool.py             # wait_until 条件轮询
│   ├── ids.py                  # unique_slug / unique_name 唯一测试数据标识
│   └── printTool.py            # zPrint
├── config/environment.py       # 环境与凭据加载（含 warden 本地仓库回退）
├── scripts/                    # stack_up / stack_down / run_tests
└── docs/
    ├── TEST_PLAN.md            # 覆盖矩阵与后续路线
    └── project_rules/          # 本规则体系
```

## 归类速查

| 内容 | 该放哪 |
|------|--------|
| 新增一个接口的封装方法 | `lib/control/client.py` |
| 扩展测试 Connector 的行为 | `lib/connector/simulator.py` |
| 造租户/项目/Agent/Connector 数据 | `lib/factory.py` |
| 新增断言/轮询/签名能力 | `tools/` |
| 新增环境变量或凭据回退 | `config/environment.py` |
| 编排一条业务流 | `case/<domain>/` |