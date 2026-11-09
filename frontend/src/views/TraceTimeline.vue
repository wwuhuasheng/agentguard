<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  GitBranch,
  Download,
  Play,
  Pause,
  RotateCcw,
  ArrowRight,
  ShieldCheck,
  Check,
  Clock3,
  Ban,
  AlertTriangle,
  ChevronDown,
} from 'lucide-vue-next'
import { useConsoleStore } from '../stores/console'
import { eventLabels, toolLabels, trustLabels, display, time } from '../labels'
import { scenarios } from '../mock/scenarios'
import StatusBadge from '../components/StatusBadge.vue'
import RiskCard from '../components/RiskCard.vue'
import TaskPicker from '../components/TaskPicker.vue'
import type { AuditEvent, Scenario } from '../types'
const s = useConsoleStore(),
  typeFilter = ref('all'),
  expanded = ref<string | null>(null),
  manualEvidence = ref<string | null>(null),
  newScenario = ref<Scenario>('approval')
const events = computed(
  () =>
    s.current?.events.filter(
      (e) => typeFilter.value === 'all' || e.event_type === typeFilter.value
    ) || []
)
const evidence = computed(
  () =>
    s.current?.events.find((e) => e.event_id === manualEvidence.value) ||
    [...(s.current?.events || [])].reverse().find((e) => e.event_type === 'POLICY_DECISION')
)
watch(
  () => s.selectedId,
  () => {
    expanded.value = null
    manualEvidence.value = null
  }
)
function inspect(e: AuditEvent) {
  expanded.value = expanded.value === e.event_id ? null : e.event_id
  if (e.event_type === 'POLICY_DECISION') manualEvidence.value = e.event_id
}
function icon(e: AuditEvent) {
  return e.payload.decision === 'BLOCK'
    ? Ban
    : e.event_type === 'TOOL_FAILED'
      ? AlertTriangle
      : e.event_type === 'APPROVAL_REQUIRED'
        ? Clock3
        : e.event_type === 'TOOL_EXECUTED'
          ? Check
          : ShieldCheck
}
function summary(e: AuditEvent) {
  return (
    e.payload.summary ||
    e.payload.error ||
    e.payload.reasons?.[0]?.message ||
    (e.payload.approved === true
      ? '用户批准，操作可以继续'
      : e.payload.approved === false
        ? '用户拒绝，停止该操作'
        : e.payload.tool_request
          ? `${toolLabels[e.payload.tool_request.tool_name] || e.payload.tool_request.tool_name} / ${e.payload.tool_request.action}`
          : '执行事件已记录')
  )
}
async function start() {
  await s.create(
    newScenario.value,
    scenarios.find((x) => x.id === newScenario.value)!.title + ' · 回放',
    '演示预置可信执行事件。',
    [],
    true
  )
}
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">OBSERVE / EXECUTION TRACE</span>
      <h1>每一步，都有迹可循<span class="heading-dot">.</span></h1>
      <p>从信息来源到工具结果，查看 Agent 的可解释执行记录。</p>
    </div>
    <button class="button" :disabled="!s.current" @click="s.exportTrace()">
      <Download :size="16" />导出 Trace
    </button>
  </div>
  <div class="toolbar panel">
    <TaskPicker />
    <div class="row" v-if="s.current">
      <StatusBadge :value="s.current.status" /><span class="small muted"
        >{{ s.current.events.length }} 条事件</span
      >
    </div>
  </div>
  <div v-if="s.mode === 'mock'" class="playback-bar">
    <div class="row">
      <span class="demo-label">{{ s.current?.replay ? 'TRACE REPLAY' : 'MOCK SESSION' }}</span
      ><template v-if="s.currentRun"
        ><button class="button small-button" @click="s.togglePause()">
          <Play v-if="s.currentRun.paused" :size="14" /><Pause v-else :size="14" />{{
            s.currentRun.paused ? '继续' : '暂停'
          }}</button
        ><select
          :value="s.currentRun.speed"
          aria-label="播放速度"
          @change="s.setSpeed(Number(($event.target as HTMLSelectElement).value))"
        >
          <option :value="1">1× 速度</option>
          <option :value="2">2× 速度</option>
          <option :value="4">4× 速度</option>
        </select></template
      ><button class="text-button" :disabled="!s.current" @click="s.restart()">
        <RotateCcw :size="14" />重新回放
      </button>
    </div>
    <div class="row">
      <select v-model="newScenario" aria-label="选择回放场景">
        <option v-for="x in scenarios" :key="x.id" :value="x.id">{{ x.title }}</option></select
      ><button class="button primary small-button" @click="start">
        <Play :size="14" />开始回放
      </button>
    </div>
  </div>
  <div v-if="s.current?.status === 'WAITING_APPROVAL'" class="approval-banner">
    <Clock3 :size="20" />
    <div>
      <strong>任务正在等待你的确认</strong><span>批准后继续执行，拒绝或超时将取消该操作。</span>
    </div>
    <RouterLink to="/approvals" class="button primary"
      >前往审批<ArrowRight :size="15"
    /></RouterLink>
  </div>
  <div v-if="s.current" class="trace-layout">
    <section class="panel">
      <div class="panel-heading">
        <h2>执行时间线</h2>
        <select v-model="typeFilter" aria-label="筛选事件类型">
          <option value="all">全部事件</option>
          <option v-for="(label, key) in eventLabels" :key="key" :value="key">{{ label }}</option>
        </select>
      </div>
      <div class="timeline">
        <article
          v-for="(e, i) in events"
          :key="e.event_id"
          class="timeline-item"
          :class="{ blocked: e.payload.decision === 'BLOCK' }"
        >
          <div class="timeline-marker"><component :is="icon(e)" :size="16" /></div>
          <div class="timeline-content">
            <button
              class="timeline-trigger"
              :aria-expanded="expanded === e.event_id"
              @click="inspect(e)"
            >
              <div class="row between">
                <span class="row"
                  ><strong>{{ eventLabels[e.event_type] || e.event_type }}</strong
                  ><StatusBadge v-if="e.payload.decision" :value="e.payload.decision" /></span
                ><span class="row"
                  ><time class="mono">{{ time(e.created_at) }}</time
                  ><ChevronDown :size="15"
                /></span>
              </div>
              <p>{{ summary(e) }}</p>
              <div class="timeline-foot">
                <code>{{ String(i + 1).padStart(2, '0') }} / {{ e.event_type }}</code
                ><span v-if="e.payload.tool_request">{{
                  trustLabels[e.payload.tool_request.source_trust]
                }}</span>
              </div>
            </button>
            <div v-if="expanded === e.event_id" class="event-details">
              <dl>
                <div>
                  <dt>事件 ID</dt>
                  <dd class="mono">{{ e.event_id }}</dd>
                </div>
                <div>
                  <dt>请求 ID</dt>
                  <dd class="mono">{{ e.request_id || '任务级事件' }}</dd>
                </div>
              </dl>
              <strong class="small">结构化事件</strong>
              <pre>{{ display(e.payload) }}</pre>
            </div>
          </div>
        </article>
        <div v-if="!events.length" class="empty-state">
          <GitBranch :size="30" />
          <h3>等待执行事件</h3>
          <p>启动任务后，事件将按顺序出现在这里。</p>
        </div>
        <div
          v-if="s.currentRun && !s.currentRun.paused && !s.currentRun.waiting"
          class="timeline-running"
        >
          <span class="pulse-dot"></span>正在接收模拟事件…
        </div>
      </div>
    </section>
    <aside class="trace-aside">
      <RiskCard v-if="evidence" :event="evidence" />
      <section v-if="s.current.agent_plan" class="panel padded">
        <span class="eyebrow">AGENT PLAN / TASK PASSPORT</span>
        <h3>规划与授权证据</h3>
        <p class="helper">当前由本地离线适配器生成计划；此处不代表已接入华为云 AgentArts。</p>
        <dl class="context-list">
          <div>
            <dt>规划来源</dt>
            <dd>{{ s.current.agent_plan.provider }}</dd>
          </div>
          <div>
            <dt>授权步骤</dt>
            <dd>{{ s.current.agent_plan.step_count }}</dd>
          </div>
          <div>
            <dt>护照 ID</dt>
            <dd class="mono">{{ s.current.passport_id?.slice(0, 8) }}</dd>
          </div>
        </dl>
        <div v-for="agent in s.current.agent_plan.agent_evidence" :key="agent.role" class="approval-reason">
          <ShieldCheck :size="17" />
          <div><code>{{ agent.role }}</code><p>{{ agent.conclusion }}</p></div>
        </div>
      </section>
      <section class="panel padded">
        <span class="eyebrow">TRACE CONTEXT</span>
        <h3>{{ s.current.title }}</h3>
        <p class="muted">{{ s.current.description }}</p>
        <dl class="context-list">
          <div>
            <dt>数据源</dt>
            <dd>{{ s.mode === 'mock' ? '预置模拟事件' : '真实后端事件' }}</dd>
          </div>
          <div>
            <dt>任务 ID</dt>
            <dd class="mono">{{ s.current.task_id.slice(0, 8) }}</dd>
          </div>
          <div>
            <dt>已记录事件</dt>
            <dd>{{ s.current.events.length }}</dd>
          </div>
        </dl>
        <p class="helper">记录工具调用与策略结果，不展示或推测模型的内部思维过程。</p>
      </section>
    </aside>
  </div>
  <div v-else class="panel empty-state">
    <GitBranch :size="36" />
    <h3>还没有选中的任务</h3>
    <p>先去控制台创建任务，或启动一条演示回放。</p>
    <RouterLink to="/" class="button primary">返回任务控制台</RouterLink>
  </div>
</template>
