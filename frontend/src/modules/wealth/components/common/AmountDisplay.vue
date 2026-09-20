<template>
  <span :class="['amount-display', colorClass]">
    <template v-if="showSign && (value ?? 0) !== 0">{{ (value ?? 0) > 0 ? '+' : '-' }}</template>
    {{ formatted }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatAmount } from '@/shared/utils/format'

const props = withDefaults(defineProps<{
  value: number | null | undefined
  showSign?: boolean
  colorize?: boolean
  precision?: number
}>(), {
  showSign: false,
  colorize: true,
  precision: 2,
})

const formatted = computed(() => {
  if (props.value === null || props.value === undefined) return '0.00'
  // 符号由模板按 showSign 统一渲染，这里只负责数值大小 + 千分位 + 脱敏
  return formatAmount(Math.abs(props.value), props.precision)
})

const colorClass = computed(() => {
  if (!props.colorize || !props.value) return ''
  if (props.value > 0) return 'amount-income'
  if (props.value < 0) return 'amount-expense'
  return ''
})
</script>

<style scoped>
.amount-income { color: #52c41a; }
.amount-expense { color: #f5222d; }
</style>
