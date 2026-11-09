<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  History,
  ShieldCheck,
  ArrowRight,
  RotateCcw,
  FileCheck2,
  OctagonPause,
  Check,
  Clock3,
} from 'lucide-vue-next'
import { useConsoleStore } from '../stores/console'
import { eventLabels, time } from '../labels'
import StatusBadge from '../components/StatusBadge.vue'
const s = useConsoleStore(),
  selected = ref(''),
  busy = ref(false)
const incident = computed(
  () => s.incidents.find((i) => i.incident_id === selected.value) || s.incidents[0]
)
const task = computed(() => s.tasks.find((t) => t.task_id === incident.value?.task_id))
const recoveryEvents = computed(
  () =>
    task.value?.events.filter((e) =>
      [
        'INCIDENT_TRIGGERED',
        'ACTION_CANCELLED',
        'SNAPSHOT_RESTORED',
        'RECOVERY_COMPLETED',
      ].includes(e.event_type)
    ) || []
)
async function start() {
  busy.value = true
  const t = await s.create(
    'recovery',
    '共享排班文件 · 故障恢复演示',
    '模拟文件服务连续超时，熔断后取消通知并恢复快照。',
    [],
    true
  )
  busy.value = false
  if (t) s.notify('恢复演示已启动。请先到审批台批准文件更新，再观察恢复过程。')
}
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">RECOVER / INCIDENT MANAGEMENT</span>
      <h1>异常发生后，仍可掌控<span class="heading-dot">.</span></h1>
      <p>停止后续动作，保留现场证据，恢复模拟业务状态。</p>
    </div>
    <button v-if="s.mode === 'mock'" class="button primary" :disabled="busy" @click="start">
      <RotateCcw :size="16" />启动恢复演示
    </button>
  </div>
  <div class="notice recovery-note">
    <ShieldCheck :size="19" /><span>{{
      s.mode === 'mock'
        ? '恢复仅作用于演示工作区快照。此流程不代表真实通知可以撤回。'
        : '恢复 HTTP 契约仍待确认，当前页面尚未接入真实恢复服务。'
    }}</span>
  </div>
  <div
    v-if="
      s.pending.some((a) => s.tasks.find((t) => t.task_id === a.task_id)?.scenario === 'recovery')
    "
    class="approval-banner"
  >
    <Clock3 :size="19" />
    <div>
      <strong>文件更新需要确认</strong><span>批准后将模拟连续失败，随后触发熔断恢复。</span>
    </div>
    <RouterLink to="/approvals" class="button primary"
      >前往审批<ArrowRight :size="15"
    /></RouterLink>
  </div>
  <template v-if="incident"
    ><div class="toolbar panel">
      <label class="task-picker"
        ><span>恢复事件</span
        ><select v-model="selected" aria-label="选择恢复事件">
          <option value="" disabled>最近一条恢复事件</option>
          <option v-for="i in s.incidents" :key="i.incident_id" :value="i.incident_id">
            {{ i.incident_id.slice(0, 8) }} ·
            {{ s.tasks.find((t) => t.task_id === i.task_id)?.title }}
          </option>
        </select></label
      ><StatusBadge :value="incident.status" />
    </div>
    <div class="recovery-summary">
      <article class="panel padded">
        <span class="eyebrow">CIRCUIT BREAKER</span><OctagonPause :size="25" />
        <h2>连续 3 次失败，触发熔断</h2>
        <p class="muted">{{ incident.reason }}</p>
        <small class="mono"
          >{{ time(incident.created_at) }} · {{ incident.incident_id.slice(0, 8) }}</small
        >
      </article>
      <article class="panel padded">
        <span class="eyebrow">CANCELLED ACTIONS</span
        ><strong class="big-number">{{
          incident.cancelled_count.toString().padStart(2, '0')
        }}</strong>
        <h3>后续通知已取消</h3>
        <p class="muted">尚未发送的通知停止执行，避免错误继续扩散。</p>
      </article>
      <article class="panel padded">
        <span class="eyebrow">SNAPSHOT RECOVERY</span><FileCheck2 :size="25" />
        <h2>{{ incident.after ? '快照已恢复' : '等待快照恢复' }}</h2>
        <p class="muted">共享文件恢复到本次操作前的状态。</p>
        <span class="small">{{
          incident.after === incident.before ? '内容一致性校验通过' : '恢复进行中'
        }}</span>
      </article>
    </div>
    <div class="panel">
      <div class="panel-heading">
        <div>
          <h2>共享文件状态对比</h2>
          <p>/workspace/activities/roster.csv · 模拟快照</p>
        </div>
        <StatusBadge :value="incident.status" />
      </div>
      <div class="diff-grid">
        <section>
          <span class="eyebrow">01 / BEFORE</span>
          <h3>操作前快照</h3>
          <pre>{{ incident.before }}</pre>
        </section>
        <section>
          <span class="eyebrow">02 / INTERRUPTED</span>
          <h3>异常中间状态</h3>
          <pre>{{ incident.damaged }}</pre>
        </section>
        <section :class="{ restored: incident.after }">
          <span class="eyebrow">03 / RESTORED</span>
          <h3>恢复后状态 <Check v-if="incident.after" :size="16" /></h3>
          <pre>{{ incident.after || '等待恢复…' }}</pre>
        </section>
      </div>
    </div>
    <section class="panel recovery-log">
      <div class="panel-heading">
        <h2>恢复动作记录</h2>
        <RouterLink to="/trace" class="text-button" @click="s.select(incident.task_id)"
          >查看完整轨迹<ArrowRight :size="14"
        /></RouterLink>
      </div>
      <article v-for="e in recoveryEvents" :key="e.event_id">
        <span class="mono muted">{{ time(e.created_at) }}</span
        ><strong>{{ eventLabels[e.event_type] }}</strong
        ><span>{{ e.payload.summary }}</span
        ><Check :size="16" />
      </article></section
  ></template>
  <div v-else class="panel empty-state large-empty">
    <span class="empty-icon"><History :size="32" :stroke-width="1.3" /></span>
    <h2>暂无异常恢复事件</h2>
    <p>启动恢复演示并批准文件更新，查看熔断、取消和快照恢复的完整流程。</p>
    <button v-if="s.mode === 'mock'" class="button" :disabled="busy" @click="start">
      体验恢复流程<ArrowRight :size="15" />
    </button>
  </div>
</template>
