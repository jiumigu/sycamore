<template>
  <div class="quarterly-workbench" v-loading="store.quarterlyLoading">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>🔍 季度决策工作台</h2>
        <el-tag size="small" type="warning" effect="plain">从数据到决策</el-tag>
      </div>
      <div class="header-actions">
        <el-select v-model="store.currentYear" size="small" style="width: 100px" @change="handleYearChange">
          <el-option v-for="y in store.availableYears" :key="y" :label="`${y}年`" :value="y" />
        </el-select>
        <el-radio-group v-model="store.currentQuarter" size="small" @change="handleQuarterChange">
          <el-radio-button v-for="q in QUARTER_OPTIONS" :key="q.value" :value="q.value">
            {{ q.label }}
          </el-radio-button>
        </el-radio-group>
        <el-button :icon="Refresh" size="small" @click="store.fetchQuarterlyReport()" />
      </div>
    </div>

    <!-- 洞察卡片 -->
    <el-row :gutter="16" class="insights-row">
      <el-col v-for="insight in store.quarterlyInsights" :key="insight.message" :span="6">
        <el-card shadow="hover" class="insight-card" :class="`insight-${insight.type}`">
          <div class="insight-body">
            <span class="insight-icon">{{ insight.icon }}</span>
            <span class="insight-text">{{ insight.message }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 季度对比概览 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📊 季度对比总览</span>
          <el-tooltip content="环比 = 与上季度相比；同比 = 与去年同期相比" placement="left">
            <el-icon class="hint-icon"><WarningFilled /></el-icon>
          </el-tooltip>
        </div>
      </template>

      <el-table :data="moduleTableData" stripe size="small" style="width: 100%">
        <el-table-column label="模块" min-width="80">
          <template #default="{ row }">
            <span class="module-dot" :style="{ background: row.color }" />
            {{ row.label }}
          </template>
        </el-table-column>
        <el-table-column label="本季得分" min-width="80" sortable prop="points">
          <template #default="{ row }">
            <span class="value-cell">{{ row.points.toFixed(1) }}</span>
            <span class="value-unit">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="上季度" min-width="70" prop="prev_quarter_points" align="right" />
        <el-table-column label="环比" min-width="80" sortable prop="qoq_change" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.qoq_change)">
              {{ row.qoq_change > 0 ? '+' : '' }}{{ row.qoq_change }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="去年同期" min-width="70" prop="last_year_points" align="right" />
        <el-table-column label="同比" min-width="80" sortable prop="yoy_change" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.yoy_change)">
              {{ row.yoy_change > 0 ? '+' : '' }}{{ row.yoy_change }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 模块趋势对比图 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <span class="card-title">📈 环比变化一览</span>
      </template>
      <div class="bar-chart-wrapper" ref="chartRef1"></div>
    </el-card>

    <!-- 追问：洞察与反思 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">❓ 关键追问</span>
          <el-tag size="small" type="info">
            {{ answeredCount }}/{{ store.quarterlyQuestions.length }} 已回答
          </el-tag>
        </div>
      </template>

      <div v-if="!store.quarterlyQuestions.length" class="empty-state">
        暂无追问，说明各项指标平稳 🎉
      </div>

      <div v-for="(q, i) in store.quarterlyQuestions" :key="q.question_key" class="question-item">
        <div class="question-header">
          <el-tag :type="categoryTag(q.question_category)" size="small" class="q-category">
            {{ categoryLabel(q.question_category) }}
          </el-tag>
          <span class="question-text">{{ q.question_text }}</span>
        </div>

        <div class="answer-area">
          <el-input
            v-model="answerMap[q.question_key]"
            type="textarea"
            :rows="2"
            placeholder="写下你的思考..."
            :disabled="isAnswered(q.question_key)"
          />
          <div class="answer-actions">
            <el-checkbox v-model="actionMap[q.question_key]" :disabled="isAnswered(q.question_key)">
              已采取行动
            </el-checkbox>
            <div class="answer-buttons">
              <el-button size="small" @click="skipQuestion(q.question_key)">跳过</el-button>
              <el-button
                size="small"
                type="primary"
                :loading="savingKey === q.question_key"
                :disabled="!answerMap[q.question_key]?.trim()"
                @click="submitAnswer(q.question_key)"
              >
                {{ isAnswered(q.question_key) ? '已回答' : '提交反思' }}
              </el-button>
            </div>
          </div>
        </div>

        <div v-if="isAnswered(q.question_key)" class="answered-note">
          <el-icon><Check /></el-icon>
          <span>{{ getAnswerText(q.question_key) }}</span>
        </div>

        <el-divider v-if="i < store.quarterlyQuestions.length - 1" />
      </div>
    </el-card>

    <!-- 历史问答回顾 -->
    <el-card v-if="historyAnswers.length" shadow="hover" class="section-card">
      <template #header>
        <span class="card-title">📜 历史问答回顾</span>
      </template>
      <div v-for="a in historyAnswers" :key="a.id" class="history-item">
        <div class="history-q">{{ a.question_text }}</div>
        <div class="history-a">
          <el-icon><ChatDotRound /></el-icon>
          {{ a.answer_text }}
        </div>
        <div class="history-meta">
          <span class="history-date">{{ a.updated_at?.slice(0, 10) }}</span>
          <el-tag v-if="a.action_taken" size="small" type="success">已行动</el-tag>
        </div>
        <el-divider />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { Refresh, WarningFilled, Check, ChatDotRound } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { useSummaryStore } from '../stores/summaryStore'
import { QUARTER_OPTIONS, MODULE_LABELS, MODULE_COLORS } from '../types/summaryTypes'

const store = useSummaryStore()

const answerMap = reactive<Record<string, string>>({})
const actionMap = reactive<Record<string, boolean>>({})
const savingKey = ref('')
const chartRef1 = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const categoryTag = (cat: string): 'danger' | 'warning' | 'success' | 'info' => {
  const map: Record<string, 'danger' | 'warning' | 'success' | 'info'> = {
    drop: 'danger',
    target_behind: 'warning',
    improve: 'success',
    low_performer: 'info',
  }
  return map[cat] || 'info'
}

const categoryLabel = (cat: string): string => {
  const map: Record<string, string> = {
    drop: '⚠ 下降',
    improve: '↑ 上升',
    target_behind: '🎯 目标',
    low_performer: '📉 低效',
    general: '💡 通用',
  }
  return map[cat] || cat
}

const moduleTableData = computed(() => store.quarterlyReport?.modules ?? [])

const answeredCount = computed(() => {
  return store.quarterlyAnswers.filter(a => a.answer_text?.trim()).length
})

const historyAnswers = computed(() => {
  return store.quarterlyAnswers.filter(a => a.answer_text?.trim())
})

function isAnswered(key: string): boolean {
  return store.quarterlyAnswers.some(a => a.question_key === key && a.answer_text?.trim())
}

function getAnswerText(key: string): string {
  return store.quarterlyAnswers.find(a => a.question_key === key)?.answer_text ?? ''
}

function changeClass(val: number): string {
  if (val > 0) return 'change-up'
  if (val < 0) return 'change-down'
  return 'change-flat'
}

function handleYearChange(year: number) {
  store.switchQuarter(store.currentQuarter)
}

function handleQuarterChange(quarter: number) {
  store.switchQuarter(quarter)
}

function skipQuestion(key: string) {
  answerMap[key] = '(跳过)'
  submitAnswer(key)
}

async function submitAnswer(key: string) {
  const text = answerMap[key] || ''
  const action = actionMap[key] || false
  savingKey.value = key
  await store.saveAnswer(key, text, action)
  savingKey.value = ''
}

function renderChart() {
  const report = store.quarterlyReport
  if (!report || !chartRef1.value) return

  if (chartInstance) chartInstance.dispose()

  chartInstance = echarts.init(chartRef1.value)

  const modules = report.modules
  const labels = modules.map(m => m.label)
  const current = modules.map(m => m.points)
  const previous = modules.map(m => m.prev_quarter_points)
  // 同比
  const lastYear = modules.map(m => m.last_year_points)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: ['本季度', '上季度', '去年同期'],
      top: 0,
      left: 'center',
      textStyle: { fontSize: 12 },
    },
    grid: {
      left: 50,
      right: 20,
      top: 40,
      bottom: 30,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '进度点',
      nameTextStyle: { fontSize: 11 },
    },
    series: [
      {
        name: '去年同期',
        type: 'bar',
        data: lastYear,
        itemStyle: { color: '#D1D5DB', opacity: 0.6 },
        barWidth: 8,
        barGap: '20%',
      },
      {
        name: '上季度',
        type: 'bar',
        data: previous,
        itemStyle: { color: '#93C5FD', opacity: 0.8 },
        barWidth: 8,
      },
      {
        name: '本季度',
        type: 'bar',
        data: current.map((v, i) => ({
          value: v,
          itemStyle: { color: modules[i].color },
        })),
        barWidth: 8,
      },
    ],
  })
}

