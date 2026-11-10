import type { Task, AuditEvent, Approval, Incident, FileMeta, CurrentUser, ActivityInput, ActivityPermissionPreview } from '../types'
export const configuredMode = import.meta.env.VITE_DATA_MODE === 'live' ? 'live' : 'mock'
const base = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
    signal: AbortSignal.timeout(10000),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? `：${body.detail}` : ''
    throw new Error(`接口返回 ${response.status}：${path}${detail}`)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
// Live API 契约。失败直接报错，不自动切换 Mock。
export const liveApi = {
  currentUser: () => request<CurrentUser>('/api/me'),
  async tasks() {
    const rows = await request<Task[]>('/api/tasks')
    if (!Array.isArray(rows)) throw new Error('任务接口应返回数组，请对齐 docs/INTEGRATION.md')
    return rows
  },
  create: (input: {
    title: string
    description: string
    scenario: string
    files: FileMeta[]
    permissions: string[]
    activity?: ActivityInput
  }) => request<Task>('/api/tasks', { method: 'POST', body: JSON.stringify(input) }),
  previewActivity: (input: { title: string; description: string; activity: ActivityInput }) =>
    request<ActivityPermissionPreview>('/api/activities/preview', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  task: (id: string) => request<Task>(`/api/tasks/${encodeURIComponent(id)}`),
  events: (id: string) => request<AuditEvent[]>(`/api/tasks/${encodeURIComponent(id)}/events`),
  approvals: () => request<Approval[]>('/api/approvals'),
  decide: (id: string, approved: boolean) =>
    request<Approval>(`/api/approvals/${encodeURIComponent(id)}/decision`, {
      method: 'POST',
      body: JSON.stringify({
        decision: approved ? 'APPROVE' : 'REJECT',
        comment: '',
        modified_arguments: null,
      }),
    }),
  incident: (id: string) => request<Incident>(`/api/incidents/${encodeURIComponent(id)}`),
}
