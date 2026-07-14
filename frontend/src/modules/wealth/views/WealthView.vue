<template>
  <div class="wealth-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">人生现金流</h1>
        <el-tag type="warning" class="module-tag">财务维度</el-tag>
      </div>
      <div class="header-actions">
        <span class="header-stats">
          已度过 <b>{{ summary?.lived_weeks ?? 0 }}</b> 周 ·
          结余 <b class="text-income">{{ summary?.surplus_weeks ?? 0 }}</b> 周 ·
          赤字 <b class="text-expense">{{ summary?.deficit_weeks ?? 0 }}</b> 周
        </span>
        <el-button @click="switchToMonthly">
          <el-icon><Calendar /></el-icon>
          月度日历
        </el-button>
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6f7ff">
              <el-icon color="#1890ff"><TrendCharts /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value text-income">￥{{ fmt(summary?.total_income) }}</div>
              <div class="stat-label">总收入</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff1f0">
              <el-icon color="#f5222d"><Bottom /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value text-expense">￥{{ fmt(summary?.total_expense) }}</div>
              <div class="stat-label">总支出</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f6ffed">
              <el-icon color="#52c41a"><Wallet /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value" :class="(summary?.total_net ?? 0) >= 0 ? 'text-income' : 'text-expense'">
                ￥{{ fmt(summary?.total_net) }}
              </div>
              <div class="stat-label">净结余</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff7e6">
              <el-icon color="#fa8c16"><DataAnalysis /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value text-info">{{ summary?.surplus_rate ?? 0 }}%</div>
              <div class="stat-label">结余周占比</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 推演 + 图例 -->
    <el-row :gutter="16" class="tools-row">
      <el-col :xs="24" :md="16">
        <el-card shadow="never" class="tools-card">
          <ControlPanel
            :loading="store.scenarioLoading"
            :result="store.coverageResult"
            @calculate="handleCalculate"
          />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="tools-card">
          <Legend />
        </el-card>
      </el-col>
    </el-row>

    <!-- 热力图 -->
    <el-card shadow="never" class="heatmap-card">
      <div class="heatmap-header">
        <h3>61年 × 52周 现金流热力图</h3>
        <span class="heatmap-info">
          已度过 {{ summary?.lived_weeks ?? 0 }} 周 ·
          结余 {{ summary?.surplus_weeks ?? 0 }} 周 ·
          赤字 {{ summary?.deficit_weeks ?? 0 }} 周
        </span>
      </div>
      <div class="heatmap-scroll">
        <HeatmapGrid @select="handleWeekSelect" />
      </div>
    </el-card>

    <!-- 周明细弹窗 -->
    <WeekDetailModal
      :visible="detailVisible"
      :data="store.selectedWeekData"
      :bills="store.selectedWeekBills"
      :loading="store.weekDetailLoading"
      @close="handleDetailClose"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Calendar, TrendCharts, Bottom, Wallet, DataAnalysis } from '@element-plus/icons-vue'
import { useWealthStore } from '../stores/wealthStore'
import { formatAmount } from '@/shared/utils/format'
import HeatmapGrid from '../components/HeatmapGrid.vue'
import ControlPanel from '../components/ControlPanel.vue'
import Legend from '../components/Legend.vue'
import WeekDetailModal from '../components/WeekDetailModal.vue'

const router = useRouter()
const store = useWealthStore()
const loading = ref(false)
const detailVisible = ref(false)

const summary = computed(() => store.summary)

function fmt(val: number | undefined): string {
  if (val === undefined || val === null) return '0.00'
  return formatAmount(val)
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([
      store.fetchCalendar(),
      store.fetchSummary(),
      store.fetchScenario(),
    ])
  } catch (e) {
    console.error('加载数据失败:', e)
  } finally {
    loading.value = false
  }
}

function switchToMonthly() {
  router.push('/wealth/monthly')
}

async function handleCalculate(params: {
  current_age: number
  current_week: number
  current_cash: number
  daily_budget: number
  daily_interest_rate?: number
}) {
  try {
    await store.runCoverage(params)
  } catch (e) {
    console.error('推演失败:', e)
  }
}

function handleWeekSelect(weekIndex: number) {
  store.selectWeek(weekIndex)
  detailVisible.value = true
}

function handleDetailClose() {
  detailVisible.value = false
  store.clearSelection()
}

function handleRefresh() {
  loadAll()
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped lang="scss">
.wealth-view {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .page-title {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }

    .module-tag {
      font-size: 12px;
    }
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .header-stats {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    white-space: nowrap;

    b { font-weight: 600; }
  }
}

.stats-row {
  margin-bottom: 16px;

  .stat-card {
    :deep(.el-card__body) { padding: 16px; }
  }

  .stat-content {
    display: flex;
    align-items: center;
    gap: 14px;

    .stat-icon {
      width: 44px;
      height: 44px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      flex-shrink: 0;
    }

    .stat-info {
      .stat-value {
        font-size: 20px;
        font-weight: 600;
        line-height: 1;
        margin-bottom: 4px;
      }

      .stat-label {
        font-size: 13px;
        color: var(--el-text-color-regular);
      }
    }
  }
}

.tools-row {
  margin-bottom: 16px;

  .tools-card {
    height: 100%;

    :deep(.el-card__body) {
      padding: 0;
    }
  }
}

.heatmap-card {
  :deep(.el-card__body) {
    padding: 20px;
  }
}

.heatmap-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
}

.heatmap-info {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.heatmap-scroll {
  overflow: auto;
  padding-bottom: 4px;
}

.text-income { color: #52c41a; }
.text-expense { color: #f5222d; }
.text-info { color: #1890ff; }

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .header-stats {
    order: -1;
    width: 100%;
  }

  .stats-row {
    .stat-card {
      :deep(.el-card__body) { padding: 12px; }
    }

    .stat-content {
      gap: 10px;

      .stat-icon {
        width: 36px;
        height: 36px;
        font-size: 15px;
      }

      .stat-info {
        .stat-value { font-size: 16px; }
        .stat-label { font-size: 12px; }
      }
    }
  }
}
</style>
