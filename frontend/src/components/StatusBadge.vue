<script setup lang="ts">
import { statusLabels } from '../labels'
defineProps<{ value: string }>()
</script>
<template>
  <span class="badge" :class="['badge-' + value.toLowerCase()]"
    ><span class="badge-dot"></span>{{ statusLabels[value] || value }}</span
  >
</template>
