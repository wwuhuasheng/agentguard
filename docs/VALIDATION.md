# 整合验证记录

验证日期：2026-11-09。

## 自动化验证

- 后端：`python -m unittest discover -s tests -v` 通过，共 40 项（含 Live 活动参数、多轮审批和越权域名集成测试）。
- 覆盖：低风险放行、群发确认、外部指令阻断、删除拒绝、Windows 路径前缀、批准 / 拒绝、60 秒过期、重复决策冲突、普通任务、恢复流程和非法场景。
- 恢复流程验证三次失败、`INCIDENT_TRIGGERED`、`ACTION_CANCELLED`、`SNAPSHOT_RESTORED`、`RECOVERY_COMPLETED`，并断言文件恢复为原内容。
- 前端：`npm test` 通过，共 25 项；`npm run build` 通过（包含 Vue 类型检查）。在本机 Node 26 下运行测试需设置 `NODE_OPTIONS=--localstorage-file=/private/tmp/agentguard-review-localstorage`。
- 语法：`python -m compileall backend tests` 通过。

## 运行时边界

- `uvicorn` 已在本机完成实际启动验证，监听 `127.0.0.1:8000`。
- 实际调用验证：`/api/health` 返回 ok，`/api/me` 返回 `example.operator`；normal 任务完成，block 任务阻断，approval 批准后完成，recovery 批准后触发熔断并恢复。
- 恢复运行时检查产生 1 条 `RECOVERED` Incident；四个任务最终状态分别为 `COMPLETED`、`BLOCKED`、`COMPLETED`、`RECOVERED`。
- 前端生产构建和 Vitest 已在本次集成中实际通过。
- 统一启动入口同时提供 `/api/*` 控制台接口和 `/core/api/*` 核心事务接口，共用同一个策略网关；核心接口不能绕过演示服务直接批准演示任务。
- Live 活动任务的页面输入会进入规划、任务护照、策略、审批和 Trace；本次增加了 12 人单次审批完成、40 人两次审批及拒绝回滚的集成测试。
- 已用本机 Live 页面实际走通“填写周末读书会参数 → Trace 等待审批 → 批准共享文件 → 任务完成、通知工具执行”；审批预览保留所选 `UTC+8` 时间，不再把 10:00 显示成 02:00 UTC。
- API 状态在内存中保存，进程重启后清空；没有持久化数据库。
- 工具执行只修改 `MockWorkspace` 内存对象，不发送真实邮件或修改真实文件。

## 提交前人工复核

1. 启动 API 后确认 `/api/health` 返回 `ok`。
2. 在 Live 模式提交自定义活动任务，分别验证 12 人与 40 人通知；四个预置场景在 Mock 模式回放。
3. 审批批准和拒绝各验证一次；等待过期后再点击批准，确认不执行。
4. 检查用户名来自 `/api/me`，界面没有版本号。
5. 在常用浏览器宽度下检查控制台、轨迹、审批、恢复和评测页面。
