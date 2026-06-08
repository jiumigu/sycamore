<template>
  <div class="stats-footer" :class="{ 'stats-footer--collapsed': collapsed }">
    <div class="stats-footer__toggle" @click="collapsed = !collapsed">
      {{ collapsed ? '展开统计' : '收起统计' }}
      <el-icon :class="{ rotated: !collapsed }"><ArrowDown /></el-icon>
    </div>

    <div v-show="!collapsed" class="stats-footer__content">
      <div class="stats-footer__items">
        <div class="stats-footer__item">
          <span class="stats-footer__label">月结余</span>
          <span class="stats-footer__value" :class="(summary?.balance ?? 0) >= 0 ? 'text-income' : 'text-expense'">
            ¥{{ fmt(summary?.balance) }}
          </span>
        </div>
        <div class="stats-footer__item">
          <span class="stats-footer__label">日均支出</span>
          <span class="stats-footer__value text-expense">¥{{ fmt(summary?.avg_daily_expense) }}</span>
        </div>
        <div class="stats-footer__item">
          <span class="stats-footer__label">月总收入</span>
          <span class="stats-footer__value text-income">¥{{ fmt(summary?.total_income) }}</span>
        </div>
        <div class="stats-footer__item">
          <span class="stats-footer__label">月总支出</span>
          <span class="stats-footer__value text-expense">¥{{ fmt(summary?.total_expense) }}</span>
        </div>
        <div class="stats-footer__item">
          <span class="stats-footer__label">最高单日支出</span>
          <span class="stats-footer__value text-expense">¥{{ fmt(summary?.max_daily_expense) }}</span>
        </div>
        <div class="stats-footer__item">
          <span class="stats-footer__label">最高单日收入</span>
          <span class="stats-footer__value text-income">¥{{ fmt(summary?.max_daily_income) }}</span>
        </div>
      </div>

      <!-- 支出分类 TOP3 -->
      <div v-if="summary?.expense_top3?.length" class="stats-footer__top3">
        <span class="stats-footer__top3-label">支出TOP3:</span>
        <span v-for="(item, i) in summary.expense_top3" :key="i" class="stats-footer__top3-item">
          {{ item.category }} ¥{{ fmt(item.amount) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { formatAmount } from '@/shared/utils/format'
import type { MonthlySummary } from '../../types/wealthTypes'

defineProps<{
  summary: MonthlySummary | null
}>()

const collapsed = ref(false)

function fmt(val: number | undefined): string {
  if (val === undefined || val === null) return '0.00'
  return formatAmount(val)
}
</script>

<style scoped lang="scss">
.stats-footer {
  background: #fff;
  border-radius: 8px;
  margin-top: 12px;
  font-size: 13px;

  &__toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 6px;
    color: #999;
    font-size: 12px;
    cursor: pointer;
    user-select: none;

    &:hover { color: #409eff; }
  }

  &__content {
    padding: 0 16px 12px;
  }

  &__items {
    display: flex;
    flex-wrap: wrap;
    gap: 16px 24px;
  }

  &__item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 100px;
  }

  &__label {
    font-size: 11px;
    color: #999;
  }

  &__value {
    font-size: 16px;
    font-weight: 700;
  }

  &__top3 {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #eee;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
    color: #666;
    flex-wrap: wrap;
  }

  &__top3-label {
    font-weight: 600;
    color: #999;
  }

  &__top3-item {
    background: #f5f5f5;
    padding: 2px 8px;
    border-radius: 4px;
  }
}

.text-income { color: #389e0d; }
.text-expense { color: #cf1322; }
</style>
