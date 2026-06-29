<template>
  <div class="monthly-list">
    <div class="monthly-list__header">
      <h3>历史复盘列表</h3>
      <div class="monthly-list__actions">
        <el-button size="small" @click="$emit('refresh')" :loading="loading">刷新</el-button>
      </div>
    </div>

    <el-table :data="items" v-loading="loading" stripe size="small" style="width: 100%" @row-click="handleRowClick">
      <el-table-column prop="yearmon" label="年月" min-width="140" />
      <el-table-column prop="income" label="收入" min-width="130" align="right">
        <template #default="{ row }"><span class="money-value">￥{{ fmt(row.income) }}</span></template>
      </el-table-column>
      <el-table-column prop="expense" label="支出" min-width="130" align="right">
        <template #default="{ row }"><span class="money-value">￥{{ fmt(row.expense) }}</span></template>
      </el-table-column>
      <el-table-column prop="balance" label="结余" min-width="130" align="right">
        <template #default="{ row }">
          <span :class="['money-value', row.balance >= 0 ? 'text-income' : 'text-expense']">
            {{ row.balance >= 0 ? '￥' : '-￥' }}{{ fmt(Math.abs(row.balance)) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="savings_rate" label="结余率" width="100" align="right">
        <template #default="{ row }">{{ row.savings_rate }}%</template>
      </el-table-column>
      <el-table-column prop="deposit" label="存款余额" min-width="130" align="right">
        <template #default="{ row }"><span class="money-value">￥{{ fmt(row.deposit) }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" @click.stop="$emit('edit', row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="total > pageSize" class="monthly-list__pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        small
        layout="prev, pager, next"
        @current-change="$emit('pageChange', $event)"
      />
    </div>

    <div v-if="!items.length && !loading" class="monthly-list__empty">
      暂无复盘数据，请在月度复盘页面上方选择月份后点击「生成复盘」
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { formatAmount } from '@/shared/utils/format'
import type { MonthlyListItem } from '../../types/wealthTypes'

const props = withDefaults(defineProps<{
  items: MonthlyListItem[]
  total?: number
  page?: number
  pageSize?: number
  loading?: boolean
}>(), {
  total: 0, page: 1, pageSize: 12, loading: false,
})

const emit = defineEmits<{
  edit: [row: MonthlyListItem]
  refresh: []
  pageChange: [page: number]
  select: [yearmon: string]
}>()

const page = ref(props.page)

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  return formatAmount(v)
}

function handleRowClick(row: MonthlyListItem) {
  emit('select', row.yearmon)
}
</script>

<style scoped>
.monthly-list__header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
}
.monthly-list__header h3 { margin: 0; font-size: 16px; font-weight: 600; }
.monthly-list__pagination { margin-top: 12px; display: flex; justify-content: center; }
.monthly-list__empty { padding: 24px; text-align: center; color: var(--el-text-color-placeholder); font-size: 13px; }
.money-value { font-family: 'SF Mono', 'Menlo', 'Consolas', monospace; }
.text-income { color: #52c41a; }
.text-expense { color: #f5222d; }
</style>
