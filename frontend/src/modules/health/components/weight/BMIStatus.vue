<template>
  <div class="bmi-card" v-if="stats?.bmi">
    <div class="bmi-header">
      <span class="bmi-label">BMI</span>
      <span class="bmi-value">{{ stats.bmi }}</span>
    </div>
    <div class="bmi-status" :style="{ color: bmiColor }">
      {{ stats.bmi_status }}
    </div>
    <div class="bmi-bar">
      <div class="bmi-track">
        <div
          v-for="range in BMI_RANGES"
          :key="range.label"
          class="bmi-segment"
          :style="{ background: range.color, width: segmentWidth(range) }"
        />
      </div>
      <div class="bmi-indicator" :style="{ left: indicatorPos + '%' }">▼</div>
    </div>
    <div class="bmi-range-labels">
      <span
        v-for="r in BMI_RANGES"
        :key="r.label"
        class="bmi-label-item"
        :style="{ color: r.color, left: labelPos(r) + '%' }"
      >{{ r.label }}</span>
    </div>
    <div class="bmi-advice" v-if="adviceText">{{ adviceText }}</div>
  </div>
  <div class="bmi-card bmi-empty" v-else>
    <div class="bmi-label">BMI</div>
    <div class="bmi-value">--</div>
    <div class="bmi-sub">填写身体信息后计算</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BMI_RANGES } from '../../types/healthTypes'
import type { WeightStats } from '../../types/healthTypes'

const props = defineProps<{ stats: WeightStats | null }>()

const bmiColor = computed(() => {
  if (!props.stats?.bmi) return '#9CA3AF'
  for (const r of BMI_RANGES) {
    if ((props.stats?.bmi ?? 0) < r.max) return r.color
  }
  return '#EF4444'
})

const adviceText = computed(() => {
  if (!props.stats?.bmi) return ''
  for (const r of BMI_RANGES) {
    if ((props.stats?.bmi ?? 0) < r.max) return r.advice
  }
  return ''
})

const MAX_BMI = 35

const segmentWidth = (range: typeof BMI_RANGES[0]) => {
  const index = BMI_RANGES.indexOf(range)
  const prevMax = index > 0 ? BMI_RANGES[index - 1].max : 0
  const effectiveMax = range.max === Infinity ? MAX_BMI : range.max
  return ((effectiveMax - prevMax) / MAX_BMI * 100) + '%'
}

const labelPos = (range: typeof BMI_RANGES[0]) => {
  const index = BMI_RANGES.indexOf(range)
  const prevMax = index > 0 ? BMI_RANGES[index - 1].max : 0
  const effectiveMax = range.max === Infinity ? MAX_BMI : range.max
  const center = (prevMax + effectiveMax) / 2
  return Math.min((center / MAX_BMI) * 100, 100)
}

const indicatorPos = computed(() => {
  if (!props.stats?.bmi) return 0
  return Math.min((props.stats.bmi / MAX_BMI) * 100, 95)
})
</script>

<style scoped>
.bmi-card {
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 16px;
}
.bmi-header { display: flex; align-items: baseline; gap: 8px; }
.bmi-label { font-size: 13px; color: #6B7280; }
.bmi-value { font-size: 28px; font-weight: 700; color: #1F2937; }
.bmi-status { font-size: 16px; font-weight: 600; margin: 4px 0 12px; }
.bmi-bar { position: relative; margin: 8px 0 4px; }
.bmi-track { display: flex; height: 8px; border-radius: 4px; overflow: hidden; }
.bmi-segment { height: 100%; }
.bmi-indicator {
  position: absolute; top: -2px; font-size: 12px;
  transform: translateX(-50%); color: #374151;
}
.bmi-range-labels { position: relative; height: 14px; font-size: 10px; margin-top: 4px; }
.bmi-label-item { position: absolute; transform: translateX(-50%); white-space: nowrap; }
.bmi-advice { font-size: 13px; color: #6B7280; margin-top: 8px; }
.bmi-empty { text-align: center; padding: 24px; }
.bmi-sub { font-size: 12px; color: #9CA3AF; margin-top: 4px; }
</style>
