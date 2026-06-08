<template>
  <div class="review-header">
    <div class="review-header__nav">
      <el-button text @click="$emit('prevMonth')">
        <el-icon><ArrowLeft /></el-icon>
      </el-button>
      <span class="review-header__ym">{{ year }}年{{ month }}月</span>
      <el-button text @click="$emit('nextMonth')">
        <el-icon><ArrowRight /></el-icon>
      </el-button>
      <el-button size="small" class="review-header__today" @click="$emit('today')">今天</el-button>
    </div>

    <div class="review-header__cards">
      <el-row :gutter="12">
        <el-col :xs="12" :sm="6" v-for="card in cards" :key="card.key">
          <el-card shadow="never" class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" :style="{ background: card.bg }">
                <el-icon :color="card.color"><component :is="card.icon" /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value" :class="card.valueClass">
                  <template v-if="card.unit === '%'">{{ card.displayValue }}</template>
                  <template v-else>￥{{ fmt(card.value) }}</template>
                </div>
                <div class="stat-label">
                  {{ card.label }}
                  <span v-if="card.change !== null" :class="card.changeClass">
                    {{ card.change > 0 ? '↑' : '↓' }}{{ Math.abs(card.change) }}%
                  </span>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatAmount } from '@/shared/utils/format'
import { ArrowLeft, ArrowRight, TrendCharts, Bottom, Wallet, DataAnalysis } from '@element-plus/icons-vue'
import type { MonthlyReview } from '../../types/wealthTypes'

const props = defineProps<{
  review: MonthlyReview | null
  loading?: boolean
}>()

defineEmits<{
  prevMonth: []
  nextMonth: []
  today: []
}>()

const year = computed(() => props.review?.year ?? new Date().getFullYear())
const month = computed(() => props.review?.month ?? new Date().getMonth() + 1)

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  return formatAmount(v)
}

const cards = computed(() => {
  const r = props.review
  return [
    {
      key: 'income',
      label: '本月收入',
      value: r?.income ?? 0,
      change: r?.mom_change?.income ?? null,
      valueClass: 'text-income',
      changeClass: 'text-income',
      icon: TrendCharts,
      bg: '#e6f7ff', color: '#1890ff',
    },
    {
      key: 'expense',
      label: '本月支出',
      value: r?.expense ?? 0,
      change: r?.mom_change?.expense ?? null,
      valueClass: 'text-expense',
      changeClass: 'text-expense',
      icon: Bottom,
      bg: '#fff1f0', color: '#f5222d',
    },
    {
      key: 'balance',
      label: '本月结余',
      value: r?.balance ?? 0,
      change: r?.mom_change?.balance ?? null,
      valueClass: (r?.balance ?? 0) >= 0 ? 'text-income' : 'text-expense',
      changeClass: 'text-info',
      icon: Wallet,
      bg: '#f6ffed', color: '#52c41a',
    },
    {
      key: 'savings',
      label: '结余率',
      value: r?.savings_rate ?? 0,
      displayValue: (r?.savings_rate ?? 0).toFixed(1) + '%',
      unit: '%',
      change: null,
      valueClass: 'text-info',
      changeClass: '',
      icon: DataAnalysis,
      bg: '#fff7e6', color: '#fa8c16',
    },
  ]
})
</script>

<style scoped>
.review-header__nav {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.review-header__ym {
  font-size: 18px;
  font-weight: 600;
  min-width: 100px;
  text-align: center;
}
.review-header__today { margin-left: 4px; }

.stat-card :deep(.el-card__body) { padding: 14px; }
.stat-content {
  display: flex;
  align-items: center;
  gap: 12px;
}
.stat-icon {
  width: 40px; height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-info .stat-value {
  font-size: 18px; font-weight: 600; line-height: 1; margin-bottom: 3px;
}
.stat-label {
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.text-income { color: #52c41a; }
.text-expense { color: #f5222d; }
.text-info { color: #1890ff; }
</style>
