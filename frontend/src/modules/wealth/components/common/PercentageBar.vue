<template>
  <div class="pct-bar">
    <div class="pct-bar__fill" :style="{ width: pct + '%', background: color }" />
    <span v-if="showLabel" class="pct-bar__label">{{ pct }}%</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  percentage: number
  color?: string
  showLabel?: boolean
  height?: number
}>(), {
  color: '#409eff',
  showLabel: false,
  height: 8,
})

const pct = computed(() => Math.min(Math.max(props.percentage, 0), 100))
</script>

<style scoped>
.pct-bar {
  width: 100%;
  height: v-bind('height + "px"');
  background: var(--el-border-color-light);
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}
.pct-bar__fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}
.pct-bar__label {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
