/** 综合进度看板 — Pinia Store */

import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import * as summaryApi from '../api/summaryApi'
import type {
  YearlyOverview, MonthlyDetail, TrendData, TrendMonth, TrendModuleMeta, RadarData, ModuleDetail,
  QuarterlyReport, QuestionItem, AnswerItem, InsightItem,
} from '../types/summaryTypes'

export const useSummaryStore = defineStore('summary', () => {
  const loading = ref(false)
  const overview = ref<YearlyOverview | null>(null)
  const monthlyDetail = ref<MonthlyDetail | null>(null)
  const radarData = ref<RadarData | null>(null)
  /** 趋势：覆盖率 + 强度两套值（v3.62.44 起是对象，不再是平铺的点数） */
  const trend = ref<TrendData | null>(null)
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
  // 总分退役后，这里不再有「各模块点数堆叠 / 月度总分 / 月目标线」三个派生量：
  // 趋势图直接读 `trend` 里的覆盖率与强度，组件自己拼。

  /** 12 个月的原始行（空数组兜底，模板里不用到处判空） */
  const trendData = computed<TrendMonth[]>(() => trend.value?.months ?? [])
  /** 维度元信息（颜色 / 单位由后端下发） */
  const trendModules = computed<TrendModuleMeta[]>(() => trend.value?.modules ?? [])

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
      trend.value = res.data as TrendData
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
    loading, overview, monthlyDetail, trend, trendData, trendModules, radarData,
    availableYears, currentYear, currentMonth, moduleDetail,
    fetchOverview, fetchMonthlyDetail, fetchTrend, fetchRadar,
    fetchYears, fetchModuleDetail, fetchAll, switchYear,
    // 季度决策工作台
    quarterlyReport, quarterlyQuestions, quarterlyAnswers, quarterlyInsights,
    currentQuarter, quarterlyLoading,
    fetchQuarterlyReport, saveAnswer, switchQuarter,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useSummaryStore, import.meta.hot))
}
