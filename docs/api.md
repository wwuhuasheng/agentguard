# AgentGuard Demo HTTP API

后端是演示用内存服务，每次进程重启会清空任务、审批和事件。所有策略决策都通过 `PolicyEngine` 和 `MCPGateway` 执行；演示工具只操作内存中的日程、通知和共享文件。

## 启动

```powershell
python -m pip install -e ".[api]"
uvicorn backend.api.server:app --reload --port 8000
```

CORS 默认允许 Vite 开发地址 `127.0.0.1:5173` 和静态演示地址 `127.0.0.1:4173`。

## 通用约定

- JSON 字段使用 snake_case。
- 时间使用带时区的 ISO 8601。
- `Approval.approval_id` 等于网关的 `request_id`。
- 策略、审批和工具事件通过 `event_id` 去重；前端按返回顺序展示。
- 业务错误返回 404 / 409 / 422；参数校验错误由 FastAPI 返回 422。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 返回 `{ "status": "ok" }`。 |
| GET | `/api/me` | 返回演示用户 `example.operator`。真实登录和会话鉴权后续接入。 |
| GET | `/api/tasks` | 按创建时间倒序返回任务，每个任务带完整事件。 |
| POST | `/api/activities/preview` | 根据本次活动参数只读预估三步工具操作的授权范围与决策，不创建任务。 |
| POST | `/api/tasks` | 创建任务并立即执行对应场景，返回 201 和 Task。 |
| GET | `/api/tasks/{task_id}` | 返回单个 Task。 |
| GET | `/api/tasks/{task_id}/events` | 返回 AuditEvent 数组。 |
| GET | `/api/approvals` | 返回审批，按创建时间倒序。 |
| POST | `/api/approvals/{approval_id}/decision` | 批准或拒绝一个待确认请求。 |
| GET | `/api/incidents` | 返回熔断恢复事件。 |
| GET | `/api/incidents/{incident_id}` | 返回单个 Incident。 |

## 提交前权限预览

请求体包含 `title`、`description` 和与 `activity` 任务相同的结构化 `activity`。返回 `mode: PREVIEW_ONLY` 以及日历创建、共享文件更新、通知发送三张卡片，每张卡片给出操作范围、预计的 `ALLOW / CONFIRM / BLOCK` 和规则理由。预览不会调用 AgentArts、创建任务、签发真实护照、等待审批或执行工具；提交时仍重新评估，因此预览不是最终授权。

## 创建任务

```json
POST /api/tasks
{
  "title": "活动安排",
  "description": "创建日程并通知参与者",
  "scenario": "normal",
  "files": [],
  "permissions": ["calendar.create", "send_notice.send"]
}
```

`scenario` 支持：

- `normal`：创建日程并发送小范围通知，预期自动完成。
- `approval`：40 人通知触发 `CONFIRM`，等待 `/decision`。
- `block`：外部不可信请求发送敏感字段到外部邮箱，预期 `BLOCK`。
- `recovery`：共享文件更新先确认；批准后连续失败三次，熔断并恢复快照。
- `activity`：使用用户提交的时间、地点、通知对象和人数生成三步事务；共享文件更新须确认，超过 30 人通知还会再次确认。返回 `agent_plan` 与 `passport_id` 供前端展示。

Live 活动任务示例（时间必须带时区且晚于当前时间）：

```json
{
  "title": "周末读书会",
  "description": "请提前十分钟到场",
  "scenario": "activity",
  "activity": {
    "starts_at": "2026-11-15T10:00:00+08:00",
    "location": "社区图书馆",
    "recipient": "readers@example.org",
    "recipient_count": 12
  }
}
```

`files` 与 `permissions` 是演示元数据；运行时不会根据 `files` 读取正文，也不会把客户端传来的 `permissions` 提升为真实授权。

`activity` 任务可额外提交一个 `reference`：`{"name":"活动策划.txt","content":"演示用脱敏资料"}`。仅接受 UTF-8 TXT/CSV、1–32768 字节；CSV 最多 20 列、500 行，列宽须一致。服务端只在请求期间检查正文，不把正文或 CSV 行值保存到任务、事件或规划器输入。响应中的 `source_summary` 仅含文件名、大小、哈希、来源等级、行数、白名单字段及风险标记，并追加 `SOURCE_INSPECTED` 事件。`files` 元数据不能替代 `reference` 正文。

参考资料始终标记为 `EXTERNAL_UNTRUSTED`；其中的收件地址、操作指令和授权声明不会覆盖用户填写的结构化参数。敏感列名会被标记并排除，未知列也不进入可用字段。危险指令标记是启发式提示，**不能**作为准确检出或无风险证明；目前也不会从资料中自动生成计划。文件名和列名仍可能含个人信息，演示请只用自制/脱敏资料。

## 审批决策

```json
POST /api/approvals/{approval_id}/decision
{
  "decision": "APPROVE",
  "comment": "",
  "modified_arguments": null
}
```

`decision` 只接受 `APPROVE` / `REJECT`。当前演示服务不支持修改参数；`modified_arguments` 非 null 返回 422。审批 60 秒过期；重复决策返回 409。

## Task

```json
{
  "task_id": "uuid",
  "title": "活动安排",
  "description": "创建日程并通知参与者",
  "scenario": "normal",
  "status": "COMPLETED",
  "created_at": "2026-11-07T15:00:00+08:00",
  "updated_at": "2026-11-07T15:00:00+08:00",
  "files": [],
  "permissions": [],
  "events": [],
  "replay": false
}
```

Task 状态包含 `EXECUTING`、`WAITING_APPROVAL`、`COMPLETED`、`BLOCKED`、`REJECTED`、`EXPIRED`、`RECOVERING`、`RECOVERED`、`FAILED`。
`activity` 任务还包含 `agent_plan`（本地规划来源、三角色证据、步骤）和 `passport_id`；提交参考资料时还包含 `source_summary`。这证明的是本地离线链路，不等于已在 AgentArts 上部署。

## AuditEvent

```json
{
  "event_id": "uuid",
  "event_type": "POLICY_DECISION",
  "request_id": "uuid",
  "task_id": "uuid",
  "created_at": "2026-11-07T15:00:00+08:00",
  "payload": {}
}
```

事件类型覆盖网关的 `POLICY_DECISION`、`APPROVAL_REQUIRED`、`APPROVAL_RESOLVED`、`TOOL_EXECUTED`、`TOOL_FAILED`，以及服务层的 `SOURCE_INSPECTED`、`APPROVAL_EXPIRED`、`INCIDENT_TRIGGERED`、`ACTION_CANCELLED`、`SNAPSHOT_RESTORED`、`RECOVERY_COMPLETED`。

前端风险证据需要 `payload.tool_request`。服务层序列化时会把请求上下文补齐；审批相关事件还会带 `approval_id` 和 `expires_at`。
