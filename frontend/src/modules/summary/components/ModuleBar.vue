<template>
  <!--
    ⚠️ 已退役（v3.62.43）：总分解散后「各模块贡献占比」不再有意义，
        总览页改用 `CoverageTable.vue`（覆盖率 + 强度）。
        文件保留未删（删文件由人执行），所以这里仍需跟类型保持同步。
        `percent` 字段（占全年的比例）已随总分一起移除 —— 别再往 ModulePoint 上补字段。
  -->
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
        <span
          v-if="zeroReasonText(item.zero_reason)"
          class="bar-flag"
          :title="zeroReasonHint(item.zero_reason)"
        >{{ zeroReasonText(item.zero_reason) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ModulePoint } from '../types/summaryTypes'
import { zeroReasonText, zeroReasonHint } from '../constants/zeroReason'

const props = withDefaults(defineProps<{
  modules: ModulePoint[]
  showUnit?: boolean
}>(), {
  showUnit: true,
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
  min-width: 80px;
  text-align: right;
  justify-content: flex-end;
  flex-shrink: 0;
}

/* 原因码标记：说明「0 分」是取不到还是净流出，而不是假装它真是 0 */
.bar-flag {
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 3px;
  background: var(--el-fill-color);
  font-size: 10px;
  line-height: 15px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  align-self: center;
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
