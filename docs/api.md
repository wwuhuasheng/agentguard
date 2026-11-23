# AgentGuard Demo HTTP API

后端是演示用内存服务，每次进程重启会清空任务、审批和事件。所有策略决策都通过 `PolicyEngine` 和 `MCPGateway` 执行；演示工具只操作内存中的日程、通知和共享文件。

## 启动

```powershell
python -m pip install -e ".[api]"
uvicorn backend.api.server:app --reload --port 8000
```

CORS 默认允许 Vite 开发地址 `127.0.0.1:5173` 和静态演示地址 `127.0.0.1:4173`。

## 多访客模拟演示

```bash
AGENTGUARD_DEMO_ISOLATION=1 uvicorn backend.api.server:app --port 8000
```

此模式由服务端生成 `HttpOnly`、`SameSite=Lax` 的随机 Cookie；浏览器会话各有独立任务、审批、审计和模拟工具空间。`/core/*` 会关闭，避免通过底层接口绕过访客范围。会话闲置一小时后失效，最多同时保留 64 个；服务重启会清空全部状态。健康检查和 CORS 预检不占会话名额。跨域写请求的 `Origin` 必须匹配服务自身或允许列表；增加前端来源时设置 `AGENTGUARD_ALLOWED_ORIGINS=https://你的演示域名`。HTTPS 部署还应设置 `AGENTGUARD_SESSION_SECURE_COOKIE=1`。

本地联调时请让前后端统一使用 `127.0.0.1`，例如前端 `npm run dev -- --host 127.0.0.1`、`VITE_API_BASE_URL=http://127.0.0.1:8000`。前端 Live 请求已携带 Cookie。正式在线演示优先同域反向代理，且当前实现只适用于单进程、内存、模拟工具；Cookie 代表访客会话，不验证个人真实身份。接入真实工具或云端付费调用前，还需要正式认证、持久化、限流和服务端成本约束。

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
| GET | `/api/me` | 默认返回演示用户 `example.operator`；访客隔离模式返回该会话的匿名演示用户。真实登录后续接入。 |
| GET | `/api/tasks` | 按创建时间倒序返回任务，每个任务带完整事件。 |
| POST | `/api/activities/preview` | 根据本次活动参数只读预估所选工具操作的授权范围与决策，不创建任务。 |
| POST | `/api/activities/reference-preview` | 对一份脱敏 TXT/CSV 做只读资料核对建议，不创建任务。 |
| POST | `/api/tasks` | 创建任务并立即执行对应场景，返回 201 和 Task。 |
| GET | `/api/tasks/{task_id}` | 返回单个 Task。 |
| GET | `/api/tasks/{task_id}/events` | 返回 AuditEvent 数组。 |
| GET | `/api/tasks/{task_id}/evidence` | 返回可离线校验的脱敏任务证据包；遵循访客会话范围。 |
| GET | `/api/approvals` | 返回审批，按创建时间倒序。 |
| POST | `/api/approvals/{approval_id}/decision` | 批准或拒绝一个待确认请求。 |
| GET | `/api/incidents` | 返回熔断恢复事件。 |
| GET | `/api/incidents/{incident_id}` | 返回单个 Incident。 |

## 提交前权限预览

请求体包含 `title`、`description` 和与 `activity` 任务相同的结构化 `activity`。`activity.update_shared_file` 为可选布尔值，默认 `true`；设为 `false` 后仅预览日历与通知两步，且实际任务护照不会包含共享文件更新。返回 `mode: PREVIEW_ONLY` 及所选操作的范围、预计的 `ALLOW / CONFIRM / BLOCK` 和规则理由。选择更新文件时，额外返回 `least_privilege_option`：在相同用户参数下，计算取消文件更新前后的工具数、待确认数和阻断数，供用户决定是否收窄权限；服务端不会自动改变任务。预览不会调用 AgentArts、创建任务、签发真实护照、等待审批或执行工具；提交时仍重新评估，因此预览不是最终授权。

## 创建任务

提交前如已选择资料，可调用 `POST /api/activities/reference-preview`，请求体为 `{"reference":{"name":"虚构名单.csv","content":"role,availability\n志愿者,上午\n"},"recipient_count":12}`。响应为 `PREVIEW_ONLY`、`source_summary`、`checks`、可为空的 `schedule_proposal` 和 `activity_draft`。CSV 会核对数据行数与拟通知人数是否一致，并提醒敏感列；含 `availability`、`可参与时段`、`shift` 或 `班次` 列时，仅识别标准的上午、下午、全天/均可等值，输出匿名行号与建议班次；无法识别的值留待人工安排，不返回姓名、电话或原始单元格。TXT 可从独立行的 `活动时间：YYYY-MM-DDTHH:MM+08:00`（或 +09:00、+00:00）与 `活动地点：...` 提取待核对草案；只有用户在页面明确点击采纳，才填入时间和地点。TXT 不推断人数，疑似操作指令仅提示人工核对。行数可能包含重复、未报名或其他对象，**不能**当作授权人数；草案不自动发通知、不创建任务、不保存资料正文。改变资料或人数后应重新预览。

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
- `activity`：使用用户提交的时间、地点、通知对象和人数生成两/三步事务；共享文件更新可由用户取消，若保留则须确认，超过 30 人通知还会再次确认。返回 `agent_plan` 与 `passport_id` 供前端展示。

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

审批响应的 `impact_preview` 由后端在请求暂停时生成。共享文件更新会给出目标路径、当前/拟写入内容的 SHA-256、行数和最多 4000 字的差异；群发通知会给出接收地址、人数和内容摘要。它描述的是**模拟工具**将产生的影响，不等于真实系统已发送或写入。批准文件更新时，服务端在同一把执行锁内重新核对目标文件摘要；若目标已变化，返回 `status: INVALIDATED`、`invalidation_code: TARGET_CHANGED`，当前待审批操作不会执行，需重新创建任务。此前已完成的步骤可能保留，任务轨迹会有 `PARTIAL_EFFECT_RETAINED` 提示人工核对；较新的目标文件不会被整份任务快照覆盖。多进程或真实外部系统仍需数据库事务/条件写入，不能把此内存锁当作生产并发控制。

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
当目标文件在审批期间变化，任务会转为 `CANCELLED`，审批为 `INVALIDATED`；前序步骤的去留以轨迹为准。
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

## 脱敏证据包

Live 模式轨迹页的“导出脱敏证据包”调用服务端 `/api/tasks/{task_id}/evidence`。包内含任务状态、规划来源、当前策略文件 SHA-256、按顺序编号的事件及安全事实、事件链根摘要和验证结果；不包含任务标题、通知正文、收件地址、资料文件名、工具完整参数或执行输出。规则检查包括“执行必须有先前允许/确认的策略决定”“确认操作必须有同请求指纹的批准”“同一请求不能成功执行两次”。导出时任务仍在等待审批也可以，后续审批会生成**新的**链根摘要。

```bash
python scripts/verify_evidence.py agentguard-evidence-任务ID.json
python scripts/verify_evidence.py agentguard-evidence-任务ID.json --expect-root 另行保存的64位根摘要
```

首次导出时应从 `manifest.event_root_sha256` 另行记录根摘要，之后用 `--expect-root` 比对。仅验证文件内部结构和已保存的根摘要；任何人都能重算一个新包，所以**没有独立保存的根摘要或可信签名时，不能证明包来自原服务器**。本功能面向模拟工具的可复现演示，不是法律意义上的取证或真实业务审计。Mock 模式仍导出本地回放 JSON，不能使用这个校验器。
