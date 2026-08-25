<template>
  <span class="relevance-badge" :class="`relevance-${props.relevance}`">
    {{ icon }} {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RelevanceConfig } from '../types'
import type { SampleRelevance } from '../types'

const props = defineProps<{
  relevance: SampleRelevance
}>()

const config = computed(() => RelevanceConfig[props.relevance] || RelevanceConfig.knowledge)
const label = computed(() => config.value.label)
const icon = computed(() => config.value.icon)
</script>

<style scoped>
.relevance-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.relevance-high {
  background: #fdf6ec;
  color: #e6a23c;
}

.relevance-reference {
  background: #ecf5ff;
  color: #409eff;
}

.relevance-knowledge {
  background: #f4f4f5;
  color: #909399;
}
</style>
