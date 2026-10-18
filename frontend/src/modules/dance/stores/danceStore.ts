import { acceptHMRUpdate, defineStore } from 'pinia'
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

  /// 🔴 `recordParams` 必须能传进来（**页码** / 年份 / 各筛选）：
  /// 记录列表走 DRF 全局分页，不传 `page` 就永远只有第 1 页，
  /// 而 `totalCount` 是全量 ⇒ 分页条按全量渲染页数、翻页却全空（v3.62.14 修）。
  /// ⚠️ 年份**只从 `recordParams` 里取**：趋势图与记录列表用同一个 year，
  ///    两处各传一次就会「图是 2025、表是 2026」且不报错。
  async function fetchAll(recordParams?: Record<string, unknown>) {
    const year = recordParams?.year as number | undefined
    await Promise.all([
      fetchOverview(),
      fetchTrend(year),
      fetchTeachers(),
      fetchTypes(),
      fetchScoreTrend(),
      fetchRecords({ year, ...recordParams }),
    ])
  }

  return {
    records, totalCount, loading, overview, trendData, teachers, typeStats, scoreTrend, calendarData,
    fetchRecords, fetchOverview, fetchTrend, fetchTeachers, fetchTypes, fetchScoreTrend, fetchCalendar, fetchAll,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDanceStore, import.meta.hot))
}
