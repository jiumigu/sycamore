<template>
  <div class="summary-dashboard" v-loading="store.loading">
    <!-- 季度决策卡片 -->
    <QuarterlyDecisionCards />

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
            <div class="card-header-flex">
              <span class="card-title">📊 各模块贡献</span>
              <span v-if="overview?.total_points != null" class="year-progress-badge">
                {{ overview.total_points }} / {{ overview.yearly_target }} 分
                ({{ overview.progress_percent }}%)
              </span>
            </div>
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
          <template #header>
          <div class="card-header-flex">
            <span class="card-title">📡 七维平衡</span>
            <el-button size="small" text type="primary" @click="openRadarConfig">
              <el-icon style="margin-right:2px"><Setting /></el-icon>配置
            </el-button>
          </div>
        </template>
          <!-- v-show 保持组件常驻，避免 v-if 卸载/重挂载导致 ECharts DOM 竞态 -->
          <RadarChart v-show="!!store.radarData" />
          <div v-if="!store.radarData" class="chart-empty">暂无数据</div>
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

    <!-- 身体-状态关联（暂隐藏，等待数据接口就绪后启用） -->
    <!-- <BodyMindChart /> -->

    <!-- 月度详情表格 -->
    <el-card shadow="hover" class="chart-card full-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📅 月度明细</span>
          <div class="header-actions">
            <el-button size="small" @click="openYearDetail">📆 年度明细</el-button>
            <el-button size="small" @click="showMonthModal = true">查看本月详情</el-button>
          </div>
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

    <!-- 每日金句 -->
    <el-card shadow="hover" class="chart-card full-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📖 每日金句</span>
          <el-button size="small" text @click="refreshQuote">🔄 换一句</el-button>
        </div>
      </template>
      <div class="quote-card-body" v-if="dailyQuote">
        <div v-if="dailyQuote.is_paragraph" class="quote-title" @click="showQuoteFull = true">
          {{ dailyQuote.short_title || dailyQuote.content.slice(0, 50) + '...' }}
        </div>
        <div v-else class="quote-content">{{ dailyQuote.content }}</div>
        <div class="quote-author" v-if="dailyQuote.author">— {{ dailyQuote.author }}</div>
        <el-tag size="small">{{ dailyQuote.language }}</el-tag>
      </div>
      <div v-else class="chart-empty">暂无金句</div>
    </el-card>
    <el-dialog v-model="showQuoteFull" title="金句详情" width="500px">
      <div class="full-quote-content">{{ dailyQuote?.content }}</div>
      <div v-if="dailyQuote?.author" class="full-quote-author">— {{ dailyQuote.author }}</div>
      <div v-if="dailyQuote?.source" class="full-quote-source">📎 {{ dailyQuote.source }}</div>
    </el-dialog>

    <!-- 月度详情弹窗 -->
    <!-- 年度明细弹窗 -->
    <el-dialog v-model="showYearModal" title="📆 年度明细" width="960" append-to-body>
      <el-table :data="yearRows" v-loading="yearLoading" stripe size="small" max-height="420" style="width: 100%">
        <el-table-column v-for="col in YEAR_COLUMNS" :key="col.key" :label="col.label" :prop="col.key"
          align="right" :min-width="col.width" />
        <el-table-column label="达成率" min-width="90" align="right" fixed="right">
          <template #default="{ row }">
            <span :class="row.progress_percent >= 100 ? 'text-success' : row.progress_percent >= 50 ? 'text-primary' : 'text-warning'">
              {{ row.progress_percent }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <MonthlyModal
      v-model:visible="showMonthModal"
      :year="store.currentYear"
      :month="store.currentMonth"
      @view-module="handleViewModule"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { Refresh, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getRadarConfig, saveRadarConfig as apiSaveRadarConfig, getRadarConfigHistory, getYearlyDetail } from '../api/summaryApi'
import { useSummaryStore } from '../stores/summaryStore'
import { YEARLY_TARGET } from '../types/summaryTypes'
import QuarterlyDecisionCards from '../components/QuarterlyDecisionCards.vue'
import ProgressRing from '../components/ProgressRing.vue'
import ModuleBar from '../components/ModuleBar.vue'
import RadarChart from '../components/RadarChart.vue'
import TrendChart from '../components/TrendChart.vue'
import MonthlyModal from '../components/MonthlyModal.vue'
import BodyMindChart from '../components/BodyMindChart.vue'
import { getRandomQuote } from '@/modules/toolkit/api/quoteApi'
import type { Quote } from '@/modules/toolkit/types/quoteTypes'

const store = useSummaryStore()
const currentYear = computed(() => store.currentYear)
const overview = computed(() => store.overview)
const showMonthModal = ref(false)

// ─── 年度明细 ───
const YEAR_COLUMNS = [
  { key: 'year', label: '年份', width: 70 },
  { key: 'total_points', label: '总进度', width: 80 },
  { key: 'yearly_target', label: '目标', width: 70 },
  { key: 'wealth', label: '财富', width: 70 },
  { key: 'health', label: '健康', width: 70 },
  { key: 'times', label: '时间投入', width: 85 },
  { key: 'book', label: '阅读', width: 70 },
  { key: 'sugar', label: '小确幸', width: 70 },
  { key: 'travel', label: '旅行', width: 70 },
  { key: 'words', label: '文字', width: 70 },
]
const showYearModal = ref(false)
const yearRows = ref<Array<Record<string, any>>>([])
const yearLoading = ref(false)

async function openYearDetail() {
  showYearModal.value = true
  if (yearRows.value.length) return
  yearLoading.value = true
  try {
    const res = await getYearlyDetail()
    yearRows.value = res.data.years || []
  } catch {
    ElMessage.error('获取年度明细失败')
  } finally {
    yearLoading.value = false
  }
}
const dailyQuote = ref<Quote | null>(null)
const showQuoteFull = ref(false)

// ─── 七维平衡封顶配置 ───
const CONFIG_ITEMS = [
  { key: 'wealth_max', label: '财富', unit: '万元' },
  { key: 'health_max', label: '健康', unit: '万步' },
  { key: 'times_max', label: '时间投入', unit: '小时/30' },
  { key: 'words_max', label: '文字记录', unit: '万字' },
  { key: 'sugar_max', label: '小确幸', unit: '级' },
  { key: 'travel_max', label: '旅行', unit: '次' },
  { key: 'book_max', label: '阅读', unit: '本' },
]
const configItems = CONFIG_ITEMS
const configVisible = ref(false)
const savingConfig = ref(false)
const configForm = reactive<Record<string, number | string>>({
  wealth_max: 10, health_max: 80, times_max: 80,
  words_max: 20, sugar_max: 50, travel_max: 20, book_max: 20, note: '',
})
const configHistory = ref<Array<Record<string, any>>>([])

async function openRadarConfig() {
  try {
    const res = await getRadarConfig()
    for (const item of CONFIG_ITEMS) {
      if (res.data[item.key] != null) configForm[item.key] = res.data[item.key]
    }
    configForm.note = ''
    configVisible.value = true
    const his = await getRadarConfigHistory()
    configHistory.value = his.data || []
  } catch {
    ElMessage.error('获取配置失败')
  }
}

async function saveRadarConfig() {
  savingConfig.value = true
  try {
    await apiSaveRadarConfig({ ...configForm })
    ElMessage.success('封顶配置已保存')
    configVisible.value = false
    await store.fetchRadar()  // 立即刷新雷达图
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingConfig.value = false
  }
}

async function refreshQuote() {
  try {
    const res = await getRandomQuote()
    dailyQuote.value = res.data as Quote
  } catch {
    dailyQuote.value = null
  }
}

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
  refreshQuote()
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

.quote-card-body {
  padding: 8px 0;
}
.quote-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-color-primary);
  cursor: pointer;
  line-height: 1.5;
}
.quote-content {
  font-size: 14px;
  color: #1F2937;
  line-height: 1.6;
  white-space: pre-wrap;
}
.quote-author {
  margin-top: 6px;
  font-size: 13px;
  color: #6B7280;
  font-style: italic;
}
.full-quote-content {
  font-size: 16px;
  line-height: 1.8;
  white-space: pre-wrap;
  margin-bottom: 12px;
}
.full-quote-author {
  font-size: 14px;
  color: #6B7280;
  font-style: italic;
  margin-bottom: 4px;
}
.full-quote-source {
  font-size: 13px;
  color: #9CA3AF;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.card-header-flex {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.year-progress-badge {
  font-size: 12px;
  font-weight: 600;
  color: #1F2937;
  background: #F3F4F6;
  padding: 2px 10px;
  border-radius: 12px;
}
.config-hint {
  font-size: 12px;
  color: #6B7280;
  margin-bottom: 12px;
}
.config-unit {
  margin-left: 8px;
  font-size: 12px;
  color: #9CA3AF;
}
.history-divider {
  margin: 4px 0 8px;
}
.history-collapse {
  max-height: 220px;
  overflow-y: auto;
}
.history-time {
  font-size: 12px;
  color: #4B5563;
  margin-right: 6px;
}
.history-tag {
  margin-right: 6px;
}
.history-note {
  font-size: 12px;
  color: #6B7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}
.history-detail {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px 16px;
  padding: 4px 8px;
}
.history-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}
.history-label {
  color: #6B7280;
}
.history-empty {
  font-size: 12px;
  color: #9CA3AF;
  text-align: center;
  padding: 8px 0;
}
</style>
