<script setup lang="ts">
import { computed, ref } from 'vue'
import { BarChart3, FlaskConical, Download, ArrowUpRight, Search } from 'lucide-vue-next'
import { evaluationSamples } from '../mock/scenarios'
import StatusBadge from '../components/StatusBadge.vue'
const samples = evaluationSamples(),
  category = ref('全部类别'),
  result = ref('all'),
  query = ref(''),
  page = ref(1)
const categories = ['全部类别', '正常任务', '外部诱导', '越权调用', '参数异常', '故障恢复']
const filtered = computed(() =>
  samples.filter(
    (x) =>
      (category.value === '全部类别' || x.category === category.value) &&
      (result.value === 'all' || (result.value === 'pass') === x.success) &&
      x.id.toLowerCase().includes(query.value.toLowerCase())
  )
)
const rows = computed(() => filtered.value.slice((page.value - 1) * 10, page.value * 10)),
  pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / 10)))
const normal = samples.filter((x) => x.category === '正常任务'),
  risk = samples.filter((x) => !['正常任务', '故障恢复'].includes(x.category)),
  recovery = samples.filter((x) => x.category === '故障恢复')
function pct(n: number, d: number) {
  return d ? ((n / d) * 100).toFixed(1) : '0.0'
}
const metrics = [
  {
    label: '风险阻断率',
    value: pct(risk.filter((x) => x.success).length, risk.length),
    detail: `${risk.filter((x) => x.success).length} / ${risk.length} 条风险样例被正确阻断`,
    formula: '正确阻断的风险样例 / 风险样例总数',
  },
  {
    label: '正常任务成功率',
    value: pct(normal.filter((x) => x.success).length, normal.length),
    detail: `${normal.filter((x) => x.success).length} / ${normal.length} 条正常任务完成`,
    formula: '成功完成的正常样例 / 正常样例总数',
  },
  {
    label: '误报率',
    value: pct(normal.filter((x) => x.actual === 'BLOCK').length, normal.length),
    detail: '正常任务被错误阻断的比例',
    formula: '错误阻断的正常样例 / 正常样例总数',
  },
  {
    label: '恢复成功率',
    value: pct(recovery.filter((x) => x.success).length, recovery.length),
    detail: `${recovery.filter((x) => x.success).length} / ${recovery.length} 条故障样例恢复`,
    formula: '成功恢复样例 / 故障样例总数',
  },
]
const groups = [
  {
    name: '仅系统提示词',
    value: Number(pct(risk.filter((x) => x.baselinePrompt).length, risk.length)),
    note: '提示词约束',
    style: 'light',
  },
  {
    name: '提示词 + 敏感词',
    value: Number(pct(risk.filter((x) => x.baselineKeyword).length, risk.length)),
    note: '增加关键词检测',
    style: 'medium',
  },
  {
    name: '御界完整方案',
    value: Number(metrics[0]!.value),
    note: '来源 + 策略 + 网关 + 审批',
    style: 'dark',
  },
]
function change() {
  page.value = 1
}
function exportData() {
  const blob = new Blob(
    [JSON.stringify({ source: 'SYNTHETIC_DEMO_NOT_REAL_EVALUATION', metrics, samples }, null, 2)],
    { type: 'application/json' }
  )
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'agentguard-DEMO-evaluation.json'
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>
<template>
  <div class="page-heading">
    <div>
      <span class="eyebrow">MEASURE / EVALUATION BOARD</span>
      <h1>用数据，验证可信执行<span class="heading-dot">.</span></h1>
      <p>分别观察安全性与可用性，不以阻断率替代任务完成率。</p>
    </div>
    <button class="button" @click="exportData"><Download :size="16" />导出样例数据</button>
  </div>
  <div class="evaluation-notice">
    <FlaskConical :size="21" />
    <div>
      <strong>演示样例 · 非真实评测结论</strong>
      <p>以下 60 条为前端构造的数据，用于验证指标计算和看板交互。正式数据需由成员 C 提供。</p>
    </div>
    <span class="demo-label">SYNTHETIC DATA</span>
  </div>
  <div class="stats-grid eval-stats">
    <article v-for="m in metrics" :key="m.label" class="stat-card" :title="m.formula">
      <div class="row between">
        <span>{{ m.label }}</span
        ><ArrowUpRight :size="16" />
      </div>
      <strong>{{ m.value }}<em>%</em></strong
      ><small>{{ m.detail }}</small
      ><span class="metric-formula">{{ m.formula }}</span>
    </article>
  </div>
  <div class="evaluation-grid">
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>方案对照 · 风险阻断率</h2>
          <p>相同样例，比较三组演示结果</p>
        </div>
        <span class="demo-label">DEMO</span>
      </div>
      <div
        class="comparison-chart"
        role="img"
        :aria-label="groups.map((g) => g.name + ' ' + g.value + '%').join('，')"
      >
        <div class="chart-axis">
          <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
        </div>
        <div v-for="g in groups" :key="g.name" class="chart-row">
          <div>
            <strong>{{ g.name }}</strong
            ><small>{{ g.note }}</small>
          </div>
          <div class="bar-track">
            <span class="bar" :class="g.style" :style="{ width: g.value + '%' }"></span>
          </div>
          <b class="mono">{{ g.value.toFixed(1) }}%</b>
        </div>
      </div>
      <div class="info-strip">全部结果由演示样例计算；不能用于比赛材料中的实际效果声明。</div>
    </section>
    <section class="panel">
      <div class="panel-heading">
        <h2>样例类别分布</h2>
        <span class="section-number">60 CASES</span>
      </div>
      <div class="distribution">
        <article v-for="(c, i) in categories.slice(1)" :key="c">
          <span
            class="distribution-block"
            :style="{ background: ['#242424', '#666666', '#969696', '#bcbcbc', '#e1e1e1'][i] }"
          ></span
          ><span>{{ c }}</span>
          <div class="distribution-track">
            <span
              :style="{ width: (samples.filter((x) => x.category === c).length / 20) * 100 + '%' }"
            ></span>
          </div>
          <strong>{{ samples.filter((x) => x.category === c).length }}</strong>
        </article>
      </div>
    </section>
  </div>
  <section class="panel">
    <div class="panel-heading">
      <div class="row">
        <h2>样例明细</h2>
        <span class="count-tag">{{ filtered.length }}</span>
      </div>
      <div class="table-controls">
        <div class="search-wrap">
          <Search :size="14" /><input
            v-model="query"
            class="search"
            placeholder="搜索样例 ID"
            aria-label="搜索样例"
            @input="change"
          />
        </div>
        <select v-model="category" aria-label="筛选样例类别" @change="change">
          <option v-for="c in categories" :key="c">{{ c }}</option></select
        ><select v-model="result" aria-label="筛选样例结果" @change="change">
          <option value="all">全部结果</option>
          <option value="pass">符合预期</option>
          <option value="fail">未达预期</option>
        </select>
      </div>
    </div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th>样例 ID</th>
            <th>类别</th>
            <th>预期结果</th>
            <th>实际结果</th>
            <th>是否符合预期</th>
            <th>数据来源</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="x in rows" :key="x.id">
            <td class="mono">{{ x.id }}</td>
            <td>{{ x.category }}</td>
            <td><StatusBadge :value="x.expected" /></td>
            <td><StatusBadge :value="x.actual" /></td>
            <td>
              <span :class="x.success ? 'result-pass' : 'result-fail'">{{
                x.success ? '✓ 符合预期' : '× 未达预期'
              }}</span>
            </td>
            <td class="muted small">前端演示样例</td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="6" class="empty-inline">没有匹配的样例</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="pagination">
      <span>共 {{ filtered.length }} 条 · 每页 10 条</span>
      <div class="row">
        <button class="button small-button" :disabled="page <= 1" @click="page--">上一页</button
        ><span class="mono">{{ page }} / {{ pages }}</span
        ><button class="button small-button" :disabled="page >= pages" @click="page++">
          下一页
        </button>
      </div>
    </div>
  </section>
</template>
