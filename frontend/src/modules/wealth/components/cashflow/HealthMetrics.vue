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
          :percentage="item.pct"
          :color="item.pct > 50 ? '#67c23a' : item.pct > 20 ? '#e6a23c' : '#f56c6c'"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PercentageBar from '../common/PercentageBar.vue'
import type { HealthMetrics } from '../../types/wealthTypes'

const props = defineProps<{
  metrics: HealthMetrics | null
}>()

const items = computed(() => {
  if (!props.metrics) return []
  const m = props.metrics
  return [
    {
      key: 'emergency',
      label: '紧急备用金',
      display: '¥' + m.emergency_fund.toLocaleString(),
      status: m.emergency_fund > 10000 ? 'good' : m.emergency_fund > 5000 ? 'warn' : 'bad',
    },
    {
      key: 'liquidity',
      label: '活期占比',
      display: m.liquidity_ratio + '%',
      pct: m.liquidity_ratio,
      status: m.liquidity_ratio > 30 ? 'warn' : m.liquidity_ratio > 10 ? 'good' : 'bad',
    },
    {
      key: 'debt',
      label: '负债率',
      display: m.debt_ratio + '%',
      pct: m.debt_ratio,
      status: m.debt_ratio < 30 ? 'good' : m.debt_ratio < 50 ? 'warn' : 'bad',
    },
    {
      key: 'pf',
      label: '公积金占比',
      display: m.provident_fund_ratio + '%',
      pct: m.provident_fund_ratio,
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
.health-metrics__empty {
  padding: 24px; text-align: center; color: var(--el-text-color-placeholder);
}
</style>
