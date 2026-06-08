<template>
  <div class="module-bars">
    <div
      v-for="item in sortedModules"
      :key="item.module"
      class="bar-row"
      @click="$emit('view-module', item.module)"
    >
      <div class="bar-label">
        <span class="bar-dot" :style="{ background: item.color }"></span>
        <span class="bar-name">{{ item.label }}</span>
      </div>
      <div class="bar-track">
        <div
          class="bar-fill"
          :style="{
            width: maxPoints > 0 ? (item.points / maxPoints * 100) + '%' : '0%',
            background: item.color,
          }"
        ></div>
      </div>
      <div class="bar-value">
        <span class="bar-points">{{ item.points }}</span>
        <span class="bar-unit" v-if="showUnit">点</span>
        <span class="bar-percent" v-if="showPercent">({{ item.percent }}%)</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ModulePoint } from '../types/summaryTypes'

const props = withDefaults(defineProps<{
  modules: ModulePoint[]
  showUnit?: boolean
  showPercent?: boolean
}>(), {
  showUnit: true,
  showPercent: false,
})

defineEmits<{ 'view-module': [module: string] }>()

const maxPoints = computed(() => Math.max(...props.modules.map(m => m.points), 0))

const sortedModules = computed(() => [...props.modules].sort((a, b) => b.points - a.points))
</script>

<style scoped>
.module-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 6px;
  transition: background 0.2s;
}
.bar-row:hover {
  background: var(--el-fill-color-light);
}

.bar-label {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 72px;
  flex-shrink: 0;
}

.bar-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.bar-name {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.bar-track {
  flex: 1;
  height: 14px;
  background: var(--el-fill-color);
  border-radius: 7px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 7px;
  transition: width 0.6s ease;
  min-width: 2px;
}

.bar-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
  width: 80px;
  text-align: right;
  justify-content: flex-end;
  flex-shrink: 0;
}

.bar-points {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.bar-unit {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.bar-percent {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
