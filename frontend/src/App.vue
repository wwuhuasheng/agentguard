<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ShieldCheck,
  LayoutDashboard,
  GitBranch,
  CircleCheck,
  History,
  ChartNoAxesCombined,
  ArrowUpRight,
  Play,
  CircleHelp,
  X,
  RotateCcw,
  Menu,
  Radio,
  ChevronRight,
} from 'lucide-vue-next'
import { useConsoleStore } from './stores/console'
import { scenarios } from './mock/scenarios'
import type { Scenario } from './types'
const s = useConsoleStore(),
  route = useRoute(),
  router = useRouter(),
  mobile = ref(false)
const replayDialog = ref<HTMLDialogElement>(),
  helpDialog = ref<HTMLDialogElement>(),
  resetDialog = ref<HTMLDialogElement>()
const nav = [
  { path: '/', label: '任务控制台', icon: LayoutDashboard },
  { path: '/trace', label: '执行轨迹', icon: GitBranch },
  { path: '/approvals', label: '人工审批', icon: CircleCheck },
  { path: '/incidents', label: '事件与恢复', icon: History },
  { path: '/evaluation', label: '评测看板', icon: ChartNoAxesCombined },
]
let clock: ReturnType<typeof setInterval>, poll: ReturnType<typeof setInterval>
onMounted(() => {
  void s.initialize()
  clock = setInterval(() => s.tick(), 250)
  poll = setInterval(() => {
    if (s.mode === 'live') void s.refresh()
  }, 4000)
})
onUnmounted(() => {
  clearInterval(clock)
  clearInterval(poll)
})
async function startReplay(id: Scenario) {
  replayDialog.value?.close()
  const t = await s.create(
    id,
    scenarios.find((x) => x.id === id)!.title + ' · 演示回放',
    '使用预置脱敏数据演示可信执行流程。',
    [],
    true
  )
  if (t) void router.push('/trace')
}
function resetDemo() {
  s.reset()
  resetDialog.value?.close()
}
const displayedUserName = computed(
  () => s.currentUser?.display_name || s.currentUser?.username || '未登录用户'
)
const displayedUserId = computed(() => s.currentUser?.username || '等待用户信息')
const userInitial = computed(() => displayedUserName.value.trim().charAt(0).toUpperCase() || '?')
</script>
<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ open: mobile }">
      <RouterLink to="/" class="brand" @click="mobile = false"
        ><span class="brand-icon"><ShieldCheck :size="25" :stroke-width="1.6" /></span
        ><span
          ><strong>御界 <span class="brand-dot">/</span> AgentGuard</strong
          ><small>可信执行守护系统</small></span
        ></RouterLink
      >
      <div class="workspace-label">WORKSPACE <span>01</span></div>
      <nav aria-label="主导航">
        <RouterLink
          v-for="n in nav"
          :key="n.path"
          :to="n.path"
          class="nav-item"
          :class="{ active: route.path === n.path }"
          @click="mobile = false"
          ><component :is="n.icon" :size="19" :stroke-width="1.7" /><span>{{ n.label }}</span
          ><b v-if="n.path === '/approvals' && s.pending.length" class="nav-count">{{
            s.pending.length
          }}</b
          ><ChevronRight v-else-if="route.path === n.path" :size="14" class="nav-arrow"
        /></RouterLink>
      </nav>
      <div class="sidebar-divider"></div>
      <span class="workspace-label">DEMONSTRATION</span>
      <button class="nav-item" :disabled="s.mode === 'live'" @click="replayDialog?.showModal()">
        <Play :size="18" /><span>演示回放</span><span class="keycap">DEMO</span>
      </button>
      <button class="nav-item" @click="helpDialog?.showModal()">
        <CircleHelp :size="18" /><span>连接与使用说明</span>
      </button>
      <div class="sidebar-bottom">
        <div class="boundary-card">
          <ShieldCheck :size="20" /><strong>让每一次执行有边界</strong>
          <p>权限可见 · 风险可控<br />操作可追踪 · 异常可恢复</p>
        </div>
        <div class="profile">
          <span class="avatar">{{ userInitial }}</span>
          <div><strong>{{ displayedUserName }}</strong><small>{{ displayedUserId }}</small></div>
        </div>
      </div>
    </aside>
    <button v-if="mobile" class="scrim" aria-label="关闭导航" @click="mobile = false"></button>
    <div class="main-shell">
      <header class="topbar">
        <div class="row">
          <button class="icon-button mobile-menu" aria-label="打开导航" @click="mobile = !mobile">
            <Menu :size="20" /></button
          ><span class="muted">工作空间</span><ChevronRight :size="14" /><span>{{
            route.meta.title
          }}</span>
        </div>
        <div class="row top-actions">
          <span class="mode-pill"
            ><Radio :size="13" />{{
              s.mode === 'mock'
                ? 'MOCK · 演示数据'
                : s.connected
                  ? 'LIVE · 已连接'
                  : 'LIVE · 未连接'
            }}</span
          ><button
            class="icon-button"
            aria-label="查看连接说明"
            title="连接说明"
            @click="helpDialog?.showModal()"
          >
            <CircleHelp :size="18" /></button
          ><span class="top-avatar">{{ userInitial }}</span>
        </div>
      </header>
      <main><RouterView /></main>
      <footer>
        <span>AGENTGUARD / TRUSTED EXECUTION</span
        ><span
          >{{ s.mode === 'mock' ? '本地模拟环境 · 无真实工具调用' : '真实接口模式 · 后端决策优先'
          }}<button v-if="s.mode === 'mock'" class="text-button" @click="resetDialog?.showModal()">
            <RotateCcw :size="12" />重置演示
          </button></span
        >
      </footer>
    </div>
    <Transition name="toast"
      ><div v-if="s.message" class="toast-message" role="status">
        <CircleCheck :size="18" />{{ s.message
        }}<button aria-label="关闭提示" @click="s.message = ''"><X :size="16" /></button></div
    ></Transition>
    <dialog ref="replayDialog" class="modal">
      <div class="row between">
        <span class="eyebrow">DEMO REPLAY</span
        ><button class="icon-button" aria-label="关闭" @click="replayDialog?.close()">
          <X :size="19" />
        </button>
      </div>
      <h2>选择一条演示流程</h2>
      <p class="muted">播放预置事件，审批步骤由你操作。无需连接后端。</p>
      <div class="replay-options">
        <button v-for="x in scenarios" :key="x.id" @click="startReplay(x.id)">
          <span class="mono">{{ x.index }}</span>
          <div>
            <strong>{{ x.title }}</strong
            ><small>{{ x.subtitle }}</small>
          </div>
          <ArrowUpRight :size="19" />
        </button>
      </div>
      <p class="small muted">恢复流程会先请求文件修改审批，批准后模拟连续失败和状态恢复。</p>
    </dialog>
    <dialog ref="helpDialog" class="modal">
      <div class="row between">
        <span class="eyebrow">CONNECTION GUIDE</span
        ><button class="icon-button" aria-label="关闭" @click="helpDialog?.close()">
          <X :size="19" />
        </button>
      </div>
      <h2>从演示到真实执行</h2>
      <p>
        当前数据源：<strong>{{ s.mode === 'mock' ? '本地 Mock' : '真实后端' }}</strong>
      </p>
      <ol class="guide-list">
        <li>
          <strong>现在就能演示</strong>
          <p>在任务控制台选择场景并启动，或从侧栏进入回放。所有示例使用脱敏数据。</p>
        </li>
        <li>
          <strong>与同学 A 联调</strong>
          <p>
            复制 .env.example 为 .env.local，设置 VITE_DATA_MODE=live 和
            VITE_API_BASE_URL，然后重启开发服务器。
          </p>
        </li>
        <li>
          <strong>确认接口契约</strong>
          <p>
            查看项目
            docs/INTEGRATION.md。任务、审批详情及恢复事件为待确认的适配对象，现有后端尚未实现这些
            HTTP 接口。
          </p>
        </li>
        <li>
          <strong>评测与文件边界</strong>
          <p>评测页是样例数据；附件仅展示本地文件名和大小，不解析文件内容或上传至服务器。</p>
        </li>
      </ol>
      <button class="button primary full" @click="helpDialog?.close()">知道了</button>
    </dialog>
    <dialog ref="resetDialog" class="modal compact">
      <span class="eyebrow">RESET DEMO</span>
      <h2>重置本地演示？</h2>
      <p class="muted">将清除当前演示任务、审批和回放进度，并恢复两条初始样例。</p>
      <div class="row end">
        <button class="button" @click="resetDialog?.close()">保留当前记录</button
        ><button
          class="button primary"
          @click="resetDemo"
        >
          确认重置
        </button>
      </div>
    </dialog>
  </div>
</template>
