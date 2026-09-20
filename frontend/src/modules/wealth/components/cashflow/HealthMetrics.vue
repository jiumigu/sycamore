<template>
  <div class="health-metrics">
    <div class="health-metrics__title">资产健康指标</div>
    <div v-if="!metrics" class="health-metrics__empty">暂无数据</div>
    <div v-else class="health-metrics__items">
      <div class="health-metrics__item" v-for="item in items" :key="item.key">
        <div class="health-metrics__item-top">
          <span class="health-metrics__item-label">{{ item.label }}</span>
          <span class="health-metrics__item-value" :class="item.status">
            {{ item.display }}
          </span>
        </div>
        <PercentageBar
          v-if="item.pct !== undefined"
          :percentage="item.pct ?? 0"
          :color="item.barColor"
        />
        <div v-if="item.hint" class="health-metrics__item-hint">{{ item.hint }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PercentageBar from '../common/PercentageBar.vue'
import { formatAmount } from '@/shared/utils/format'
import type { HealthMetrics } from '../../types/wealthTypes'

const props = defineProps<{
  metrics: HealthMetrics | null
}>()

const GOOD = '#67c23a'
const WARN = '#e6a23c'
const BAD = '#f56c6c'
const NEUTRAL = '#909399'

const items = computed(() => {
  if (!props.metrics) return []
  const m = props.metrics

  // 应急金以「月数」判定：目标月数由后端下发（emergency_months_target），
  // 不再使用写死的绝对金额阈值 —— 绝对阈值与支出水平脱钩。
  const target = m.emergency_months_target || 6
  const months = m.emergency_fund_months
  const monthsStatus = months === null
    ? 'normal'
    : months >= target ? 'good' : months >= target / 2 ? 'warn' : 'bad'
  const monthsColor = months === null
    ? NEUTRAL
    : months >= target ? GOOD : months >= target / 2 ? WARN : BAD
  const gap = m.emergency_gap

  return [
    {
      key: 'emergency',
      label: '应急金月数',
      display: months === null ? '数据不足' : `${months} 个月`,
      pct: months === null ? undefined : Math.min(100, (months / target) * 100),
      barColor: monthsColor,
      status: monthsStatus,
      hint: months === null
        ? '需近 3 个月支出记录'
        : (gap && gap > 0
            ? `目标 ${target} 个月，缺口 ¥${formatAmount(gap, 0)}`
            : `已达目标 ${target} 个月`),
    },
    {
      key: 'liquidity',
      label: '活期占比',
      display: m.liquidity_ratio + '%',
      pct: m.liquidity_ratio,
      barColor: m.liquidity_ratio > 30 ? WARN : m.liquidity_ratio > 10 ? GOOD : BAD,
      status: m.liquidity_ratio > 30 ? 'warn' : m.liquidity_ratio > 10 ? 'good' : 'bad',
    },
    {
      key: 'debt',
      label: '负债率',
      display: m.debt_ratio + '%',
      pct: m.debt_ratio,
      barColor: m.debt_ratio < 30 ? GOOD : m.debt_ratio < 50 ? WARN : BAD,
      status: m.debt_ratio < 30 ? 'good' : m.debt_ratio < 50 ? 'warn' : 'bad',
    },
    {
      key: 'pf',
      label: '公积金占比',
      display: m.provident_fund_ratio + '%',
      pct: m.provident_fund_ratio,
      barColor: m.provident_fund_ratio > 50 ? WARN : NEUTRAL,
      status: m.provident_fund_ratio > 50 ? 'warn' : 'normal',
    },
  ]
})
</script>

<style scoped>
.health-metrics__title {
  font-size: 15px; font-weight: 600; margin-bottom: 14px;
}
.health-metrics__items {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.health-metrics__item-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 13px;
}
.health-metrics__item-label {
  color: var(--el-text-color-regular);
}
.health-metrics__item-value { font-weight: 600; }
.health-metrics__item-value.good { color: #52c41a; }
.health-metrics__item-value.warn { color: #e6a23c; }
.health-metrics__item-value.bad { color: #f5222d; }
.health-metrics__item-value.normal { color: var(--el-text-color-primary); }
.health-metrics__item-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.health-metrics__empty {
  padding: 24px; text-align: center; color: var(--el-text-color-placeholder);
}
</style>
