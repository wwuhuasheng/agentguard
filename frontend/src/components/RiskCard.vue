<script setup lang="ts">
import type { AuditEvent } from '../types'
import StatusBadge from './StatusBadge.vue'
import { display, trustLabels, toolLabels } from '../labels'
defineProps<{ event: AuditEvent }>()
</script>
<template>
  <div class="risk-card">
    <div class="row between">
      <span class="eyebrow">DECISION EVIDENCE</span
      ><StatusBadge :value="event.payload.decision || 'BLOCK'" />
    </div>
    <h3>
      {{
        event.payload.decision === 'BLOCK'
          ? '操作已在工具执行前阻断'
          : event.payload.decision === 'CONFIRM'
            ? '操作正在等待你的授权'
            : '操作符合当前授权范围'
      }}
    </h3>
    <p class="muted">{{ event.payload.reasons?.[0]?.message || '后端未提供风险说明' }}</p>
    <dl v-if="event.payload.tool_request" class="evidence-meta">
      <div>
        <dt>执行工具</dt>
        <dd>
          {{
            toolLabels[event.payload.tool_request.tool_name] || event.payload.tool_request.tool_name
          }}
          <code>{{ event.payload.tool_request.action }}</code>
        </dd>
      </div>
      <div>
        <dt>信息来源</dt>
        <dd>{{ trustLabels[event.payload.tool_request.source_trust] }}</dd>
      </div>
      <div>
        <dt>接收对象 / 路径</dt>
        <dd>
          {{
            display(
              event.payload.tool_request.arguments.recipient ||
                event.payload.tool_request.arguments.path ||
                event.payload.tool_request.arguments.title
            )
          }}
        </dd>
      </div>
    </dl>
    <div v-else class="notice">此事件未携带工具上下文，需由后端补充 tool_request。</div>
    <div class="reason-list">
      <article v-for="r in event.payload.reasons" :key="r.code">
        <div class="row between">
          <code>{{ r.code }}</code
          ><span class="small muted">{{ r.level }}</span>
        </div>
        <p>{{ r.message }}</p>
        <div v-if="r.field" class="comparison">
          <span>{{ r.field }}</span>
          <div>
            <small>请求值</small>
            <pre>{{ display(r.observed) }}</pre>
          </div>
          <div>
            <small>授权范围 / 阈值</small>
            <pre>{{ display(r.expected) }}</pre>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>
