import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useConsoleStore } from './console'
import { liveApi } from '../api/client'
import type { Scenario } from '../types'
const memory = new Map<string, string>()
beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-06T02:00:00Z'))
  memory.clear()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => memory.get(k) || null,
    setItem: (k: string, v: string) => memory.set(k, v),
  })
  setActivePinia(createPinia())
})
afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
function advance(s: ReturnType<typeof useConsoleStore>, count: number) {
  for (let i = 0; i < count; i++) {
    vi.advanceTimersByTime(1100)
    s.tick()
  }
}
async function start(scenario: Scenario) {
  const s = useConsoleStore()
  await s.initialize()
  await s.create(scenario, 'test', 'scenario', [])
  return s
}
function dangerous(s: ReturnType<typeof useConsoleStore>) {
  return s.current!.events.filter(
    (e) => e.event_type === 'TOOL_EXECUTED' && e.payload.tool_request?.tool_name !== 'calendar'
  )
}
describe('Mock execution boundaries', () => {
  it('loads an explicit example user in mock mode', async () => {
    const s = useConsoleStore()
    await s.initialize()
    expect(s.currentUser?.display_name).toBe('演示用户')
    expect(s.currentUser?.username).toBe('demo-user')
  })

  it('renders the backend user after a successful live profile request', async () => {
    const s = useConsoleStore()
    await s.initialize()
    s.mode = 'live'
    vi.spyOn(liveApi, 'currentUser').mockResolvedValue({
      user_id: 'user-42',
      username: 'backend.operator',
      display_name: '后端操作员',
      role: 'operator',
    })
    await s.loadCurrentUser()
    expect(s.currentUser?.display_name).toBe('后端操作员')
    expect(s.currentUser?.username).toBe('backend.operator')
  })

  it('clears the live profile when the backend user request fails', async () => {
    const s = useConsoleStore()
    await s.initialize()
    s.mode = 'live'
    vi.spyOn(liveApi, 'currentUser').mockRejectedValue(new Error('offline'))
    await s.loadCurrentUser()
    expect(s.currentUser).toBeNull()
    expect(s.message).toContain('offline')
  })

  it('cancels an active session on restart', async () => {
    const s = await start('normal')
    advance(s, 1)
    const old = s.current!.task_id
    await s.restart()
    expect(s.tasks.find((t) => t.task_id === old)?.status).toBe('CANCELLED')
    expect(s.runtimes[old]).toBeUndefined()
  })
  it('refreshes live task state after a successful approval', async () => {
    const s = await start('approval')
    advance(s, 4)
    const a = s.pending[0]!
    s.mode = 'live'
    vi.spyOn(liveApi, 'decide').mockResolvedValue({ ...a, status: 'APPROVED' })
    const tasks = vi
      .spyOn(liveApi, 'tasks')
      .mockResolvedValue(s.tasks.map((t) => ({ ...t, status: 'COMPLETED' })))
    vi.spyOn(liveApi, 'approvals').mockResolvedValue([{ ...a, status: 'APPROVED' }])
    vi.spyOn(liveApi, 'events').mockResolvedValue([])
    await s.decide(a.approval_id, true)
    expect(tasks).toHaveBeenCalledOnce()
    expect(s.current!.status).toBe('COMPLETED')
    expect(s.connected).toBe(true)
  })
  it('reports live failure without replacing data with a mock result', async () => {
    const s = await start('normal')
    s.mode = 'live'
    vi.spyOn(liveApi, 'tasks').mockRejectedValue(new Error('offline'))
    await s.refresh()
    expect(s.mode).toBe('live')
    expect(s.connected).toBe(false)
    expect(s.message).toContain('offline')
  })

  it('completes the normal scenario', async () => {
    const s = await start('normal')
    advance(s, 5)
    expect(s.current!.status).toBe('COMPLETED')
    expect(dangerous(s)).toHaveLength(1)
  })
  it('blocks unsafe request before execution', async () => {
    const s = await start('block')
    advance(s, 20)
    expect(s.current!.status).toBe('BLOCKED')
    expect(dangerous(s)).toHaveLength(0)
    expect(s.pending).toHaveLength(0)
  })
  it('waits for approval, executes once despite duplicate approval', async () => {
    const s = await start('approval')
    advance(s, 4)
    expect(s.current!.status).toBe('WAITING_APPROVAL')
    advance(s, 10)
    expect(dangerous(s)).toHaveLength(0)
    const id = s.pending[0]!.approval_id
    await s.decide(id, true)
    await s.decide(id, true)
    expect(dangerous(s)).toHaveLength(1)
    expect(s.current!.status).toBe('COMPLETED')
  })
  it('rejects without executing and cannot approve afterward', async () => {
    const s = await start('approval')
    advance(s, 4)
    const id = s.pending[0]!.approval_id
    await s.decide(id, false)
    await s.decide(id, true)
    advance(s, 10)
    expect(s.current!.status).toBe('REJECTED')
    expect(dangerous(s)).toHaveLength(0)
  })
  it('expires approvals even while playback is paused', async () => {
    const s = await start('approval')
    advance(s, 4)
    const id = s.pending[0]!.approval_id
    s.togglePause()
    vi.advanceTimersByTime(60001)
    s.tick()
    await s.decide(id, true)
    expect(s.current!.status).toBe('EXPIRED')
    expect(dangerous(s)).toHaveLength(0)
    expect(s.pending).toHaveLength(0)
  })
  it('rejects a late click even before the next periodic tick', async () => {
    const s = await start('approval')
    advance(s, 4)
    const id = s.pending[0]!.approval_id
    vi.advanceTimersByTime(60001)
    await s.decide(id, true)
    expect(s.current!.status).toBe('EXPIRED')
    expect(dangerous(s)).toHaveLength(0)
  })
  it('pauses progression then resumes', async () => {
    const s = await start('normal')
    s.togglePause()
    advance(s, 10)
    expect(s.current!.events).toHaveLength(0)
    s.togglePause()
    advance(s, 5)
    expect(s.current!.status).toBe('COMPLETED')
  })
  it('requires approval before three failures and recovery', async () => {
    const s = await start('recovery')
    advance(s, 4)
    expect(s.incidents).toHaveLength(0)
    expect(s.current!.status).toBe('WAITING_APPROVAL')
    await s.decide(s.pending[0]!.approval_id, true)
    advance(s, 6)
    expect(s.current!.events.filter((e) => e.event_type === 'TOOL_FAILED')).toHaveLength(3)
    expect(s.current!.status).toBe('RECOVERED')
    expect(s.incidents[0]!.after).toBe(s.incidents[0]!.before)
    expect(s.incidents[0]!.cancelled_count).toBe(1)
    expect(dangerous(s)).toHaveLength(0)
  })
  it('reset clears old timers and pending requests', async () => {
    const s = await start('approval')
    advance(s, 4)
    s.reset()
    advance(s, 100)
    expect(s.tasks).toHaveLength(2)
    expect(s.pending).toHaveLength(0)
    expect(Object.keys(s.runtimes)).toHaveLength(0)
  })
  it('restores session paused and resumes it without duplicate events', async () => {
    const s = await start('normal')
    advance(s, 2)
    const id = s.current!.task_id
    const count = s.current!.events.length
    setActivePinia(createPinia())
    const loaded = useConsoleStore()
    await loaded.initialize()
    expect(loaded.selectedId).toBe(id)
    expect(loaded.currentRun.paused).toBe(true)
    advance(loaded, 5)
    expect(loaded.current!.events).toHaveLength(count)
    loaded.togglePause()
    advance(loaded, 5)
    expect(loaded.current!.status).toBe('COMPLETED')
    expect(new Set(loaded.current!.events.map((e) => e.event_id)).size).toBe(
      loaded.current!.events.length
    )
  })
  it('restart cancels old approval and creates a separate replay', async () => {
    const s = await start('approval')
    advance(s, 4)
    const old = s.current!.task_id
    const approval = s.pending[0]!.approval_id
    await s.restart()
    expect(s.current!.task_id).not.toBe(old)
    expect(s.approvals.find((a) => a.approval_id === approval)?.status).toBe('REJECTED')
    expect(s.tasks.find((t) => t.task_id === old)?.status).toBe('REJECTED')
  })
})
