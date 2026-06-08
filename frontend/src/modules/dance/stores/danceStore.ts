import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as danceApi from '../api/danceApi'
import type { CalendarItem, DanceOverview, DanceRecord, DanceTypeStat, ScoreTrendItem, TeacherStat, TrendData } from '../types/danceTypes'

export const useDanceStore = defineStore('dance', () => {
  const records = ref<DanceRecord[]>([])
  const totalCount = ref(0)
  const loading = ref(false)
  const overview = ref<DanceOverview | null>(null)
  const trendData = ref<TrendData | null>(null)
  const teachers = ref<TeacherStat[]>([])
  const typeStats = ref<DanceTypeStat[]>([])
  const scoreTrend = ref<ScoreTrendItem[]>([])
  const calendarData = ref<CalendarItem[]>([])

  async function fetchRecords(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await danceApi.getDanceList(params)
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

  async function fetchOverview() {
    const res = await danceApi.getDanceStats()
    overview.value = res.data
    return res.data
  }

  async function fetchTrend(year?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    const res = await danceApi.getDanceTrend(params)
    trendData.value = res.data
    return res.data
  }

  async function fetchTeachers() {
    const res = await danceApi.getDanceTeachers()
    teachers.value = res.data
    return res.data
  }

  async function fetchTypes() {
    const res = await danceApi.getDanceTypes()
    typeStats.value = res.data
    return res.data
  }

  async function fetchScoreTrend() {
    const res = await danceApi.getDanceScoreTrend()
    scoreTrend.value = res.data
    return res.data
  }

  async function fetchCalendar(year?: number, month?: number) {
    const params: Record<string, unknown> = {}
    if (year) params.year = year
    if (month) params.month = month
    const res = await danceApi.getDanceCalendar(params)
    calendarData.value = res.data
    return res.data
  }

  async function fetchAll(year?: number) {
    await Promise.all([
      fetchOverview(),
      fetchTrend(year),
      fetchTeachers(),
      fetchTypes(),
      fetchScoreTrend(),
      fetchRecords({ year }),
    ])
  }

  return {
    records, totalCount, loading, overview, trendData, teachers, typeStats, scoreTrend, calendarData,
    fetchRecords, fetchOverview, fetchTrend, fetchTeachers, fetchTypes, fetchScoreTrend, fetchCalendar, fetchAll,
  }
})
