import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  MonthlyReview, TrendItem, CategoryRankingItem,
  MonthlyListData, CompareData, BalanceInfoFormData,
} from '../types/wealthTypes'

export const useReviewStore = defineStore('review', () => {
  // ─── 状态 ───
  const currentYear = ref(new Date().getFullYear())
  const currentMonth = ref(new Date().getMonth() + 1)
  const review = ref<MonthlyReview | null>(null)
  const trendData = ref<TrendItem[]>([])
  const expenseRanking = ref<CategoryRankingItem[]>([])
  const incomeRanking = ref<CategoryRankingItem[]>([])
  const monthlyList = ref<MonthlyListData | null>(null)
  const compareData = ref<CompareData | null>(null)

  const loading = ref(false)
  const trendLoading = ref(false)
  const rankingLoading = ref(false)
  const listLoading = ref(false)

  // ─── 方法 ───
  async function fetchReview(year?: number, month?: number) {
    const y = year ?? currentYear.value
    const m = month ?? currentMonth.value
    currentYear.value = y
    currentMonth.value = m
    loading.value = true
    try {
      const resp = await wealthApi.getMonthlyReview({ year: y, month: m })
      review.value = resp.data as MonthlyReview
    } catch (e) {
      console.error('获取复盘数据失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchTrendData(months = 12) {
    trendLoading.value = true
    try {
      const resp = await wealthApi.getTrendData({ months })
      trendData.value = resp.data as TrendItem[]
    } catch (e) {
      console.error('获取趋势数据失败:', e)
    } finally {
      trendLoading.value = false
    }
  }

  async function fetchRanking(year?: number, month?: number) {
    const y = year ?? currentYear.value
    const m = month ?? currentMonth.value
    rankingLoading.value = true
    try {
      const [expResp, incResp] = await Promise.all([
        wealthApi.getCategoryRanking({ year: y, month: m, type: '支出' }),
        wealthApi.getCategoryRanking({ year: y, month: m, type: '收入' }),
      ])
      expenseRanking.value = expResp.data as CategoryRankingItem[]
      incomeRanking.value = incResp.data as CategoryRankingItem[]
    } catch (e) {
      console.error('获取分类排行失败:', e)
    } finally {
      rankingLoading.value = false
    }
  }

  async function fetchMonthlyList(page = 1, pageSize = 12) {
    listLoading.value = true
    try {
      const resp = await wealthApi.getMonthlyList({ page, page_size: pageSize })
      monthlyList.value = resp.data as MonthlyListData
    } catch (e) {
      console.error('获取历史复盘列表失败:', e)
    } finally {
      listLoading.value = false
    }
  }

  async function fetchCompare(year?: number, month?: number) {
    const y = year ?? currentYear.value
    const m = month ?? currentMonth.value
    try {
      const resp = await wealthApi.getCompareData({ year: y, month: m })
      compareData.value = resp.data as CompareData
    } catch (e) {
      console.error('获取同比环比失败:', e)
    }
  }

  async function saveBalanceList(data: BalanceInfoFormData) {
    try {
      await wealthApi.createBalanceList(data as unknown as Record<string, unknown>)
      await fetchReview()
    } catch (e) {
      console.error('保存复盘数据失败:', e)
      throw e
    }
  }

  async function updateBalanceList(data: BalanceInfoFormData) {
    try {
      await wealthApi.updateBalanceList(data as unknown as Record<string, unknown>)
      await fetchReview()
    } catch (e) {
      console.error('更新复盘数据失败:', e)
      throw e
    }
  }

  function navigateMonth(delta: number) {
    const d = new Date(currentYear.value, currentMonth.value - 1 + delta, 1)
    currentYear.value = d.getFullYear()
    currentMonth.value = d.getMonth() + 1
    loadAll()
  }

  function goToToday() {
    currentYear.value = new Date().getFullYear()
    currentMonth.value = new Date().getMonth() + 1
    loadAll()
  }

  function goToYearMonth(year: number, month: number) {
    currentYear.value = year
    currentMonth.value = month
    loadAll()
  }

  function loadAll() {
    fetchReview()
    fetchTrendData()
  }

  function resetState() {
    currentYear.value = new Date().getFullYear()
    currentMonth.value = new Date().getMonth() + 1
    review.value = null
    trendData.value = []
    expenseRanking.value = []
    incomeRanking.value = []
    monthlyList.value = null
    compareData.value = null
  }

  return {
    currentYear, currentMonth,
    review, trendData, expenseRanking, incomeRanking,
    monthlyList, compareData,
    loading, trendLoading, rankingLoading, listLoading,
    fetchReview, fetchTrendData, fetchRanking,
    fetchMonthlyList, fetchCompare,
    saveBalanceList, updateBalanceList,
    navigateMonth, goToToday, goToYearMonth, loadAll, resetState,
  }
})
