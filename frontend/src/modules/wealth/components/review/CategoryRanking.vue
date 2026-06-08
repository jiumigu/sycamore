<template>
  <div class="cat-ranking">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="支出分类TOP5" name="expense">
        <div v-if="expenseData.length" class="cat-ranking__list">
          <div v-for="(item, i) in expenseData" :key="i" class="cat-ranking__item">
            <div class="cat-ranking__top">
              <span class="cat-ranking__name">{{ item.category }}</span>
              <span class="cat-ranking__amt text-expense">￥{{ fmt(item.amount) }}</span>
            </div>
            <div class="cat-ranking__bar">
              <PercentageBar :percentage="item.percentage" color="#f5222d" />
            </div>
            <span class="cat-ranking__pct">{{ item.percentage }}%</span>
          </div>
        </div>
        <div v-else class="cat-ranking__empty">暂无支出数据</div>
      </el-tab-pane>
      <el-tab-pane label="收入来源TOP5" name="income">
        <div v-if="incomeData.length" class="cat-ranking__list">
          <div v-for="(item, i) in incomeData" :key="i" class="cat-ranking__item">
            <div class="cat-ranking__top">
              <span class="cat-ranking__name">{{ item.category }}</span>
              <span class="cat-ranking__amt text-income">￥{{ fmt(item.amount) }}</span>
            </div>
            <div class="cat-ranking__bar">
              <PercentageBar :percentage="item.percentage" color="#52c41a" />
            </div>
            <span class="cat-ranking__pct">{{ item.percentage }}%</span>
          </div>
        </div>
        <div v-else class="cat-ranking__empty">暂无收入数据</div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { formatAmount } from '@/shared/utils/format'
import PercentageBar from '../common/PercentageBar.vue'
import type { CategoryRankingItem } from '../../types/wealthTypes'

defineProps<{
  expenseData: CategoryRankingItem[]
  incomeData: CategoryRankingItem[]
}>()

const activeTab = ref('expense')

function fmt(v: number): string {
  return formatAmount(v)
}
</script>

<style scoped>
.cat-ranking__list { display: flex; flex-direction: column; gap: 12px; }
.cat-ranking__item { display: flex; flex-direction: column; gap: 4px; }
.cat-ranking__top { display: flex; justify-content: space-between; }
.cat-ranking__name { font-size: 13px; color: var(--el-text-color-regular); }
.cat-ranking__amt { font-size: 13px; font-weight: 600; }
.cat-ranking__pct { font-size: 11px; color: var(--el-text-color-secondary); }
.cat-ranking__empty {
  padding: 24px; text-align: center; color: var(--el-text-color-placeholder);
}
.text-income { color: #52c41a; }
.text-expense { color: #f5222d; }
</style>
