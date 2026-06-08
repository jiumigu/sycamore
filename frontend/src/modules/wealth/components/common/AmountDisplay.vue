<template>
  <span :class="['amount-display', colorClass]">
    <template v-if="showSign && (value ?? 0) !== 0">{{ (value ?? 0) > 0 ? '+' : '-' }}</template>
    {{ formatted }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'

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

const { maskAmount } = usePrivacyMask()

const formatted = computed(() => {
  if (props.value === null || props.value === undefined) return '0.00'
  const raw = Math.abs(props.value).toLocaleString('zh-CN', {
    minimumFractionDigits: props.precision,
    maximumFractionDigits: props.precision,
  })
  return maskAmount(raw)
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
