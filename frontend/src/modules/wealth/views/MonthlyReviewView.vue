<template>
  <div class="review-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">收入支出复盘</h1>
        <el-tag type="warning" class="module-tag">财务维度</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="switchToMonthly">
          <el-icon><Calendar /></el-icon>
          月度日历
        </el-button>
        <el-button @click="switchToHeatmap">
          <el-icon><Grid /></el-icon>
          现金流热力图
        </el-button>
        <el-button @click="switchToCashflow">
          <el-icon><Money /></el-icon>
          现金盘点
        </el-button>
        <el-button @click="handleManualCreate">
          <el-icon><Edit /></el-icon>
          手动录入
        </el-button>
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 指标卡片 -->
    <el-card shadow="never" class="section-card">
      <ReviewHeader
        :review="store.review"
        :loading="store.loading"
        @prev-month="store.navigateMonth(-1)"
        @next-month="store.navigateMonth(1)"
        @today="store.goToToday"
      />
    </el-card>

    <!-- 趋势图 -->
    <el-card shadow="never" class="section-card">
      <TrendChart :data="store.trendData" />
    </el-card>

    <!-- 历史复盘列表 -->
    <el-card shadow="never" class="section-card">
      <MonthlyListTable
        :items="store.monthlyList?.items ?? []"
        :total="store.monthlyList?.total ?? 0"
        :loading="store.listLoading"
        @edit="handleEditBalanceInfo"
        @refresh="store.fetchMonthlyList()"
        @page-change="handlePageChange"
        @select="handleListSelect"
      />
    </el-card>

    <!-- 编辑/手动录入弹窗 -->
    <BalanceInfoModal
      :visible="editModalVisible"
      :is-create="isCreating"
      :data="editingData"
      :saving="false"
      @close="editModalVisible = false"
      @save="handleSaveBalanceInfo"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Calendar, Grid, Money, Edit } from '@element-plus/icons-vue'
import { useReviewStore } from '../stores/reviewStore'
import ReviewHeader from '../components/review/ReviewHeader.vue'
import TrendChart from '../components/review/TrendChart.vue'
import MonthlyListTable from '../components/review/MonthlyListTable.vue'
import BalanceInfoModal from '../components/review/BalanceInfoModal.vue'
import type { MonthlyListItem, BalanceInfoFormData } from '../types/wealthTypes'

const router = useRouter()
const store = useReviewStore()

const editModalVisible = ref(false)
const isCreating = ref(false)
const editingData = ref<MonthlyListItem | null>(null)

function switchToMonthly() {
  router.push('/wealth/monthly')
}
function switchToHeatmap() {
  router.push('/wealth/heatmap')
}
function switchToCashflow() {
  router.push('/wealth/cashflow')
}

function handleRefresh() {
  store.loadAll()
  store.fetchMonthlyList()
}

function handleManualCreate() {
  isCreating.value = true
  editingData.value = {
    yearmon: '',
    income: 0,
    expense: 0,
    balance: null,
    deposit: null,
    savings_rate: 0,
    notes: '',
  }
  editModalVisible.value = true
}

function handlePageChange(page: number) {
  store.fetchMonthlyList(page)
}

function handleEditBalanceInfo(row: MonthlyListItem) {
  isCreating.value = false
  editingData.value = row
  editModalVisible.value = true
}

function handleSaveBalanceInfo(data: BalanceInfoFormData) {
  const promise = isCreating.value
    ? store.saveBalanceList(data)
    : store.updateBalanceList(data)
  promise.then(() => {
    editModalVisible.value = false
    editingData.value = null
    store.fetchMonthlyList()
  })
}

function handleListSelect(yearmon: string) {
  const [y, m] = yearmon.split('-').map(Number)
  store.goToYearMonth(y, m)
}

onMounted(() => {
  store.loadAll()
  store.fetchMonthlyList()
})
</script>

<style scoped>
.review-view {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}
.module-tag { font-size: 12px; }
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.section-card {
  margin-bottom: 16px;
}
.section-card :deep(.el-card__body) { padding: 20px; }

.text-income { color: #52c41a; }
.text-expense { color: #f5222d; }

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .header-actions { width: 100%; justify-content: flex-start; }
}
</style>
