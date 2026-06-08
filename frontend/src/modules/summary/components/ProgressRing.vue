<template>
  <div class="progress-ring" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" viewBox="0 0 120 120">
      <!-- 背景圈 -->
      <circle
        cx="60" cy="60" r="52"
        fill="none"
        :stroke="bgColor"
        :stroke-width="strokeWidth"
      />
      <!-- 进度圈 -->
      <circle
        cx="60" cy="60" r="52"
        fill="none"
        :stroke="progressColor"
        :stroke-width="strokeWidth"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
        stroke-linecap="round"
        transform="rotate(-90, 60, 60)"
        class="progress-arc"
      />
    </svg>
    <div class="ring-center">
      <div class="ring-value" :style="{ color: textColor }">{{ displayValue }}</div>
      <div class="ring-label">{{ label }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  value: number
  max: number
  size?: number
  strokeWidth?: number
  label?: string
  color?: string
  bgColor?: string
}>(), {
  size: 160,
  strokeWidth: 8,
  label: '',
  color: '#10B981',
  bgColor: '#E5E7EB',
})

const circumference = 2 * Math.PI * 52

const percent = computed(() => Math.min(props.value / props.max, 1))
const dashOffset = computed(() => circumference * (1 - percent.value))
const progressColor = computed(() => {
  const p = percent.value
  if (p >= 0.66) return '#10B981'
  if (p >= 0.33) return '#F59E0B'
  return '#EF4444'
})
const textColor = computed(() => progressColor.value)
const displayValue = computed(() => `${(percent.value * 100).toFixed(1)}%`)
</script>

<style scoped>
.progress-ring {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.progress-arc {
  transition: stroke-dashoffset 0.8s ease;
}

.ring-center {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.ring-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
}

.ring-label {
  font-size: 11px;
  color: #6B7280;
  margin-top: 4px;
}
</style>
