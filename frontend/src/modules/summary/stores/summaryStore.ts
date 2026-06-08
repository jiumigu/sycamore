/** 综合进度看板 — Pinia Store */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import * as summaryApi from '../api/summaryApi'
import type {
  YearlyOverview, MonthlyDetail, TrendPoint, RadarData, ModuleDetail,
  QuarterlyReport, QuestionItem, AnswerItem, InsightItem,
} from '../types/summaryTypes'
import { MODULE_LABELS, MODULE_COLORS, MONTHLY_TARGET } from '../types/summaryTypes'

export const useSummaryStore = defineStore('summary', () => {
  const loading = ref(false)
  const overview = ref<YearlyOverview | null>(null)
  const monthlyDetail = ref<MonthlyDetail | null>(null)
  const trendData = ref<TrendPoint[]>([])
  const radarData = ref<RadarData | null>(null)
  const availableYears = ref<number[]>([])
  const currentYear = ref(new Date().getFullYear())
  const currentMonth = ref(new Date().getMonth() + 1)
  const moduleDetail = ref<ModuleDetail | null>(null)

  // ── 季度决策工作台 ──
  const quarterlyReport = ref<QuarterlyReport | null>(null)
  const quarterlyQuestions = ref<QuestionItem[]>([])
  const quarterlyAnswers = ref<AnswerItem[]>([])
  const quarterlyInsights = ref<InsightItem[]>([])
  const currentQuarter = ref(Math.ceil((new Date().getMonth() + 1) / 3))
  const quarterlyLoading = ref(false)

  // ── 图表 computed ──

  const trendMonths = computed(() => trendData.value.map(d => `${d.month}月`))

  const trendSeries = computed(() => {
    const keys = ['wealth', 'health', 'times', 'words', 'sugar', 'travel', 'book'] as const
    return keys.map(k => ({
      name: MODULE_LABELS[k],
      type: 'bar' as const,
      stack: 'total',
      barMaxWidth: 20,
      itemStyle: { color: MODULE_COLORS[k] },
      data: trendData.value.map(d => d[k]),
    }))
  })

  const totalByMonth = computed(() => trendData.value.map(d => d.total_points))
  const monthTargetLine = computed(() => trendData.value.map(() => MONTHLY_TARGET))

  // ── 操作 ──

  async function fetchOverview(year?: number) {
    try {
      const res = await summaryApi.getYearlyOverview({ year: year ?? currentYear.value })
      overview.value = res.data
    } catch {
      ElMessage.error('获取年度总览失败')
    }
  }

  async function fetchMonthlyDetail(year?: number, month?: number) {
    try {
      const res = await summaryApi.getMonthlyDetail({
        year: year ?? currentYear.value,
        month: month ?? currentMonth.value,
      })
      monthlyDetail.value = res.data
    } catch {
      ElMessage.error('获取月度详情失败')
    }
  }

  async function fetchTrend(year?: number) {
    try {
      const res = await summaryApi.getTrend({ year: year ?? currentYear.value })
      trendData.value = res.data
    } catch {
      ElMessage.error('获取趋势数据失败')
    }
  }

  async function fetchRadar(year?: number) {
    try {
      const res = await summaryApi.getRadar({ year: year ?? currentYear.value })
      radarData.value = res.data
    } catch {
      ElMessage.error('获取雷达数据失败')
    }
  }

  async function fetchYears() {
    try {
      const res = await summaryApi.getYears()
      availableYears.value = res.data
    } catch {
      /* ignore */
    }
  }

  async function fetchModuleDetail(module: string, year?: number, month?: number) {
    try {
      const res = await summaryApi.getModuleDetail({
        module,
        year: year ?? currentYear.value,
        month: month ?? undefined,
      })
      moduleDetail.value = res.data
    } catch {
      ElMessage.error('获取模块详情失败')
    }
  }

  async function fetchAll(year?: number) {
    loading.value = true
    try {
      await Promise.all([
        fetchOverview(year),
        fetchTrend(year),
        fetchRadar(year),
        fetchYears(),
      ])
    } finally {
      loading.value = false
    }
  }

  function switchYear(year: number) {
    currentYear.value = year
    fetchAll(year)
  }

  // ── 季度决策工作台 ─────────────────────────────────

  async function fetchQuarterlyReport(year?: number, quarter?: number) {
    quarterlyLoading.value = true
    try {
      const yr = year ?? currentYear.value
      const q = quarter ?? currentQuarter.value
      const [reportRes, insightsRes, questionsRes, answersRes] = await Promise.all([
        summaryApi.getQuarterlyReport({ year: yr, quarter: q }),
        summaryApi.getQuarterlyInsights({ year: yr, quarter: q }),
        summaryApi.getQuarterlyQuestions({ year: yr, quarter: q }),
        summaryApi.getQuarterlyAnswers({ year: yr, quarter: q }),
      ])
      quarterlyReport.value = reportRes.data
      quarterlyInsights.value = insightsRes.data
      quarterlyQuestions.value = questionsRes.data
      quarterlyAnswers.value = answersRes.data
    } catch {
      ElMessage.error('获取季度报告失败')
    } finally {
      quarterlyLoading.value = false
    }
  }

  async function saveAnswer(questionKey: string, answerText: string, actionTaken = false) {
    try {
      await summaryApi.saveQuarterlyAnswers(
        { year: currentYear.value, quarter: currentQuarter.value },
        { question_key: questionKey, answer_text: answerText, action_taken: actionTaken },
      )
      // 刷新问答列表
      await fetchQuarterlyAnswers()
      ElMessage.success('回答已保存')
    } catch {
      ElMessage.error('保存回答失败')
    }
  }

  async function fetchQuarterlyAnswers() {
    try {
      const res = await summaryApi.getQuarterlyAnswers({
        year: currentYear.value,
        quarter: currentQuarter.value,
      })
      quarterlyAnswers.value = res.data
    } catch {
      /* ignore */
    }
  }

  function switchQuarter(quarter: number) {
    currentQuarter.value = quarter
    fetchQuarterlyReport()
  }

  return {
    loading, overview, monthlyDetail, trendData, radarData,
    availableYears, currentYear, currentMonth, moduleDetail,
    trendMonths, trendSeries, totalByMonth, monthTargetLine,
    fetchOverview, fetchMonthlyDetail, fetchTrend, fetchRadar,
    fetchYears, fetchModuleDetail, fetchAll, switchYear,
    // 季度决策工作台
    quarterlyReport, quarterlyQuestions, quarterlyAnswers, quarterlyInsights,
    currentQuarter, quarterlyLoading,
    fetchQuarterlyReport, saveAnswer, switchQuarter,
  }
})
