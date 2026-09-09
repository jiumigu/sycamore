import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  MonthlyDay, DailyDetail, MonthlySummary, BillCreateData,
} from '../types/wealthTypes'

export const useWealthStore = defineStore('wealth', () => {
  // ─── 月度日历状态 ───
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

  // ─── 月度日历方法 ───

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
    currentYear, currentMonth,
    monthlyDays, monthlySummary, currentDailyDetail, selectedDate,
    monthlyLoading, dailyDetailLoading,
    navigateMonth, goToToday, goToYearMonth,
    fetchMonthlyData, selectDate, createBill,
    resetState,
  }
})
