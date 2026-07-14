import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  WeekCalendarEntry, CurrentScenario, CoverageResult,
  LifeSummary, BillItem, CalendarQueryParams, WeekDataMap,
  MonthlyDay, DailyDetail, MonthlySummary, FullBillItem, BillCreateData,
  CalendarViewMode,
} from '../types/wealthTypes'

export const useWealthStore = defineStore('wealth', () => {
  // ─── 周历热力图状态 ───
  const weekData = ref<WeekDataMap>({})
  const calendarLoading = ref(false)
  const scenario = ref<CurrentScenario | null>(null)
  const scenarioLoading = ref(false)
  const coverageSet = ref<Set<number>>(new Set())
  const coverageResult = ref<CoverageResult | null>(null)
  const summary = ref<LifeSummary | null>(null)
  const summaryLoading = ref(false)
  const selectedWeekIndex = ref<number | null>(null)
  const selectedWeekData = ref<WeekCalendarEntry | null>(null)
  const selectedWeekBills = ref<BillItem[]>([])
  const weekDetailLoading = ref(false)
  const filterAge = ref<number | undefined>()
  const filterLivedOnly = ref(false)

  // ─── 月度日历状态 ───
  /** 当前视图模式 */
  const viewMode = ref<CalendarViewMode>('heatmap')
  /** 当前查看的年月 */
  const currentYear = ref(new Date().getFullYear())
  const currentMonth = ref(new Date().getMonth() + 1)
  /** 当月每日数据 */
  const monthlyDays = ref<MonthlyDay[]>([])
  /** 当月汇总 */
  const monthlySummary = ref<MonthlySummary | null>(null)
  /** 单日明细 */
  const currentDailyDetail = ref<DailyDetail | null>(null)
  /** 当前选中的日期 */
  const selectedDate = ref<string | null>(null)
  const monthlyLoading = ref(false)
  const dailyDetailLoading = ref(false)

  // ─── 周历方法 ───
  async function fetchCalendar(params?: CalendarQueryParams) {
    calendarLoading.value = true
    try {
      const response = await wealthApi.getCalendar(params)
      const entries = response.data as WeekCalendarEntry[]
      const map: WeekDataMap = {}
      for (const entry of entries) {
        map[entry.global_week_index] = entry
      }
      weekData.value = map
      return entries
    } catch (error) {
      console.error('获取周历失败:', error)
      throw error
    } finally {
      calendarLoading.value = false
    }
  }

  async function fetchScenario() {
    scenarioLoading.value = true
    try {
      const response = await wealthApi.getCurrentScenario()
      scenario.value = response.data as CurrentScenario
      return response.data
    } catch (error) {
      console.error('获取推演状态失败:', error)
      throw error
    } finally {
      scenarioLoading.value = false
    }
  }

  async function runCoverage(params: {
    current_age: number
    current_week: number
    current_cash: number
    daily_budget: number
    daily_interest_rate?: number
  }) {
    scenarioLoading.value = true
    try {
      const response = await wealthApi.calculateCoverage(params)
      const result = response.data as CoverageResult
      coverageResult.value = result
      coverageSet.value = new Set(result.coverage_weeks)
      scenario.value = {
        id: 1,
        snapshot_time: new Date().toISOString(),
        current_age: params.current_age,
        current_week: params.current_week,
        current_cash: String(params.current_cash),
        daily_budget: String(params.daily_budget),
        support_weeks: result.support_weeks,
        end_age: result.end_age,
        end_week: result.end_week,
      }
      return result
    } catch (error) {
      console.error('推演计算失败:', error)
      throw error
    } finally {
      scenarioLoading.value = false
    }
  }

  async function fetchSummary(params?: { user_id?: number }) {
    summaryLoading.value = true
    try {
      const response = await wealthApi.getLifeSummary(params)
      summary.value = response.data as LifeSummary
      return response.data
    } catch (error) {
      console.error('获取总览失败:', error)
      throw error
    } finally {
      summaryLoading.value = false
    }
  }

  async function selectWeek(weekIndex: number) {
    selectedWeekIndex.value = weekIndex
    selectedWeekData.value = weekData.value[weekIndex] ?? null
    weekDetailLoading.value = true
    try {
      const response = await wealthApi.getBillsByWeek({ week_index: weekIndex })
      selectedWeekBills.value = response.data.bills as BillItem[]
    } catch {
      selectedWeekBills.value = []
    } finally {
      weekDetailLoading.value = false
    }
  }

  function clearSelection() {
    selectedWeekIndex.value = null
    selectedWeekData.value = null
    selectedWeekBills.value = []
  }

  function resetCoverage() {
    coverageSet.value = new Set()
    coverageResult.value = null
  }

  async function initCalendar(params: { user_id?: number; birth_date?: string }) {
    try {
      const response = await wealthApi.initCalendar(params)
      return response.data
    } catch (error) {
      console.error('初始化周历失败:', error)
      throw error
    }
  }

  // ─── 月度日历方法 ───
  /** 切换视图 */
  function setViewMode(mode: CalendarViewMode) {
    viewMode.value = mode
  }

  /** 切换月份 */
  function navigateMonth(delta: number) {
    const d = new Date(currentYear.value, currentMonth.value - 1 + delta, 1)
    currentYear.value = d.getFullYear()
    currentMonth.value = d.getMonth() + 1
    fetchMonthlyData()
  }

  /** 返回今日所在月份 */
  function goToToday() {
    currentYear.value = new Date().getFullYear()
    currentMonth.value = new Date().getMonth() + 1
    fetchMonthlyData()
  }

  /** 跳转到指定年月 */
  function goToYearMonth(year: number, month: number) {
    currentYear.value = year
    currentMonth.value = month
    fetchMonthlyData()
  }

  /** 获取月度数据 */
  async function fetchMonthlyData() {
    monthlyLoading.value = true
    try {
      const [calResp, sumResp] = await Promise.all([
        wealthApi.getMonthlyCalendar({
          year: currentYear.value,
          month: currentMonth.value,
        }),
        wealthApi.getMonthlySummary({
          year: currentYear.value,
          month: currentMonth.value,
        }),
      ])
      monthlyDays.value = calResp.data.days as MonthlyDay[]
      monthlySummary.value = sumResp.data as MonthlySummary
    } catch (error) {
      console.error('获取月度数据失败:', error)
    } finally {
      monthlyLoading.value = false
    }
  }

  /** 选中某日 */
  async function selectDate(dateStr: string) {
    selectedDate.value = dateStr
    dailyDetailLoading.value = true
    try {
      const resp = await wealthApi.getDailyDetail({ date: dateStr })
      currentDailyDetail.value = resp.data as DailyDetail
    } catch (error) {
      console.error('获取日明细失败:', error)
    } finally {
      dailyDetailLoading.value = false
    }
  }

  /** 快速记账 */
  async function createBill(data: BillCreateData) {
    try {
      const resp = await wealthApi.createBill(data)
      // 成功后刷新当月数据
      await fetchMonthlyData()
      // 如果当前有选中日期，刷新明细
      if (selectedDate.value) {
        await selectDate(selectedDate.value)
      }
      return resp.data
    } catch (error) {
      console.error('记账失败:', error)
      throw error
    }
  }

  function resetState() {
    // 周历
    weekData.value = {}
    calendarLoading.value = false
    scenario.value = null
    scenarioLoading.value = false
    coverageSet.value = new Set()
    coverageResult.value = null
    summary.value = null
    summaryLoading.value = false
    selectedWeekIndex.value = null
    selectedWeekData.value = null
    selectedWeekBills.value = []
    weekDetailLoading.value = false
    filterAge.value = undefined
    filterLivedOnly.value = false
    // 月度
    viewMode.value = 'heatmap'
    currentYear.value = new Date().getFullYear()
    currentMonth.value = new Date().getMonth() + 1
    monthlyDays.value = []
    monthlySummary.value = null
    currentDailyDetail.value = null
    selectedDate.value = null
    monthlyLoading.value = false
    dailyDetailLoading.value = false
  }

  return {
    weekData, calendarLoading,
    scenario, scenarioLoading,
    coverageSet, coverageResult,
    summary, summaryLoading,
    selectedWeekIndex, selectedWeekData, selectedWeekBills, weekDetailLoading,
    filterAge, filterLivedOnly,
    fetchCalendar, fetchScenario, runCoverage, fetchSummary,
    selectWeek, clearSelection, resetCoverage, initCalendar,
    // 月度
    viewMode, currentYear, currentMonth,
    monthlyDays, monthlySummary, currentDailyDetail, selectedDate,
    monthlyLoading, dailyDetailLoading,
    setViewMode, navigateMonth, goToToday, goToYearMonth,
    fetchMonthlyData, selectDate, createBill,
    resetState,
  }
})