watch(() => store.quarterlyReport, () => {
  nextTick(renderChart)
}, { deep: true })

onMounted(() => {
  store.fetchQuarterlyReport()
})
</script>

<style scoped lang="scss">
.quarterly-workbench {
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
  h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 洞察卡片 */
.insights-row {
  margin-bottom: 16px;
}

.insight-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
  &.insight-success { border-left: 4px solid #10B981; }
  &.insight-warning { border-left: 4px solid #F59E0B; }
  &.insight-danger { border-left: 4px solid #EF4444; }
  &.insight-info { border-left: 4px solid #6366F1; }
  :deep(.el-card__body) { padding: 14px; }
}

.insight-body {
  display: flex;
  align-items: center;
  gap: 10px;
}

.insight-icon {
  font-size: 22px;
  flex-shrink: 0;
}

.insight-text {
  font-size: 12px;
  line-height: 1.4;
  color: var(--el-text-color-primary);
}

/* 通用卡片 */
.section-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
  :deep(.el-card__body) { padding: 12px 16px 16px; }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.hint-icon {
  color: var(--el-text-color-secondary);
  cursor: help;
  font-size: 14px;
}

/* 模块表格 */
.module-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

.value-cell {
  font-weight: 600;
  font-size: 14px;
}
.value-unit {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-left: 2px;
}

.change-up {
  color: #10B981;
  font-weight: 600;
}
.change-down {
  color: #EF4444;
  font-weight: 600;
}
.change-flat {
  color: var(--el-text-color-secondary);
}

/* 柱状图 */
.bar-chart-wrapper {
  width: 100%;
  height: 300px;
}

/* 追问区域 */
.question-item {
  margin-bottom: 4px;
}

.question-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 10px;
}

.q-category {
  flex-shrink: 0;
  margin-top: 1px;
}

.question-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}

.answer-area {
  padding-left: 0;
}

.answer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.answer-buttons {
  display: flex;
  gap: 8px;
}

.answered-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 12px;
  background: #F0FDF4;
  border-radius: 6px;
  font-size: 13px;
  color: #15803D;
  line-height: 1.5;
}

.history-item {
  margin-bottom: 8px;
}

.history-q {
  font-size: 13px;
  color: var(--el-text-color-primary);
  margin-bottom: 6px;
  font-weight: 500;
}

.history-a {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  color: #6B7280;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  line-height: 1.5;
}

.history-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.history-date {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.empty-state {
  text-align: center;
  color: #9CA3AF;
  font-size: 14px;
  padding: 40px 0;
}
</style>
