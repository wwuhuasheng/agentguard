export const statusLabels: Record<string, string> = {
  CANCELLED: '已取消',
  ANALYZING: '分析中',
  EXECUTING: '执行中',
  WAITING_APPROVAL: '等待审批',
  COMPLETED: '已完成',
  BLOCKED: '已阻断',
  REJECTED: '已拒绝',
  EXPIRED: '已超时取消',
  RECOVERING: '恢复中',
  RECOVERED: '已恢复',
  FAILED: '执行失败',
  PENDING: '待审批',
  APPROVED: '已批准',
  ALLOW: '自动放行',
  CONFIRM: '需要确认',
  BLOCK: '禁止执行',
  LOW: '低风险',
  MEDIUM: '中风险',
  HIGH: '高风险',
  CRITICAL: '严重风险',
}
export const trustLabels: Record<string, string> = {
  SYSTEM_TRUSTED: '系统可信指令',
  USER_CONFIRMED: '用户已确认',
  INTERNAL_REFERENCE: '内部参考资料',
  EXTERNAL_UNTRUSTED: '外部不可信文档',
  MODEL_GENERATED: '模型生成内容',
}
export const eventLabels: Record<string, string> = {
  TASK_CANCELLED: '回放会话已取消',
  POLICY_DECISION: '策略决策',
  APPROVAL_REQUIRED: '等待人工审批',
  APPROVAL_RESOLVED: '审批已处理',
  APPROVAL_EXPIRED: '审批超时取消',
  TOOL_EXECUTED: '工具执行成功',
  TOOL_FAILED: '工具执行失败',
  TASK_STARTED: '任务开始分析',
  TOOL_REQUESTED: '提出工具请求',
  INCIDENT_TRIGGERED: '触发异常熔断',
  ACTION_CANCELLED: '取消后续动作',
  SNAPSHOT_RESTORED: '文件快照已恢复',
  RECOVERY_COMPLETED: '状态恢复完成',
}
export const toolLabels: Record<string, string> = {
  calendar: '活动日历',
  send_notice: '通知服务',
  shared_file: '共享文件',
}
export function display(value: unknown): string {
  return value == null
    ? '未提供'
    : typeof value === 'object'
      ? JSON.stringify(value, null, 2)
      : String(value)
}
export function time(value: string): string {
  return new Date(value).toLocaleTimeString('zh-CN', { hour12: false })
}
export function dateTime(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
