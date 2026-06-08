import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as healthApi from '../api/healthApi'
import type {
  CalendarItem, DailyTrendItem, HealthRecord, HealthSummary, MilestoneList,
  MilestoneTimelineItem, TypeStatItem, UserBodyInfo, WeightGoal, WeightMilestone,
  WeightRecord, WeightStats, WeightTrend, YearlyComparisonItem,
} from '../types/healthTypes'

export const useHealthStore = defineStore('health', () => {
  const records = ref<HealthRecord[]>([])
  const totalCount = ref(0)
  const loading = ref(false)
  const summary = ref<HealthSummary | null>(null)
  const milestones = ref<MilestoneList | null>(null)
  const dailyTrend = ref<DailyTrendItem[]>([])
  const typeStats = ref<TypeStatItem[]>([])
  const yearlyComparison = ref<YearlyComparisonItem[]>([])
  const calendarData = ref<CalendarItem[]>([])
  const milestoneTimeline = ref<MilestoneTimelineItem[]>([])

  async function fetchRecords(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await healthApi.getHealthList(params)
      if (res.data.results) {
        records.value = res.data.results
        totalCount.value = res.data.count
      } else if (Array.isArray(res.data)) {
        records.value = res.data
        totalCount.value = res.data.length
      }
      return res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchSummary() {
    const res = await healthApi.getHealthSummary()
    summary.value = res.data
    return res.data
  }

  async function fetchMilestones() {
    const res = await healthApi.getHealthMilestones()
    milestones.value = res.data
    return res.data
  }

  async function fetchDailyTrend(days = 30) {
    const res = await healthApi.getHealthDailyTrend(days)
    dailyTrend.value = res.data
    return res.data
  }

  async function fetchTypeStats() {
    const res = await healthApi.getHealthTypeStats()
    typeStats.value = res.data
    return res.data
  }

  async function fetchYearlyComparison() {
    const res = await healthApi.getHealthYearlyComparison()
    yearlyComparison.value = res.data
    return res.data
  }

  async function fetchCalendar(year?: number, month?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    if (month) params.month = month
    const res = await healthApi.getHealthCalendar(params)
    calendarData.value = res.data
    return res.data
  }

  async function fetchMilestoneTimeline() {
    const res = await healthApi.getHealthMilestoneTimeline()
    milestoneTimeline.value = res.data
    return res.data
  }

  async function fetchAll() {
    await Promise.all([
      fetchSummary(),
      fetchMilestones(),
      fetchDailyTrend(),
      fetchTypeStats(),
      fetchYearlyComparison(),
      fetchMilestoneTimeline(),
      fetchRecords(),
    ])
  }

  return {
    records, totalCount, loading, summary, milestones, dailyTrend,
    typeStats, yearlyComparison, calendarData, milestoneTimeline,
    fetchRecords, fetchSummary, fetchMilestones, fetchDailyTrend,
    fetchTypeStats, fetchYearlyComparison, fetchCalendar,
    fetchMilestoneTimeline, fetchAll,
  }
})

// ─── 体重管理 Store ───

export const useWeightStore = defineStore('weight', () => {
  const records = ref<WeightRecord[]>([])
  const stats = ref<WeightStats | null>(null)
  const trend = ref<WeightTrend | null>(null)
  const goal = ref<WeightGoal | null>(null)
  const milestones = ref<WeightMilestone[]>([])
  const bodyInfo = ref<UserBodyInfo | null>(null)
  const loading = ref(false)

  async function fetchStats() {
    const res = await healthApi.getWeightStats({ user_id: 1 })
    stats.value = res.data
    return res.data
  }

  async function fetchTrend() {
    const res = await healthApi.getWeightTrend({ user_id: 1 })
    trend.value = res.data
    return res.data
  }

  async function fetchGoal() {
    const res = await healthApi.getWeightGoal({ user_id: 1 })
    goal.value = res.data
    return res.data
  }

  async function createGoal(data: Record<string, unknown>) {
    const res = await healthApi.createWeightGoal({ user_id: 1, ...data })
    goal.value = res.data
    return res.data
  }

  async function fetchMilestones() {
    const res = await healthApi.getWeightMilestones({ user_id: 1 })
    milestones.value = res.data
    return res.data
  }

  async function fetchBodyInfo() {
    const res = await healthApi.getWeightBodyInfo({ user_id: 1 })
    bodyInfo.value = res.data
    return res.data
  }

  async function updateBodyInfo(data: Record<string, unknown>) {
    const res = await healthApi.updateWeightBodyInfo({ user_id: 1, ...data })
    bodyInfo.value = res.data
    return res.data
  }

  async function fetchRecords(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await healthApi.getWeightRecords({ user_id: 1, ...params })
      if (res.data.results) {
        records.value = res.data.results
      } else if (Array.isArray(res.data)) {
        records.value = res.data
      }
      return res.data
    } finally {
      loading.value = false
    }
  }

  async function createRecord(data: Record<string, unknown>) {
    const res = await healthApi.createWeightRecord({ user_id: 1, ...data })
    records.value.unshift(res.data)
    return res.data
  }

  async function updateRecord(id: number, data: Record<string, unknown>) {
    const res = await healthApi.updateWeightRecord(id, { user_id: 1, ...data })
    const idx = records.value.findIndex(r => r.id === id)
    if (idx >= 0) records.value[idx] = res.data
    return res.data
  }

  async function deleteRecord(id: number) {
    await healthApi.deleteWeightRecord(id)
    records.value = records.value.filter(r => r.id !== id)
  }

  async function loadAll() {
    await Promise.all([
      fetchStats(),
      fetchTrend(),
      fetchGoal(),
      fetchMilestones(),
      fetchBodyInfo(),
      fetchRecords(),
    ])
  }

  return {
    records, stats, trend, goal, milestones, bodyInfo, loading,
    fetchStats, fetchTrend, fetchGoal, createGoal,
    fetchMilestones, fetchBodyInfo, updateBodyInfo,
    fetchRecords, createRecord, updateRecord, deleteRecord, loadAll,
  }
})
