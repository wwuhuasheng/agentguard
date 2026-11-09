// 前七个对象沿用 A 的 domain.py。Task / Approval / Incident 为待确认的前端适配对象。
export type Decision = 'ALLOW' | 'CONFIRM' | 'BLOCK'
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type TrustLevel =
  | 'SYSTEM_TRUSTED'
  | 'USER_CONFIRMED'
  | 'INTERNAL_REFERENCE'
  | 'EXTERNAL_UNTRUSTED'
  | 'MODEL_GENERATED'
export interface ToolRequest {
  task_id: string
  agent_id: string
  tool_name: string
  action: string
  arguments: Record<string, unknown>
  source_trust: TrustLevel
  request_id: string
  created_at: string
}
export interface RiskEvidence {
  code: string
  message: string
  level: RiskLevel
  field: string | null
  observed: unknown
  expected: unknown
}
export interface PolicyDecision {
  request_id: string
  decision: Decision
  risk_level: RiskLevel
  reasons: RiskEvidence[]
  policy_id: string | null
}
export interface ExecutionResult {
  request_id: string
  status: 'SUCCEEDED' | 'PENDING_CONFIRMATION' | 'BLOCKED' | 'REJECTED' | 'FAILED'
  decision: Decision
  output?: Record<string, unknown> | null
  error?: string | null
}
export interface AuditEvent {
  event_id: string
  event_type: string
  request_id: string
  task_id: string
  created_at: string
  payload: Record<string, unknown> & {
    tool_request?: ToolRequest
    decision?: Decision
    risk_level?: RiskLevel
    reasons?: RiskEvidence[]
  }
}
export type Scenario = 'normal' | 'approval' | 'block' | 'recovery'
export type TaskStatus =
  | 'ANALYZING'
  | 'EXECUTING'
  | 'WAITING_APPROVAL'
  | 'COMPLETED'
  | 'BLOCKED'
  | 'REJECTED'
  | 'EXPIRED'
  | 'RECOVERING'
  | 'RECOVERED'
  | 'FAILED'
  | 'CANCELLED'
export interface FileMeta {
  name: string
  size: number
  type: string
}
export interface Task {
  task_id: string
  title: string
  description: string
  scenario: Scenario
  status: TaskStatus
  created_at: string
  updated_at: string
  files: FileMeta[]
  permissions: string[]
  events: AuditEvent[]
  replay: boolean
}
export interface Approval {
  approval_id: string
  request_id: string
  task_id: string
  summary: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED'
  expires_at: string
  resolved_at?: string
  tool_request: ToolRequest
  reasons: RiskEvidence[]
}
export interface Incident {
  incident_id: string
  task_id: string
  reason: string
  status: 'RECOVERING' | 'RECOVERED'
  created_at: string
  before: string
  damaged: string
  after: string | null
  cancelled_count: number
}
export interface EvalSample {
  id: string
  category: string
  expected: Decision | 'RECOVERED'
  actual: Decision | 'RECOVERED'
  success: boolean
  baselinePrompt: boolean
  baselineKeyword: boolean
}

export interface CurrentUser {
  user_id: string
  username: string
  display_name?: string | null
  avatar_url?: string | null
  role?: string | null
}
