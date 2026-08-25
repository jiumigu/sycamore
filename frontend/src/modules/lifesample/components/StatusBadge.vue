<template>
  <span class="status-badge" :class="`status-${props.status}`">
    {{ icon }} {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { StatusConfig } from '../types'
import type { SampleStatus } from '../types'

const props = defineProps<{
  status: SampleStatus
}>()

const config = computed(() => StatusConfig[props.status] || StatusConfig.collected)
const label = computed(() => config.value.label)
const icon = computed(() => config.value.icon)
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-collected {
  background: #f4f4f5;
  color: #909399;
}

.status-verified {
  background: #ecf5ff;
  color: #409eff;
}

.status-reviewed {
  background: #f0f9eb;
  color: #67c23a;
}
</style>
