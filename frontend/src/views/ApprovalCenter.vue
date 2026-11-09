<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  Clock3,
  Check,
  X,
  ArrowRight,
  Inbox,
  ShieldCheck,
  FileText,
  Users,
  ExternalLink,
} from 'lucide-vue-next'
import { useConsoleStore } from '../stores/console'
import StatusBadge from '../components/StatusBadge.vue'
import { dateTime, display, toolLabels, trustLabels } from '../labels'
const paramLabels: Record<string, string> = {
  recipient: '接收地址',
  recipient_count: '接收人数',
  content: '内容预览',
  path: '文件路径',
  fields: '涉及字段',
}
const s = useConsoleStore(),
  selected = ref(''),
  tab = ref('pending')
const rows = computed(() =>
  s.approvals.filter((a) =>
    tab.value === 'pending' ? a.status === 'PENDING' : a.status !== 'PENDING'
  )
)
const active = computed(
  () => rows.value.find((a) => a.approval_id === selected.value) || rows.value[0]
)
watch(
  () => s.pending.map((a) => a.approval_id).join(','),
  () => {
    if (s.pending.some((a) => a.task_id === s.selectedId))
      selected.value = s.pending.find((a) => a.task_id === s.selectedId)!.approval_id
  },
  { immediate: true }
)
const seconds = computed(() =>
  Math.max(0, Math.ceil((new Date(active.value?.expires_at || 0).getTime() - s.now) / 1000))
)
const taskTitle = computed(() => s.tasks.find((t) => t.task_id === active.value?.task_id)?.title)
function viewTask() {
  if (active.value) s.select(active.value.task_id)
}
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">CONTROL / HUMAN APPROVAL</span>
      <h1>关键操作，由你决定<span class="heading-dot">.</span></h1>
      <p>看清数据范围和影响对象，再决定是否执行。</p>
    </div>
    <span class="mode-pill"><Clock3 :size="14" />{{ s.pending.length }} 项等待确认</span>
  </div>
  <div class="tabs">
    <button :class="{ active: tab === 'pending' }" @click="tab = 'pending'">
      待审批<span>{{ s.pending.length }}</span></button
    ><button :class="{ active: tab === 'history' }" @click="tab = 'history'">
      审批历史<span>{{ s.approvals.length - s.pending.length }}</span>
    </button>
  </div>
  <div v-if="rows.length" class="approval-layout">
    <aside class="panel approval-list">
      <div class="panel-heading">
        <h2>操作请求</h2>
        <span class="section-number">{{ String(rows.length).padStart(2, '0') }}</span>
      </div>
      <button
        v-for="a in rows"
        :key="a.approval_id"
        class="approval-list-item"
        :class="{ selected: active?.approval_id === a.approval_id }"
        @click="selected = a.approval_id"
      >
        <div class="row between">
          <span class="small mono">{{ a.request_id.slice(0, 8) }}</span
          ><StatusBadge :value="a.status" />
        </div>
        <h3>{{ a.summary }}</h3>
        <span class="small muted"
          >{{ toolLabels[a.tool_request.tool_name] }} / {{ a.tool_request.action }}</span
        ><ArrowRight :size="16" />
      </button>
    </aside>
    <section v-if="active" class="panel approval-detail">
      <div class="panel-heading">
        <div>
          <span class="eyebrow">REQUEST FOR APPROVAL</span>
          <h2>{{ active.summary }}</h2>
          <p>{{ taskTitle }}</p>
        </div>
        <div v-if="active.status === 'PENDING'" class="countdown">
          <Clock3 :size="17" /><b
            >{{ Math.floor(seconds / 60) }}:{{ String(seconds % 60).padStart(2, '0') }}</b
          ><small>后自动取消</small>
        </div>
        <StatusBadge v-else :value="active.status" />
      </div>
      <div class="approval-body">
        <div class="notice">
          <ShieldCheck :size="18" /><span>{{
            active.status === 'PENDING'
              ? '当前操作尚未执行。请确认下面的对象与数据范围。'
              : active.status === 'APPROVED'
                ? '审批已批准，后续执行结果请查看任务轨迹。'
                : '该审批已结束，此次操作不会执行。'
          }}</span>
        </div>
        <div class="approval-facts">
          <article>
            <span><FileText :size="16" />操作对象</span
            ><strong>{{ toolLabels[active.tool_request.tool_name] }}</strong
            ><code>{{ active.tool_request.action }}</code>
          </article>
          <article>
            <span><Users :size="16" />影响范围</span
            ><strong>{{
              active.tool_request.arguments.recipient_count
                ? active.tool_request.arguments.recipient_count + ' 名接收人'
                : '1 份共享文件'
            }}</strong
            ><small>仅本次活动</small>
          </article>
          <article>
            <span><ExternalLink :size="16" />信息来源</span
            ><strong>{{ trustLabels[active.tool_request.source_trust] }}</strong
            ><small>按来源信任级别审查</small>
          </article>
        </div>
        <h3>准备执行什么</h3>
        <dl class="detail-fields">
          <div v-for="(value, key) in active.tool_request.arguments" :key="key">
            <dt>{{ paramLabels[key] || key }}</dt>
            <dd>
              <pre>{{ display(value) }}</pre>
            </dd>
          </div>
        </dl>
        <h3>为什么需要确认</h3>
        <div v-for="r in active.reasons" :key="r.code" class="approval-reason">
          <Clock3 :size="18" />
          <div>
            <strong>{{ r.message }}</strong>
            <p v-if="r.field">
              {{ r.field }}：{{ display(r.observed)
              }}<span v-if="r.expected !== null"> · 自动执行阈值：{{ display(r.expected) }}</span>
            </p>
            <code>{{ r.code }}</code>
          </div>
        </div>
        <details>
          <summary>查看完整工具请求</summary>
          <pre class="json-preview">{{ display(active.tool_request) }}</pre>
        </details>
        <p class="helper">
          参数修改与重新校验接口尚待同学 A 实现，当前版本支持批准、拒绝和到期取消。
        </p>
        <p v-if="active.resolved_at" class="helper">处理时间：{{ dateTime(active.resolved_at) }}</p>
      </div>
      <div class="approval-actions">
        <RouterLink to="/trace" class="text-button" @click="viewTask"
          >查看任务轨迹<ArrowRight :size="14"
        /></RouterLink>
        <div v-if="active.status === 'PENDING'" class="row">
          <button class="button" :disabled="s.busy" @click="s.decide(active.approval_id, false)">
            <X :size="16" />拒绝操作</button
          ><button
            class="button primary"
            :disabled="s.busy"
            @click="s.decide(active.approval_id, true)"
          >
            <Check :size="16" />批准执行
          </button>
        </div>
      </div>
    </section>
  </div>
  <div v-else class="panel empty-state large-empty">
    <span class="empty-icon"><Inbox :size="32" :stroke-width="1.3" /></span>
    <h2>{{ tab === 'pending' ? '当前没有待审批操作' : '还没有审批历史' }}</h2>
    <p>
      {{
        tab === 'pending'
          ? '低风险操作会自动放行，高影响操作会出现在这里。'
          : '批准、拒绝和到期取消的结果会保留在这里。'
      }}
    </p>
    <RouterLink to="/" class="button primary"
      >{{ tab === 'pending' ? '创建一个人工确认场景' : '返回控制台'
      }}<ArrowRight :size="15" /></RouterLink
    ><span class="helper">演示：选择「人工确认」→ 启动任务 → 等待审批卡片出现。</span>
  </div>
</template>
