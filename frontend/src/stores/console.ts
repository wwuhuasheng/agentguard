import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  Task,
  Scenario,
  AuditEvent,
  Approval,
  Incident,
  ToolRequest,
  FileMeta,
  CurrentUser,
  ActivityInput,
  ActivityReference,
} from '../types'
import { blockReasons, event, permissions, reason, toolRequest, uid } from '../mock/scenarios'
import { configuredMode, liveApi } from '../api/client'
interface Runtime {
  step: number
  next: number
  paused: boolean
  speed: number
  waiting: boolean
  request: ToolRequest | null
}
const STORAGE = 'agentguard-console-v1'
export const useConsoleStore = defineStore('console', () => {
  const mode = ref<'mock' | 'live'>(configuredMode),
    tasks = ref<Task[]>([]),
    approvals = ref<Approval[]>([]),
    incidents = ref<Incident[]>([])
  const selectedId = ref(''),
    runtimes = ref<Record<string, Runtime>>({}),
    message = ref(''),
    busy = ref(false),
    now = ref(Date.now()),
    connected = ref(false)
  const currentUser = ref<CurrentUser | null>(null)
  const current = computed(() => tasks.value.find((t) => t.task_id === selectedId.value))
  const pending = computed(() => approvals.value.filter((a) => a.status === 'PENDING'))
  const currentRun = computed(() => runtimes.value[selectedId.value])
  let toastTimer: ReturnType<typeof setTimeout> | undefined
  function notify(text: string) {
    message.value = text
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => (message.value = ''), 5000)
  }
  const mockUser: CurrentUser = {
    user_id: 'demo-user-001',
    username: 'demo-user',
    display_name: '演示用户',
    avatar_url: null,
    role: 'operator',
  }
  async function loadCurrentUser() {
    if (mode.value === 'mock') {
      currentUser.value = { ...mockUser }
      return currentUser.value
    }
    try {
      const user = await liveApi.currentUser()
      if (!user || typeof user.username !== 'string' || !user.username.trim())
        throw new Error('用户接口缺少 username')
      currentUser.value = user
      return user
    } catch (e) {
      currentUser.value = null
      notify(`用户信息尚未加载：${e instanceof Error ? e.message : '网络异常'}`)
      return null
    }
  }
  function save() {
    if (mode.value !== 'mock') return
    try {
      localStorage.setItem(
        STORAGE,
        JSON.stringify({
          version: 1,
          tasks: tasks.value,
          approvals: approvals.value,
          incidents: incidents.value,
          selectedId: selectedId.value,
          runtimes: runtimes.value,
        })
      )
    } catch {
      /* 浏览器禁用存储时仍保留当前会话 */
    }
  }
  function append(task: Task, evt: AuditEvent) {
    if (!task.events.some((e) => e.event_id === evt.event_id)) task.events.push(evt)
    task.updated_at = evt.created_at
  }
  function taskBase(scenario: Scenario, title: string, replay = false): Task {
    const at = new Date().toISOString()
    return {
      task_id: uid(),
      title,
      description: '安排社区公益活动，创建日程并向已授权参与者发送通知。',
      scenario,
      status: 'ANALYZING',
      created_at: at,
      updated_at: at,
      files: [],
      permissions: [...permissions],
      events: [],
      replay,
    }
  }
  function policy(t: Task, req: ToolRequest, decision: 'ALLOW' | 'CONFIRM' | 'BLOCK') {
    append(
      t,
      event(
        t.task_id,
        'POLICY_DECISION',
        {
          tool_request: req,
          request_id: req.request_id,
          decision,
          risk_level: decision === 'BLOCK' ? 'CRITICAL' : decision === 'CONFIRM' ? 'HIGH' : 'LOW',
          policy_id:
            req.tool_name === 'calendar'
              ? 'activity-calendar-v1'
              : req.tool_name === 'shared_file'
                ? 'activity-files-v1'
                : 'activity-notice-v1',
          reasons:
            decision === 'BLOCK'
              ? blockReasons()
              : [
                  decision === 'CONFIRM'
                    ? req.tool_name === 'shared_file'
                      ? reason(
                          'ACTION_REQUIRES_CONFIRMATION',
                          '修改共享文件前需要用户确认。',
                          'MEDIUM',
                          'action',
                          'update'
                        )
                      : reason(
                          'BULK_ACTION_REQUIRES_CONFIRMATION',
                          '接收人数超过自动执行阈值。',
                          'HIGH',
                          'recipient_count',
                          40,
                          30
                        )
                    : reason('POLICY_MATCHED', '工具、操作和参数均符合当前授权。', 'LOW'),
                ],
        },
        req.request_id
      )
    )
  }
  function executed(t: Task, req: ToolRequest) {
    append(
      t,
      event(
        t.task_id,
        'TOOL_EXECUTED',
        {
          tool_request: req,
          output:
            req.tool_name === 'calendar'
              ? { created: true, event: req.arguments }
              : req.tool_name === 'shared_file'
                ? { updated: true, path: req.arguments.path }
                : { sent: true, notice: req.arguments },
        },
        req.request_id
      )
    )
  }
  function seed() {
    tasks.value = []
    approvals.value = []
    incidents.value = []
    runtimes.value = {}
    const normal = taskBase('normal', '社区公益活动 · 日程创建')
    const req = toolRequest(normal.task_id, 'normal', 'calendar')
    append(normal, event(normal.task_id, 'TASK_STARTED', { summary: '已读取脱敏活动资料' }))
    policy(normal, req, 'ALLOW')
    executed(normal, req)
    normal.status = 'COMPLETED'
    const blocked = taskBase('block', '异常附件 · 敏感名单外发')
    const b = toolRequest(blocked.task_id, 'block')
    append(blocked, event(blocked.task_id, 'TOOL_REQUESTED', { tool_request: b }, b.request_id))
    policy(blocked, b, 'BLOCK')
    blocked.status = 'BLOCKED'
    tasks.value = [normal, blocked]
    selectedId.value = normal.task_id
    save()
  }
  async function initialize() {
    if (mode.value === 'live') {
      await loadCurrentUser()
      await refresh()
      return
    }
    await loadCurrentUser()
    try {
      const raw = localStorage.getItem(STORAGE)
      if (raw) {
        const d = JSON.parse(raw)
        if (
          d.version === 1 &&
          Array.isArray(d.tasks) &&
          Array.isArray(d.approvals) &&
          Array.isArray(d.incidents) &&
          d.tasks.every((t: Task) => typeof t.task_id === 'string' && Array.isArray(t.events))
        ) {
          tasks.value = d.tasks
          approvals.value = d.approvals
          incidents.value = d.incidents
          selectedId.value = d.selectedId
          runtimes.value = d.runtimes || {}
          for (const r of Object.values(runtimes.value)) {
            r.paused = true
            r.next = Date.now() + 900
          }
          tick()
          return
        }
      }
    } catch {
      /* 损坏缓存重置演示 */
    }
    seed()
  }
  async function create(
    scenario: Scenario,
    title: string,
    description: string,
    files: FileMeta[],
    replay = false,
    activity?: ActivityInput,
    reference?: ActivityReference
  ) {
    if (busy.value) return
    busy.value = true
    try {
      if (mode.value === 'live') {
        const t = await liveApi.create({
          title, description, scenario, files, permissions: [], activity, reference,
        })
        t.events = t.events || []
        tasks.value.unshift(t)
        selectedId.value = t.task_id
        return t
      }
      const t = taskBase(scenario, title, replay)
      t.description = description
      t.files = files
      tasks.value.unshift(t)
      selectedId.value = t.task_id
      runtimes.value[t.task_id] = {
        step: 0,
        next: Date.now() + 250,
        paused: false,
        speed: 1,
        waiting: false,
        request: null,
      }
      save()
      return t
    } catch (e) {
      notify(e instanceof Error ? e.message : '创建任务失败')
    } finally {
      busy.value = false
    }
  }
  function tick() {
    now.value = Date.now()
    if (mode.value !== 'mock') return
    let changed = false
    for (const a of pending.value) {
      if (new Date(a.expires_at).getTime() <= now.value) {
        const t = tasks.value.find((t) => t.task_id === a.task_id)
        a.status = 'EXPIRED'
        a.resolved_at = new Date().toISOString()
        if (t) {
          t.status = 'EXPIRED'
          append(
            t,
            event(
              t.task_id,
              'APPROVAL_EXPIRED',
              { approval_id: a.approval_id, summary: '到期未确认，操作已取消' },
              a.request_id
            )
          )
          delete runtimes.value[t.task_id]
        }
        changed = true
      }
    }
    for (const [id, r] of Object.entries(runtimes.value)) {
      if (r.paused || r.waiting || r.next > now.value) continue
      const t = tasks.value.find((t) => t.task_id === id)
      if (!t) {
        delete runtimes.value[id]
        continue
      }
      r.next = now.value + 1000 / r.speed
      changed = true
      if (r.step === 0) {
        append(t, event(id, 'TASK_STARTED', { summary: '接收活动事务请求，读取预置脱敏演示资料' }))
        t.status = 'ANALYZING'
      }
      if (r.step === 1) {
        r.request = toolRequest(id, t.scenario, 'calendar')
        append(t, event(id, 'TOOL_REQUESTED', { tool_request: r.request }, r.request.request_id))
        policy(t, r.request, 'ALLOW')
        t.status = 'EXECUTING'
      }
      if (r.step === 2 && r.request) executed(t, r.request)
      if (r.step === 3) {
        r.request = toolRequest(
          id,
          t.scenario,
          t.scenario === 'recovery' ? 'shared_file' : 'send_notice'
        )
        append(t, event(id, 'TOOL_REQUESTED', { tool_request: r.request }, r.request.request_id))
        const d = t.scenario === 'block' ? 'BLOCK' : t.scenario === 'normal' ? 'ALLOW' : 'CONFIRM'
        policy(t, r.request, d)
        if (d === 'BLOCK') {
          t.status = 'BLOCKED'
          delete runtimes.value[id]
        }
        if (d === 'CONFIRM') {
          const a: Approval = {
            approval_id: uid(),
            request_id: r.request.request_id,
            task_id: id,
            summary: t.scenario === 'recovery' ? '更新共享排班文件' : '向 40 名活动参与者发送通知',
            status: 'PENDING',
            expires_at: new Date(now.value + 60000).toISOString(),
            tool_request: r.request,
            reasons:
              [...t.events].reverse().find((e) => e.event_type === 'POLICY_DECISION')?.payload
                .reasons || [],
          }
          approvals.value.unshift(a)
          append(
            t,
            event(
              id,
              'APPROVAL_REQUIRED',
              {
                status: 'PENDING',
                approval_id: a.approval_id,
                expires_at: a.expires_at,
                tool_request: r.request,
              },
              r.request.request_id
            )
          )
          t.status = 'WAITING_APPROVAL'
          r.waiting = true
          notify('一项操作需要确认，请前往人工审批台。')
        }
      }
      if (r.step === 4 && r.request) {
        if (t.scenario === 'normal') {
          executed(t, r.request)
          t.status = 'COMPLETED'
          delete runtimes.value[id]
        } else if (t.scenario === 'recovery')
          append(
            t,
            event(
              id,
              'TOOL_FAILED',
              { tool_request: r.request, error: '模拟文件服务超时', attempt: 1 },
              r.request.request_id
            )
          )
      }
      if (r.step === 5 && r.request)
        append(
          t,
          event(
            id,
            'TOOL_FAILED',
            { tool_request: r.request, error: '模拟文件服务超时', attempt: 2 },
            r.request.request_id
          )
        )
      if (r.step === 6 && r.request) {
        append(
          t,
          event(
            id,
            'TOOL_FAILED',
            { tool_request: r.request, error: '模拟文件服务超时', attempt: 3 },
            r.request.request_id
          )
        )
        append(
          t,
          event(id, 'INCIDENT_TRIGGERED', { summary: '共享文件更新连续失败 3 次，停止后续动作' })
        )
        t.status = 'RECOVERING'
        incidents.value.unshift({
          incident_id: uid(),
          task_id: id,
          reason: '共享文件工具连续超时，达到 3 次熔断阈值。',
          status: 'RECOVERING',
          created_at: new Date().toISOString(),
          before: 'name,role\n演示志愿者A,签到接待\n演示志愿者B,现场引导',
          damaged: 'name,role\n演示志愿者A,待分配',
          after: null,
          cancelled_count: 0,
        })
      }
      const incident = incidents.value.find((i) => i.task_id === id)
      if (r.step === 7 && incident) {
        incident.cancelled_count = 1
        append(t, event(id, 'ACTION_CANCELLED', { summary: '已取消尚未发送的活动通知', count: 1 }))
      }
      if (r.step === 8 && incident) {
        incident.after = incident.before
        append(
          t,
          event(id, 'SNAPSHOT_RESTORED', {
            summary: '共享排班文件恢复到操作前快照',
            path: '/workspace/activities/roster.csv',
          })
        )
      }
      if (r.step === 9 && incident) {
        incident.status = 'RECOVERED'
        t.status = 'RECOVERED'
        append(t, event(id, 'RECOVERY_COMPLETED', { summary: '模拟文件已恢复，后续通知已取消' }))
        delete runtimes.value[id]
      }
      r.step++
    }
    if (changed) save()
  }
  async function decide(id: string, approved: boolean) {
    const a = approvals.value.find((a) => a.approval_id === id)
    if (!a || a.status !== 'PENDING' || busy.value) return
    if (mode.value === 'mock' && new Date(a.expires_at).getTime() <= Date.now()) {
      tick()
      notify('审批已过期，操作已取消。')
      return
    }
    busy.value = true
    try {
      if (mode.value === 'live') {
        const result = await liveApi.decide(id, approved)
        Object.assign(a, result)
        busy.value = false
        await refresh()
        return
      }
      const t = tasks.value.find((t) => t.task_id === a.task_id)
      if (!t) throw new Error('关联任务不存在')
      a.status = approved ? 'APPROVED' : 'REJECTED'
      a.resolved_at = new Date().toISOString()
      append(t, event(t.task_id, 'APPROVAL_RESOLVED', { approved, approval_id: id }, a.request_id))
      if (approved) {
        if (t.scenario === 'recovery') {
          t.status = 'EXECUTING'
          const run = runtimes.value[t.task_id]
          if (run) {
            run.waiting = false
            run.next = Date.now() + 600
          }
        } else {
          executed(t, a.tool_request)
          t.status = 'COMPLETED'
          delete runtimes.value[t.task_id]
        }
      } else {
        t.status = 'REJECTED'
        delete runtimes.value[t.task_id]
      }
      notify(approved ? '已批准：继续执行授权操作。' : '已拒绝：工具不会执行该操作。')
      save()
    } catch (e) {
      notify(e instanceof Error ? e.message : '审批请求失败')
    } finally {
      busy.value = false
    }
  }
  function togglePause() {
    const r = currentRun.value
    if (r) {
      r.paused = !r.paused
      r.next = Date.now() + 600
      save()
    }
  }
  function setSpeed(value: number) {
    if (currentRun.value) {
      currentRun.value.speed = value
      save()
    }
  }
  async function restart() {
    const t = current.value
    if (!t) return
    if (mode.value === 'live') return
    delete runtimes.value[t.task_id]
    if (['ANALYZING', 'EXECUTING', 'RECOVERING'].includes(t.status)) {
      t.status = 'CANCELLED'
      append(t, event(t.task_id, 'TASK_CANCELLED', { summary: '重新回放，原模拟会话停止推进' }))
    }
    for (const a of approvals.value.filter(
      (a) => a.task_id === t.task_id && a.status === 'PENDING'
    )) {
      a.status = 'REJECTED'
      a.resolved_at = new Date().toISOString()
      append(
        t,
        event(
          t.task_id,
          'APPROVAL_RESOLVED',
          { approved: false, summary: '重新回放，原请求取消' },
          a.request_id
        )
      )
      t.status = 'REJECTED'
    }
    await create(t.scenario, t.title + ' · 回放', t.description, [], true)
  }
  async function refresh() {
    if (mode.value !== 'live' || busy.value) return
    busy.value = true
    try {
      const rows = await liveApi.tasks()
      tasks.value = rows.map((t) => ({ ...t, events: t.events || [] }))
      if (!selectedId.value || !rows.some((t) => t.task_id === selectedId.value))
        selectedId.value = rows[0]?.task_id || ''
      approvals.value = await liveApi.approvals()
      if (selectedId.value) {
        const eventTaskId = selectedId.value
        const events = await liveApi.events(eventTaskId)
        if (!Array.isArray(events)) throw new Error('事件接口应返回数组')
        const t = tasks.value.find((t) => t.task_id === eventTaskId)
        if (t) t.events = [...new Map(events.map((e) => [e.event_id, e])).values()]
      }
      connected.value = true
    } catch (e) {
      connected.value = false
      notify(`真实后端尚未连接：${e instanceof Error ? e.message : '网络异常'}`)
    } finally {
      busy.value = false
    }
  }
  function reset() {
    if (mode.value !== 'mock') return
    seed()
    notify('已重置演示会话。')
  }
  function select(id: string) {
    selectedId.value = id
    save()
    if (mode.value === 'live') void refresh()
  }
  function exportTrace() {
    if (!current.value) return
    const blob = new Blob(
      [
        JSON.stringify(
          { data_source: mode.value, task: current.value, exported_at: new Date().toISOString() },
          null,
          2
        ),
      ],
      { type: 'application/json' }
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `agentguard-${current.value.task_id}.json`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return {
    mode,
    currentUser,
    tasks,
    approvals,
    incidents,
    selectedId,
    runtimes,
    message,
    busy,
    now,
    connected,
    current,
    pending,
    currentRun,
    initialize,
    loadCurrentUser,
    create,
    tick,
    decide,
    togglePause,
    setSpeed,
    restart,
    refresh,
    reset,
    select,
    notify,
    exportTrace,
  }
})
