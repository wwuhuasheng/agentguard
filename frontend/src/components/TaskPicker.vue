<script setup lang="ts">
import { useConsoleStore } from '../stores/console'
const s = useConsoleStore()
</script>
<template>
  <label class="task-picker"
    ><span>当前任务</span
    ><select :value="s.selectedId" @change="s.select(($event.target as HTMLSelectElement).value)">
      <option v-if="!s.tasks.length" value="">暂无任务</option>
      <option v-for="t in s.tasks" :key="t.task_id" :value="t.task_id">
        {{ t.title }} · {{ t.task_id.slice(0, 6) }}
      </option>
    </select></label
  >
</template>
