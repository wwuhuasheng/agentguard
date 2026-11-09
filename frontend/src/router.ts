import { createRouter, createWebHashHistory } from 'vue-router'
import TaskConsole from './views/TaskConsole.vue'
import TraceTimeline from './views/TraceTimeline.vue'
import ApprovalCenter from './views/ApprovalCenter.vue'
import IncidentDetail from './views/IncidentDetail.vue'
import EvaluationBoard from './views/EvaluationBoard.vue'
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: TaskConsole, meta: { title: '任务控制台', en: 'WORKSPACE' } },
    {
      path: '/trace',
      component: TraceTimeline,
      meta: { title: '执行轨迹', en: 'EXECUTION TRACE' },
    },
    {
      path: '/approvals',
      component: ApprovalCenter,
      meta: { title: '人工审批', en: 'HUMAN IN THE LOOP' },
    },
    {
      path: '/incidents',
      component: IncidentDetail,
      meta: { title: '事件与恢复', en: 'INCIDENT & RECOVERY' },
    },
    {
      path: '/evaluation',
      component: EvaluationBoard,
      meta: { title: '评测看板', en: 'EVALUATION' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
