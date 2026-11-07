<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowUpRight,
  Plus,
  Upload,
  FileText,
  X,
  ArrowRight,
  ShieldCheck,
  Layers,
  CircleCheck,
  Ban,
  Clock3,
  RefreshCw,
  ChevronRight,
} from 'lucide-vue-next'
import { useConsoleStore } from '../stores/console'
import { scenarios, permissions } from '../mock/scenarios'
import type { Scenario, FileMeta } from '../types'
import StatusBadge from '../components/StatusBadge.vue'
import { time } from '../labels'
const s = useConsoleStore(),
  router = useRouter(),
  scenario = ref<Scenario>('approval'),
  title = ref('社区公益活动安排'),
  description = ref('根据活动资料创建日程，向本次活动参与者发送通知，并更新共享排班文件。'),
  files = ref<FileMeta[]>([]),
  input = ref<HTMLInputElement>(),
  form = ref<HTMLElement>(),
  query = ref(''),
  filter = ref('all')
const rows = computed(() =>
  s.tasks.filter(
    (t) =>
      (filter.value === 'all' || t.status === filter.value) &&
      t.title.toLowerCase().includes(query.value.toLowerCase())
  )
)
const stats = computed(() => [
  { label: '任务总数', value: s.tasks.length, suffix: '本地会话', icon: Layers },
  {
    label: '已完成 / 已恢复',
    value: s.tasks.filter((t) => ['COMPLETED', 'RECOVERED'].includes(t.status)).length,
    suffix: '可追踪的执行结果',
    icon: CircleCheck,
  },
  {
    label: '风险阻断',
    value: s.tasks.filter((t) => t.status === 'BLOCKED').length,
    suffix: '工具执行前拦截',
    icon: Ban,
  },
  { label: '待人工审批', value: s.pending.length, suffix: '控制权始终在你', icon: Clock3 },
])
const recent = computed(() =>
  s.tasks
    .flatMap((t) => t.events.map((e) => ({ e, title: t.title })))
    .sort((a, b) => b.e.created_at.localeCompare(a.e.created_at))
    .slice(0, 4)
)
async function submit() {
  if (!title.value.trim() || !description.value.trim())
    return s.notify('请填写任务名称和任务描述。')
  const t = await s.create(
    scenario.value,
    title.value.trim(),
    description.value.trim(),
    files.value
  )
  if (t) void router.push('/trace')
}
function addFiles(e: Event) {
  const list = (e.target as HTMLInputElement).files
  if (!list) return
  for (const f of list) {
    if (f.size > 10 * 1024 * 1024) {
      s.notify('单个附件不能超过 10 MB')
      continue
    }
    if (files.value.length >= 5) {
      s.notify('最多添加 5 个附件')
      break
    }
    if (!files.value.some((x) => x.name === f.name && x.size === f.size))
      files.value.push({ name: f.name, size: f.size, type: f.type })
  }
  ;(e.target as HTMLInputElement).value = ''
}
function openTask(id: string) {
  s.select(id)
  void router.push('/trace')
}
function focusForm() {
  form.value?.scrollIntoView({behavior:'smooth'})
  input.value?.focus()
}
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">WORKSPACE / OVERVIEW</span>
      <h1>任务控制台<span class="heading-dot">.</span></h1>
      <p>从授权到执行，每一步都清晰可见。</p>
    </div>
    <button
      class="button primary"
      @click="focusForm"
    >
      <Plus :size="16" />新建任务
    </button>
  </div>
  <section class="hero">
    <div>
      <span class="hero-kicker"><ShieldCheck :size="14" />TRUST IS A BOUNDARY</span>
      <h2>把权限交给 Agent，<br />把控制权留给人。</h2>
      <p>低风险自动执行，高风险由你确认，越权请求即时阻断。</p>
    </div>
    <div class="hero-visual" aria-hidden="true">
      <div class="orbit orbit-one"></div>
      <div class="orbit orbit-two"></div>
      <div class="hero-shield"><ShieldCheck :size="55" :stroke-width="1" /></div>
      <span class="orbit-label one">AGENT</span><span class="orbit-label two">POLICY</span
      ><span class="orbit-label three">TOOL</span>
    </div>
    <div class="hero-index">
      <span>01 — 03</span>
      <p>ALLOW<br />CONFIRM<br />BLOCK</p>
      <ArrowUpRight :size="23" />
    </div>
  </section>
  <div class="stats-grid">
    <article v-for="x in stats" :key="x.label" class="stat-card">
      <div class="row between">
        <span>{{ x.label }}</span
        ><component :is="x.icon" :size="17" />
      </div>
      <strong>{{ String(x.value).padStart(2, '0') }}</strong
      ><small>{{ x.suffix }}</small>
    </article>
  </div>
  <div class="dashboard-grid">
    <section ref="form" class="panel task-form">
      <div class="panel-heading">
        <div>
          <h2>创建执行任务</h2>
          <p>选择场景，体验可信执行闭环</p>
        </div>
        <span class="section-number">01 / CREATE</span>
      </div>
      <form @submit.prevent="submit">
        <label class="field-label" for="task-name">任务名称 <span>*</span></label
        ><input
          id="task-name"
          ref="input"
          v-model="title"
          maxlength="80"
          required
          placeholder="给任务起个名字"
        /><label class="field-label" for="task-description"
          >你希望 Agent 做什么 <span>*</span></label
        ><textarea
          id="task-description"
          v-model="description"
          maxlength="2000"
          required
          rows="3"
          placeholder="描述任务目标与可使用的数据范围"
        ></textarea
        ><template v-if="s.mode === 'mock'"
          ><div class="row between field-label">
            <span>演示场景</span><span class="muted small">由预置事件驱动</span>
          </div>
          <div class="scenario-grid">
            <button
              v-for="x in scenarios"
              :key="x.id"
              type="button"
              :class="{ selected: scenario === x.id }"
              @click="scenario = x.id"
            >
              <span class="row between"
                ><b>{{ x.title }}</b
                ><span class="radio-mark"></span></span
              ><small>{{ x.subtitle }}</small>
            </button>
          </div></template
        ><label class="upload-box" :class="{ disabled: s.mode === 'live' }"
          ><Upload :size="21" /><span
            ><strong>选择活动资料</strong><small>PDF / CSV / TXT · 每个不超过 10 MB</small></span
          ><Plus :size="17" /><input
            type="file"
            multiple
            accept=".pdf,.csv,.txt,.md,.xlsx"
            :disabled="s.mode === 'live'"
            @change="addFiles"
        /></label>
        <p class="helper">
          {{
            s.mode === 'mock'
              ? '附件仅记录文件名和大小；本演示使用预置资料，不读取附件内容。'
              : '文件上传接口尚未确认，真实模式暂不接收附件。'
          }}
        </p>
        <div v-if="files.length" class="file-list">
          <div v-for="(f, i) in files" :key="f.name">
            <FileText :size="15" /><span>{{ f.name }}</span
            ><small>{{ (f.size / 1024).toFixed(1) }} KB</small
            ><button
              type="button"
              class="icon-button"
              :aria-label="'移除 ' + f.name"
              @click="files.splice(i, 1)"
            >
              <X :size="14" />
            </button>
          </div>
        </div>
        <details class="permission-details">
          <summary><ShieldCheck :size="14" />本次演示的授权范围<ChevronRight :size="14" /></summary>
          <ul>
            <li v-for="p in permissions" :key="p">{{ p }}</li>
            <li>禁止删除原文件，禁止外发敏感字段</li>
          </ul>
        </details>
        <div class="form-bottom">
          <span><ShieldCheck :size="14" />所有工具请求均经过策略检查</span
          ><button class="button primary" type="submit" :disabled="s.busy">
            {{ s.busy ? '正在创建…' : s.mode === 'mock' ? '启动模拟任务' : '提交到后端'
            }}<ArrowRight :size="16" />
          </button>
        </div>
      </form>
    </section>
    <aside class="dashboard-side">
      <section class="panel">
        <div class="panel-heading">
          <h2>可信执行路径</h2>
          <span class="section-number">FLOW</span>
        </div>
        <div class="decision-flow">
          <article>
            <span class="flow-icon"><CircleCheck :size="19" /></span>
            <div><strong>符合授权，自动放行</strong><small>低风险任务保持流畅</small></div>
            <code>ALLOW</code>
          </article>
          <article>
            <span class="flow-icon"><Clock3 :size="19" /></span>
            <div><strong>影响较大，等待确认</strong><small>执行前看清操作范围</small></div>
            <code>CONFIRM</code>
          </article>
          <article>
            <span class="flow-icon dark"><Ban :size="19" /></span>
            <div><strong>越过边界，即时阻断</strong><small>危险操作不进入工具</small></div>
            <code>BLOCK</code>
          </article>
        </div>
        <div class="info-strip">
          {{
            s.mode === 'mock'
              ? '当前为前端模拟环境，不调用真实 Agent 或外部工具。'
              : '已选择真实后端模式，执行结果由后端提供。'
          }}
        </div>
      </section>
      <section class="panel recent-panel">
        <div class="panel-heading">
          <h2>最近动态</h2>
          <RouterLink to="/trace" class="icon-button" aria-label="查看执行轨迹"
            ><ArrowUpRight :size="18"
          /></RouterLink>
        </div>
        <div v-for="{ e, title: t } in recent" :key="e.event_id" class="activity-item">
          <span class="activity-dot"></span>
          <div>
            <strong>{{
              e.event_type === 'POLICY_DECISION'
                ? e.payload.decision === 'BLOCK'
                  ? '风险请求已阻断'
                  : '策略检查已完成'
                : e.event_type === 'TOOL_EXECUTED'
                  ? '工具执行已完成'
                  : '任务状态已更新'
            }}</strong
            ><small>{{ t }}</small>
          </div>
          <time>{{ time(e.created_at) }}</time>
        </div>
        <p v-if="!recent.length" class="empty-inline">暂无执行事件</p>
      </section>
    </aside>
  </div>
  <section class="panel task-list">
    <div class="panel-heading">
      <div class="row">
        <h2>任务记录</h2>
        <span class="count-tag">{{ s.tasks.length }}</span>
      </div>
      <div class="table-controls">
        <input
          v-model="query"
          class="search"
          placeholder="搜索任务…"
          aria-label="搜索任务"
        /><select v-model="filter" aria-label="筛选任务状态">
          <option value="all">全部状态</option>
          <option value="WAITING_APPROVAL">等待审批</option>
          <option value="COMPLETED">已完成</option>
          <option value="BLOCKED">已阻断</option>
          <option value="RECOVERED">已恢复</option></select
        ><button
          v-if="s.mode === 'live'"
          class="icon-button"
          aria-label="刷新任务"
          @click="s.refresh()"
        >
          <RefreshCw :size="17" />
        </button>
      </div>
    </div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>任务名称</th>
            <th>场景</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>事件</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in rows" :key="t.task_id">
            <td>
              <button class="task-name" @click="openTask(t.task_id)">
                <FileText :size="17" /><span
                  >{{ t.title
                  }}<small>{{ t.task_id.slice(0, 8) }} <b v-if="t.replay">· 回放</b></small></span
                >
              </button>
            </td>
            <td>{{ scenarios.find((x) => x.id === t.scenario)?.title || '真实任务' }}</td>
            <td><StatusBadge :value="t.status" /></td>
            <td class="mono muted">{{ time(t.created_at) }}</td>
            <td class="mono">{{ t.events.length }}</td>
            <td>
              <button class="text-button" @click="openTask(t.task_id)">
                查看<ArrowUpRight :size="14" />
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="6" class="empty-inline">没有匹配的任务，请创建任务或调整筛选条件。</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
