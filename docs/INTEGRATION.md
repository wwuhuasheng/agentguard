# Web 控制台与核心引擎整合

本分支把成员 B 的 Vue 控制台接入同学 A 的确定性策略核心，并补了一个演示 FastAPI 编排层。这不是生产后端：状态保存在进程内存，工具是 Mock 工具，登录用户是演示用户。

## 运行拓扑

```text
Vue Console -> FastAPI /api/* -------+
                                     +-> shared MCPGateway -> PolicyEngine -> Mock Tools
Core API -> FastAPI /core/api/* ------+          |
                                                +-> Audit / Recovery
```

## 后端

```powershell
python -m pip install -e ".[api]"
uvicorn backend.api.server:app --reload --port 8000
```

接口细节见 `docs/api.md`。两个 API 共用同一网关，但各自维护任务展示状态；核心任务的审批必须通过其任务决策接口，不能直接处理控制台的待审批请求。服务重启后状态清空；审批 60 秒过期；重复审批返回 409；危险请求在工具执行前阻断。

## 前端

```powershell
cd frontend
npm install
npm run dev
```

默认使用 Mock。联调真实演示 API 时在 `frontend/.env.local` 设置：

```env
VITE_DATA_MODE=live
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Live 失败不会自动退回 Mock，左侧用户名来自 `/api/me`。

## 四个演示场景

Live 模式当前以 `activity` 结构化活动任务为主：页面提交时间、地点、通知接收方、人数和内容，本地离线规划器生成日历、共享文件与通知三个事务步骤。四个预置场景保留在 Mock 回放和后端回归测试中，不作为真实 AgentArts 云端接入证据。

1. `normal`：低风险日程和小范围通知自动通过真实策略网关执行。
2. `approval`：40 人通知产生待审批请求；批准后执行一次，拒绝后不执行。
3. `block`：外部不可信请求要导出敏感字段并发给外部邮箱，策略在工具执行前返回 `BLOCK`。
4. `recovery`：批准共享文件更新后注入连续三次超时；相同获批请求只经网关最多重试两次，达到熔断阈值后取消后续通知并恢复操作前快照。

## 事件契约

HTTP 返回 snake_case 字段和带时区 ISO 8601 时间。事件按网关审计顺序返回；`POLICY_DECISION`、`APPROVAL_REQUIRED`、`APPROVAL_RESOLVED`、`TOOL_EXECUTED`、`TOOL_FAILED` 来自 `MCPGateway`。恢复流程追加服务层事件。所有事件 payload 会补齐 `tool_request`，前端可以直接展开工具参数、来源和风险证据。

## 已知边界

- 没有真实登录、多用户隔离、持久化数据库或横向扩展。
- 没有真实邮件、日程系统或共享盘；Mock 工具只修改内存对象。
- 未实现 SSE；前端每 4 秒轮询任务、审批和选中任务的事件。
- `modified_arguments` 暂不支持；前端仍传 null。
- 客户端提交的 `permissions` 只作为演示输入，不能当作真实授权来源。
