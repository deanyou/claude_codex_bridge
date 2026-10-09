# Round 02 完成总结

## 工作树差异（pi 在 vflow 关闭后继续工作产生的）
- lib/cc_bridge_daemon/app_runtime/bootstrap.py: +67 行（_inject_durable_dispatcher_into_pi_adapter）
- lib/provider_backends/pi/execution.py: +12 行（PiExecutionAdapter(dispatcher=, binding_id=)）
- lib/provider_backends/pi/pane_execution.py: +139 行
  - PiPaneExecutionAdapter.__init__ 接收 dispatcher/binding_id
  - start() 注入 state["dispatcher"] 与 state["binding_id"]
  - _wire_dispatcher_report_result helper（捕获 RESULT_DELIVERED 之外的 outcome）
  - 异常分支写 last_dispatch_outcome='exception' + recovery_required=True
  - 未知返回（非 DispatchResult）fail-closed
  - _reply_delivery_result 改为只记 transport sent 标记（不调 report_result）
- lib/durable_bridge/dispatcher.py: line 443 修（P1 #2：完整 payload 重复报告用 resolved_hash 而非入参）
- test/test_provider_pi_completion_wiring.py: 31 passed（替换原 17）
- test/test_durable_bridge_dispatcher.py: 16 passed（含 P1 回归 2）

## 我后续补的（planner 自补）
- test/test_daemon_durable_dispatcher_integration.py: 新增 7 个测试
  - PiExecutionAdapter / PiPaneExecutionAdapter plumbing 验证（4）
  - 真实 DurableDispatcher + MailboxKernelService + ResultStore 端到端 round-trip（2）
  - state 注入可观察性（1）

## 测试结果
```
pytest test/test_durable_bridge_*.py test/test_pi_pane_execution.py \
       test/test_provider_pi_completion_wiring.py \
       test/test_daemon_durable_dispatcher_integration.py -q
233 passed in 48.84s
```

## 关键不变量（已守护）
1. ✅ daemon 启动时 DurableDispatcher 单例创建（try/except 降级保留原 adapter）
2. ✅ PiExecutionAdapter(dispatcher=real) 把 dispatcher 沿 start() 注入 state
3. ✅ _settled_result 调 dispatcher.report_result 走 ResultStore 落盘 + ledger phase 推进
4. ✅ helper 处理所有非 RESULT_DELIVERED 结局（RESULT_CONFLICT / LEDGER_CONFLICT / ALREADY_TERMINAL / 异常 / 未知返回）
5. ✅ _reply_delivery_result 不调 report_result（避免"已发送"误作对端 ACK）
6. ✅ 完整 payload 重复报告不再误判冲突（resolved_hash 修）

## 不在 round 02 范围（明确留给后续）
- ❌ cc_bridge_daemon JobDispatcher.submit() 路径替换（计划 round 03）
- ❌ 多进程活体故障注入（计划 round 03 fault injection 子项）
