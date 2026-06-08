<template>
  <div class="summary-dashboard" v-loading="store.loading">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>📊 综合进度看板</h2>
        <el-tag size="small" type="success" effect="plain">年度目标 {{ YEARLY_TARGET }} 点</el-tag>
      </div>
      <div class="header-actions">
        <el-select
          v-model="store.currentYear"
          size="small"
          style="width: 100px"
          @change="store.switchYear"
        >
          <el-option
            v-for="y in store.availableYears"
            :key="y"
            :label="`${y}年`"
            :value="y"
          />
        </el-select>
        <el-button :icon="Refresh" size="small" @click="store.fetchAll" />
      </div>
    </div>

    <!-- 概览统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-icon" style="background: #D1FAE5; color: #059669">🎯</div>
            <div>
              <div class="stat-value">{{ overview?.total_points ?? '--' }}</div>
              <div class="stat-label">年度总进度 / {{ YEARLY_TARGET }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-icon" style="background: #FEF3C7; color: #D97706">📈</div>
            <div>
              <div class="stat-value">{{ overview?.progress_percent ?? '--' }}%</div>
              <div class="stat-label">目标完成率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-icon" style="background: #DBEAFE; color: #2563EB">⏳</div>
            <div>
              <div class="stat-value">{{ overview?.remaining_points ?? '--' }}</div>
              <div class="stat-label">剩余目标 / 还需</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-icon" style="background: #FCE4EC; color: #DB2777">📅</div>
            <div>
              <div class="stat-value">{{ overview?.monthly_target ?? '--' }}</div>
              <div class="stat-label">月度目标 / 月均</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 进度环 + 模块贡献 + 雷达图 -->
    <el-row :gutter="16" class="summary-top-row">
      <!-- 年度进度环 -->
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <template #header><span class="card-title">🎯 年度进度</span></template>
          <div class="ring-wrapper">
            <ProgressRing
              :value="overview?.total_points ?? 0"
              :max="YEARLY_TARGET"
              :label="`${overview?.year || currentYear}年`"
            />
          </div>
        </el-card>
      </el-col>

      <!-- 各模块贡献 -->
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <template #header>
            <span class="card-title">📊 各模块贡献</span>
          </template>
          <ModuleBar
            v-if="overview?.modules"
            :modules="overview.modules"
            :show-percent="true"
            @view-module="handleViewModule"
          />
          <div v-else class="chart-empty">暂无数据</div>
        </el-card>
      </el-col>

      <!-- 雷达图 -->
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <template #header><span class="card-title">📡 七维平衡</span></template>
          <RadarChart v-if="store.radarData" />
          <div v-else class="chart-empty">暂无数据</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 月度趋势图 -->
    <el-card shadow="hover" class="chart-card full-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📈 月度进度趋势</span>
          <div class="card-hint">堆叠柱状图展示各模块月度贡献，红线为月目标</div>
        </div>
      </template>
      <TrendChart v-if="store.trendData.length" />
      <div v-else class="chart-empty" style="height:200px;display:flex;align-items:center;justify-content:center">
        暂无趋势数据
      </div>
    </el-card>

    <!-- 月度详情表格 -->
    <el-card shadow="hover" class="chart-card full-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📅 月度明细</span>
          <el-button size="small" @click="showMonthModal = true">
            查看本月详情
          </el-button>
        </div>
      </template>
      <el-table :data="monthTableData" stripe size="small" style="width: 100%" @row-click="handleRowClick">
        <el-table-column label="月份" min-width="60">
          <template #default="{ row }">{{ row.month }}月</template>
        </el-table-column>
        <el-table-column label="总进度" min-width="80" sortable prop="total_points">
          <template #default="{ row }">
            <span :class="row.total_points >= row.month_target ? 'text-success' : 'text-warning'">
              {{ row.total_points.toFixed(1) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="目标" min-width="60" prop="month_target" />
        <el-table-column label="财富" min-width="60" prop="wealth" />
        <el-table-column label="健康" min-width="60" prop="health" />
        <el-table-column label="时间投入" min-width="70" prop="times" />
        <el-table-column label="阅读" min-width="60" prop="book" />
        <el-table-column label="小确幸" min-width="60" prop="sugar" />
        <el-table-column label="旅行" min-width="60" prop="travel" />
        <el-table-column label="文字" min-width="60" prop="words" />
        <el-table-column label="达成率" width="80" sortable>
          <template #default="{ row }">
            <span :style="{ color: row.rate >= 80 ? '#52c41a' : row.rate >= 50 ? '#faad14' : '#f5222d', fontWeight: 600 }">
              {{ row.rate }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 月度详情弹窗 -->
    <MonthlyModal
      v-model:visible="showMonthModal"
      :year="store.currentYear"
      :month="store.currentMonth"
      @view-module="handleViewModule"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { useSummaryStore } from '../stores/summaryStore'
import { YEARLY_TARGET } from '../types/summaryTypes'
import ProgressRing from '../components/ProgressRing.vue'
import ModuleBar from '../components/ModuleBar.vue'
import RadarChart from '../components/RadarChart.vue'
import TrendChart from '../components/TrendChart.vue'
import MonthlyModal from '../components/MonthlyModal.vue'

const store = useSummaryStore()
const currentYear = computed(() => store.currentYear)
const overview = computed(() => store.overview)
const showMonthModal = ref(false)

const monthTableData = computed(() => {
  return store.trendData.map(d => ({
    ...d,
    total_points: d.total_points,
    rate: d.month_target > 0 ? Math.round(d.total_points / d.month_target * 100) : 0,
  }))
})

function handleViewModule(module: string, year?: number, month?: number) {
  store.fetchModuleDetail(module, year, month)
}

function handleRowClick(row: { month: number }) {
  store.currentMonth = row.month
  showMonthModal.value = true
}

onMounted(() => {
  store.fetchAll()
})
</script>

<style scoped>
.summary-dashboard {
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
  gap: 10px;
}
.header-left h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 统计卡片 */
.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
}
.stat-card :deep(.el-card__body) {
  padding: 16px;
}

.stat-body {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

/* 图表卡片 */
.charts-row {
  margin-bottom: 16px;
}

.chart-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
}
.chart-card :deep(.el-card__body) {
  padding: 12px 16px 16px;
}

/* 顶部三列等高卡片 */
.summary-top-row {
  margin-bottom: 16px;
}
.summary-top-row .el-col {
  display: flex;
}
.summary-card {
  border: none;
  border-radius: 10px;
  flex: 1;
}
.summary-card :deep(.el-card__body) {
  padding: 12px 16px 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-hint {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.full-card {
  margin-bottom: 16px;
}

.ring-wrapper {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

.chart-empty {
  text-align: center;
  color: #9CA3AF;
  font-size: 13px;
  padding: 40px 0;
}

.text-success {
  color: #10B981;
  font-weight: 600;
}
.text-warning {
  color: #F59E0B;
  font-weight: 600;
}
</style>
