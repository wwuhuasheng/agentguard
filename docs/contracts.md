# 公共事件协议 v0.2

## ToolRequest

| 字段 | 含义 |
| --- | --- |
| `request_id` | 单次工具请求 ID |
| `task_id` | 用户任务 ID |
| `agent_id` | 发起请求的 Agent |
| `tool_name` | MCP 工具名 |
| `action` | 工具内具体动作 |
| `arguments` | 结构化参数 |
| `source_trust` | 触发该请求的信息来源 |

## TraceEvent

当前事件类型：

- `SOURCE_INSPECTED`（活动参考资料的隔离检查摘要；不含正文或 CSV 行值）
- `POLICY_DECISION`
- `APPROVAL_REQUIRED`
- `APPROVAL_RESOLVED`
- `APPROVAL_EXPIRED`
- `APPROVAL_INVALIDATED`
- `TOOL_EXECUTED`
- `TOOL_FAILED`
- `ROLLBACK_COMPLETED`
- `ROLLBACK_SKIPPED`
- `CIRCUIT_OPENED`
- `CIRCUIT_REJECTED`

`APPROVAL_REQUIRED` 必须包含请求摘要和失效时间。用户批准只对摘要完全一致的工具请求生效，参数变化后必须重新审批。

## Task Passport

完整任务由后端签发限时任务护照。护照中的每项授权同时绑定 `task_id`、Agent、工具、动作、参数及来源信任级别，并且只能消费一次。任务执行阶段出现的新内容不能修改护照；超出护照的请求统一产生 `TASK_PASSPORT_VIOLATION` 决策证据，重复执行产生`TASK_PASSPORT_REPLAY`证据。

前端与评测模块应以该事件结构开发 Mock 数据，避免后续联调时重新定义字段。

## 后续 API

```text
POST /api/tasks
GET  /api/tasks/{id}
GET  /api/tasks/{id}/events
POST /api/tasks/{id}/decision
POST /api/tasks/{id}/cancel
POST /api/approvals/{id}/decision
GET  /api/incidents/{id}
POST /api/evaluations/run
GET  /api/evaluations/{id}
```

除评测接口外均已由核心后端实现。队友开发前端时以 `POST /api/tasks` 返回的 `status`、`pending_request_id`、`plan_summary`、`results` 为准，不应在前端自行推断策略结果。

## 团队并行边界

- 前端队员：消费任务、审批、事件和熔断接口，不修改策略判定；
- 评测队员：基于公共事件协议统计拦截率、误报率和恢复成功率；
- 核心后端：维护 AgentArts 适配器、状态机、策略网关与恢复语义。

真实 AgentArts 的项目 ID、工作流 API 和鉴权配置尚未写入仓库，等待平台资源开通后通过环境变量接入。
