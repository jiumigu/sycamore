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
  // 符号由模板按 showSign 统一渲染，这里只负责数值大小 + 千分位 + 脱敏
  // 取不到交回 formatAmount（它会给「—」）；本组件不兜 0，
  // 否则「没数据」会被说成「0 元」——本组件存在的意义正是把这两件事分开。
  if (props.value === null || props.value === undefined) return formatAmount(null)
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
