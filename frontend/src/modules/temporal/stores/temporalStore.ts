import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as temporalApi from '../api/temporalApi'
import type {
  BalanceData, CalendarDay, CompletenessData, DistributionData,
  ImportResult, OneDayPage, OneDayPageStats, RankingItem, SunburstData,
  TaskOverview, TemporalTask, TrendItem, WeeklyStructure,
} from '../types/temporalTypes'

export const useTemporalStore = defineStore('temporal', () => {
  // ─── OneDay ───
  const onedayList = ref<OneDayPage[]>([])
  const stats = ref<OneDayPageStats | null>(null)
  const loading = ref(false)
  const submitting = ref(false)
  const totalCount = ref(0)

  async function fetchOneDayList(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const response = await temporalApi.getOneDayList(params)
      if (response.data.results) {
        onedayList.value = response.data.results
        totalCount.value = response.data.count
      } else if (Array.isArray(response.data)) {
        onedayList.value = response.data
        totalCount.value = response.data.length
      }
      return response.data
    } catch (error) {
      console.error('获取每日记录失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await temporalApi.getOneDayStats()
      stats.value = response.data
      return response.data
    } catch (error) {
      console.error('获取统计失败:', error)
      throw error
    }
  }

  async function createOneDay(data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await temporalApi.createOneDay(data)
      return response.data
    } catch (error) {
      console.error('创建记录失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function updateOneDay(id: number, data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await temporalApi.updateOneDay(id, data)
      return response.data
    } catch (error) {
      console.error('更新记录失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function deleteOneDay(id: number) {
    try {
      await temporalApi.deleteOneDay(id)
      onedayList.value = onedayList.value.filter(item => item.oid !== id)
      return true
    } catch (error) {
      console.error('删除记录失败:', error)
      throw error
    }
  }

  async function bulkDeleteOneDay(ids: number[]) {
    try {
      await temporalApi.bulkDeleteOneDay(ids)
      onedayList.value = onedayList.value.filter(item => !ids.includes(item.oid))
      return true
    } catch (error) {
      console.error('批量删除失败:', error)
      throw error
    }
  }

  // ─── 任务时间追踪 ───
  const taskList = ref<TemporalTask[]>([])
  const taskTotal = ref(0)
  const taskLoading = ref(false)
  const overview = ref<TaskOverview | null>(null)
  const trendData = ref<TrendItem[]>([])
  const balanceData = ref<BalanceData | null>(null)
  const rankingData = ref<RankingItem[]>([])
  const distributionData = ref<DistributionData | null>(null)
  const calendarData = ref<CalendarDay[]>([])

  // ─── 三层分类（L1 归因 / L2 类型 / L3 task_name）───
  const unclassified = ref<{ count: number; items: Array<{ task_name: string; total_hours: number; record_count: number }> }>({ count: 0, items: [] })
  const completeness = ref<CompletenessData | null>(null)
  const sunburst = ref<SunburstData | null>(null)
  const weeklyStructure = ref<WeeklyStructure | null>(null)

  async function fetchTaskList(params?: Record<string, unknown>) {
    taskLoading.value = true
    try {
      const res = await temporalApi.getTaskList(params)
      if (res.data.results) {
        taskList.value = res.data.results
        taskTotal.value = res.data.count
      } else {
        taskList.value = res.data
        taskTotal.value = res.data.length
      }
    } finally {
      taskLoading.value = false
    }
  }

  async function loadUnclassified(params?: Record<string, unknown>) {
    const res = await temporalApi.getUnclassified(params)
    unclassified.value = res.data
    return res.data
  }

  async function batchSetMeta(data: Record<string, unknown>) {
    const res = await temporalApi.batchSetMeta(data)
    return res.data
  }

  async function fetchSunburst(year?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    const res = await temporalApi.getSunburst(params)
    sunburst.value = res.data
    return res.data
  }

  async function fetchCompleteness(year?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    const res = await temporalApi.getCompleteness(params)
    completeness.value = res.data
    return res.data
  }

  async function fetchWeeklyStructure(year?: number, weeks = 12) {
    const params: Record<string, unknown> = { weeks }
    if (year) params.year = year
    const res = await temporalApi.getWeeklyStructure(params)
    weeklyStructure.value = res.data
    return res.data
  }

  async function fetchOverview(year?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    const res = await temporalApi.getTaskStats(params)
    overview.value = res.data
    completeness.value = res.data.completeness ?? null
    return res.data
  }

  async function fetchTrend(year?: number, group?: string) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    if (group) params.group = group
    const res = await temporalApi.getTaskTrend(params)
    trendData.value = res.data
    return res.data
  }

  async function fetchBalance(year?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    const res = await temporalApi.getTaskBalance(params)
    balanceData.value = res.data
    return res.data
  }

  async function fetchRanking(year?: number, limit?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    if (limit) params.limit = limit
    const res = await temporalApi.getTaskRanking(params)
    rankingData.value = res.data
    return res.data
  }

  async function fetchDistribution(year?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    const res = await temporalApi.getTaskDistribution(params)
    distributionData.value = res.data
    return res.data
  }

  async function fetchCalendar(year?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    const res = await temporalApi.getTaskCalendar(params)
    calendarData.value = res.data
    return res.data
  }

  async function importCsv(file: File) {
    const form = new FormData()
    form.append('file', file)
    const res = await temporalApi.importTaskCsv(form)
    return res.data as ImportResult
  }

  async function fetchAllTaskData(year?: number) {
    await Promise.all([
      fetchOverview(year),
      fetchTrend(year),
      fetchBalance(year),
      fetchRanking(year),
      fetchDistribution(year),
      fetchCalendar(year),
    ])
  }

  function resetState() {
    onedayList.value = []
    stats.value = null
    loading.value = false
    submitting.value = false
    totalCount.value = 0
    taskList.value = []
    overview.value = null
    trendData.value = []
    balanceData.value = null
    rankingData.value = []
    distributionData.value = null
    calendarData.value = []
    unclassified.value = { count: 0, items: [] }
    completeness.value = null
    sunburst.value = null
    weeklyStructure.value = null
  }

  return {
    onedayList, stats, loading, submitting, totalCount,
    fetchOneDayList, fetchStats, createOneDay, updateOneDay, deleteOneDay, bulkDeleteOneDay,
    taskList, taskTotal, taskLoading, overview, trendData, balanceData, rankingData, distributionData, calendarData,
    fetchTaskList, fetchOverview, fetchTrend, fetchBalance, fetchRanking, fetchDistribution, fetchCalendar,
    fetchAllTaskData, importCsv,
    unclassified, completeness, sunburst, weeklyStructure,
    loadUnclassified, batchSetMeta, fetchSunburst, fetchCompleteness, fetchWeeklyStructure,
    resetState,
  }
})
