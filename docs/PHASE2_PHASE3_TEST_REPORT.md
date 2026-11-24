# Phase 2 / Phase 3 测试报告摘要

- 报告日期：2026-11-24
- 执行环境：GitHub Actions `warden-e2e`（ubuntu-latest，postgres:16 service，自建 warden 控制面 `http://localhost:8080`）
- 触发方式：`push main`（gitee 快照同步后）或 `workflow_dispatch`
- 测试框架：pytest + requests + allure，测试 Connector 复刻 HMAC 协议
- CI 执行命令（[e2e.yml](file:///Users/huanghaitao/Documents/warden_testing/.github/workflows/e2e.yml#L129-L136)）：

```bash
pytest -m "smoke or connector or security or approval" \
  --alluredir=allure-results \
  --junitxml=artifacts/junit.xml
```

- 提交前本地预检命令（与 CI 同 marker 集合）：

```bash
.venv/bin/python -m pytest \
  case/tenant/test_policy_rules_001.py \
  case/connector/test_policy_enforcement_001.py \
  case/connector/test_connector_dispatch_001.py \
  case/connector/test_approval_decision_001.py \
  case/tenant/test_tenant_quota_001.py \
  --alluredir=allure-results --clean-alluredir
```

## 1. 结果总览

| 指标 | 结果 |
|---|---|
| Phase 2/3 新增用例 | 14 |
| GitHub Actions `warden-e2e`（[run 45338044329](https://github.com/warden-platform/warden_testing/actions/runs/45338044329)） | **success** |
| CI 核心套件 | **45 passed，0 failed，0 error，0 skipped**；JUnit 用例耗时 26.6s，job 耗时 1m48s |
| 本地预检（与 CI 同 marker） | 14 passed，0 failed，7.36s |
| 全量用例数 | 67（核心 45 + 集成 17 + UI 5） |
| 快照提交 | gitee `8aab1e3` → GitHub `c18b7ca` |

结论：新增 14 条用例随核心套件在 GitHub Actions 中全部通过，CI 结果与本地预检一致，无回归。

## 2. CI 覆盖与产物

| 项目 | 内容 |
|---|---|
| Workflow | `warden-e2e`（`.github/workflows/e2e.yml`） |
| 触发 | push `main` / 手动 `workflow_dispatch` |
| 环境 | ubuntu-latest + postgres:16-alpine + Go 构建的 warden-control |
| 用例范围 | `-m "smoke or connector or security or approval"`，新增 14 条全部命中 |
| 本次运行 | [45338044329](https://github.com/warden-platform/warden_testing/actions/runs/45338044329)，2026-11-24 06:06:59Z 启动，1m48s 完成 |
| 产物 | `warden-e2e-results`：`allure-results/` + `artifacts/junit.xml` |
| 查看方式 | Actions 运行页 → Artifacts 下载；失败时先看 JUnit 再用 allure 打开明细 |

> 注意：`scripts/sync-github.sh` 同步的是 **已提交的 HEAD 树**。新增用例在提交并 push 到 gitee 之前不会进入 GitHub 快照，也就不会出现在 CI 中。

## 3. 分组结果

### Phase 2：策略矩阵、并发与审批边界（8 条）

| 用例 | 耗时 | 验证结论 |
|---|---|---|
| `test_policy_rule_crud` | 0.87s | 规则创建/列表/更新/复制为停用副本/删除后 404 全部符合契约 |
| `test_policy_rule_validation_negative` | 0.43s | 名称、决策、环境、优先级、资源类型、动作、项目 7 类非法输入均返回 400 `INVALID_POLICY_RULE` |
| `test_policy_rule_simulation` | 0.47s | 矩阵可收紧 Rego `ALLOW`；Rego `DENY` 为不可放宽下限；非法 `base_decision` 返回 400 |
| `test_policy_deny_blocks_readonly_execution` | 0.53s | 只读动作被 DENY 后返回 403，执行落 `FAILED/POLICY_DENIED`，任务不下发，审计有 `execution.failed` |
| `test_policy_allow_skips_approval_for_change` | 0.50s | 测试环境变更默认 `WAITING_APPROVAL`；矩阵 ALLOW 后直接 `QUEUED` 且不产生审批单，执行成功 |
| `test_policy_require_approval_for_readonly` | 0.47s | 只读动作被收紧为 `WAITING_APPROVAL`，审批后入队并执行成功 |
| `test_reject_marks_execution_failed` | 0.64s | 拒绝后执行 `FAILED/APPROVAL_REJECTED`，不下发；重复拒绝 409 `ALREADY_PROCESSED` |
| `test_duplicate_approve_is_rejected` | 0.48s | 重复审批 409；首次审批后执行进入 `QUEUED`，可正常取消 |

### Phase 2：并发配额（1 条）

| 用例 | 耗时 | 验证结论 |
|---|---|---|
| `test_concurrency_quota_limits_in_flight` | 0.47s | 平台管理员可将阈值调整为 1；第二条在途执行返回 429 `CONCURRENCY_LIMIT_REACHED`；取消后额度释放；非法阈值 400、非平台身份 403 |

### Phase 2：审批越权（1 条）

| 用例 | 耗时 | 验证结论 |
|---|---|---|
| `test_agent_cannot_approve_request` | 0.50s | 无 `warden:approve` 的 Agent Key 审批返回 403 `INSUFFICIENT_SCOPE`，请求保持 `PENDING` |

### Phase 3：分发租约与结果回传（4 条）

| 用例 | 耗时 | 验证结论 |
|---|---|---|
| `test_wrong_dispatch_token_keeps_execution_dispatched` | 0.47s | 错误 `dispatchToken` 返回 409 `EXECUTION_STATE_CHANGED`，执行保持 `DISPATCHED`，正确 token 仍可完成 |
| `test_unknown_result_marks_execution_unknown` | 0.51s | `UNKNOWN` 落 `UNKNOWN/UNKNOWN_RESULT` 且带错误说明；终态不再重发任务 |
| `test_duplicate_terminal_result_is_idempotent` | 0.49s | 同一终态结果重复回传均返回 `accepted`，结果保留首次值 |
| `test_other_connector_cannot_submit_result` | 0.52s | 其他 Connector 冒领结果返回 409 `INVALID_EXECUTION_STATE`，执行不受影响 |

## 4. 关键行为结论

1. **决策优先级正确**：Rego `DENY` > 矩阵规则 > Rego 基础决策；矩阵只能在非生产环境把 `REQUIRE_APPROVAL` 放宽为 `ALLOW`，不能放宽 Rego `DENY`。
2. **拒绝语义可审计**：策略拒绝与审批拒绝分别落 `POLICY_DENIED`、`APPROVAL_REJECTED`，均不产生 Connector 任务，审计事件完整。
3. **分发租约防护有效**：token 校验、通道绑定、终态幂等均符合预期，篡改/冒领不会改变执行状态。
4. **并发保护可用**：配额按租户在途执行数生效，取消后即时释放。

## 5. 限制与后续

- 未覆盖：审批过期、列表分页、Scope 细分、Connector 租约真正过期（需等待窗口）、TaskEnvelope 在 Python 侧本地验签。
- 集成 17 条与 UI 5 条本轮未执行，需对应 mock / 前端 dev server 配置；新增用例已随 `warden-e2e` 的 core marker 集合进入 CI。
- 报告明细可在 Actions 产物 `warden-e2e-results` 中用 allure 打开；本地亦可用 `make report` 查看。
