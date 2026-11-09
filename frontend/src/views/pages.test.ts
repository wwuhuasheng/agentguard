// @vitest-environment happy-dom
import { beforeEach, afterEach, describe, it, expect, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import TaskConsole from './TaskConsole.vue'
import ApprovalCenter from './ApprovalCenter.vue'
import TraceTimeline from './TraceTimeline.vue'
import EvaluationBoard from './EvaluationBoard.vue'
import IncidentDetail from './IncidentDetail.vue'
import App from '../App.vue'
import { useConsoleStore } from '../stores/console'
let wrapper: VueWrapper | undefined
beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-06T02:00:00Z'))
  setActivePinia(createPinia())
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
async function render(component: any, live = false) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const s = useConsoleStore()
  await s.initialize()
  if (live) s.mode = 'live'
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  await router.push('/')
  wrapper = mount(component, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return s
}
function tick(s: ReturnType<typeof useConsoleStore>, n: number) {
  for (let i = 0; i < n; i++) {
    vi.advanceTimersByTime(1100)
    s.tick()
  }
}
describe('rendered page interactions', () => {
  it('shows the user returned by the store and does not show a product version', async () => {
    await render(App)
    expect(wrapper!.text()).toContain('演示用户')
    expect(wrapper!.text()).toContain('demo-user')
    expect(wrapper!.text()).not.toContain('v0.1')
  })

  it('submits a task through the form', async () => {
    const s = await render(TaskConsole)
    await wrapper!.get('#task-name').setValue('UI test task')
    await wrapper!.get('form').trigger('submit')
    await flushPromises()
    expect(s.tasks[0]!.title).toBe('UI test task')
    expect(s.tasks[0]!.scenario).toBe('approval')
  })
  it('submits structured activity fields in live mode', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 201,
      json: async () => ({
        task_id: 'live-activity-1',
        title: '周末读书会',
        description: '请提前到场',
        scenario: 'activity',
        status: 'WAITING_APPROVAL',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        files: [],
        permissions: [],
        events: [],
        replay: false,
      }),
    }))
    vi.stubGlobal('fetch', fetchMock)
    const s = await render(TaskConsole, true)
    await wrapper!.get('#task-name').setValue('周末读书会')
    await wrapper!.get('#task-description').setValue('请提前到场')
    await wrapper!.get('#activity-time').setValue('2026-11-15T10:00')
    await wrapper!.get('#activity-location').setValue('社区图书馆')
    await wrapper!.get('#activity-recipient').setValue('readers@example.org')
    await wrapper!.get('#activity-count').setValue('40')
    await wrapper!.get('form').trigger('submit')
    await flushPromises()
    const [url, request] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/api/tasks')
    const body = JSON.parse(String(request.body))
    expect(body.scenario).toBe('activity')
    expect(body.activity.location).toBe('社区图书馆')
    expect(body.activity.recipient).toBe('readers@example.org')
    expect(body.activity.recipient_count).toBe(40)
    expect(body.activity.starts_at).toBe('2026-11-15T10:00:00+08:00')
    expect(s.tasks[0]!.task_id).toBe('live-activity-1')
  })
  it('filters task records by title', async () => {
    await render(TaskConsole)
    await wrapper!.get('[aria-label="搜索任务"]').setValue('impossible-name')
    expect(wrapper!.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper!.text()).toContain('没有')
  })
  it('approves through the actual approval button then shows history', async () => {
    const s = await render(ApprovalCenter)
    await s.create('approval', 'UI approval', 'test', [])
    tick(s, 4)
    await flushPromises()
    const approve = wrapper!.findAll('button').find((b) => b.text().includes('批准执行'))!
    expect(approve.exists()).toBe(true)
    await approve.trigger('click')
    await flushPromises()
    expect(s.current!.status).toBe('COMPLETED')
    expect(wrapper!.text()).toContain('当前没有待审批')
    await wrapper!.findAll('.tabs button')[1]!.trigger('click')
    expect(wrapper!.text()).toContain('UI approval')
  })
  it('filters and expands timeline events', async () => {
    await render(TraceTimeline)
    await wrapper!.get('[aria-label="筛选事件类型"]').setValue('POLICY_DECISION')
    expect(wrapper!.findAll('.timeline-item')).toHaveLength(1)
    await wrapper!.get('.timeline-trigger').trigger('click')
    expect(wrapper!.get('.event-details').text()).toContain('POLICY_MATCHED')
  })
  it('evaluates 60 fixtures, paginates and filters failures', async () => {
    await render(EvaluationBoard)
    expect(wrapper!.text()).toContain('非真实评测结论')
    expect(wrapper!.findAll('tbody tr')).toHaveLength(10)
    await wrapper!.findAll('.pagination button')[1]!.trigger('click')
    expect(wrapper!.find('tbody').text()).toContain('DEMO-011')
    await wrapper!.get('[aria-label="筛选样例结果"]').setValue('fail')
    expect(wrapper!.findAll('tbody tr')).toHaveLength(4)
    expect(wrapper!.text()).toContain('1 / 1')
  })
  it('shows snapshot equality after the recovery scenario', async () => {
    const s = await render(IncidentDetail)
    await wrapper!
      .findAll('button')
      .find((b) => b.text() === '启动恢复演示')!
      .trigger('click')
    tick(s, 4)
    await s.decide(s.pending[0]!.approval_id, true)
    tick(s, 6)
    await flushPromises()
    expect(wrapper!.findAll('.diff-grid pre')).toHaveLength(3)
    expect(wrapper!.findAll('.diff-grid pre')[0]!.text()).toBe(
      wrapper!.findAll('.diff-grid pre')[2]!.text()
    )
    expect(wrapper!.findAll('.recovery-log article')).toHaveLength(4)
  })
})
