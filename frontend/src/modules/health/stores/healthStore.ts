import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as healthApi from '../api/healthApi'
import type {
  CalendarItem, DailyTrendItem, HealthRecord, HealthSummary, MilestoneList,
  MilestoneTimelineItem, TypeStatItem, UserBodyInfo, WeightGoal, WeightGoalAdjustment,
  WeightMilestone, WeightRecord, WeightStats, WeightTrend, YearlyComparisonItem,
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

  // ⚠️ 下面四个（`dailyTrend` / `typeStats` / `calendarData` / `milestoneTimeline`）
  //    后端接口都还在，但**当前没有任何页面渲染它们**（调用方为零）。
  //    本轮刻意不删：它们是接口层封装，删之前得先定「这几个统计块是不要了、还是还没做」
  //    —— 属产品决定，不在一轮布局调整里顺手砍。已记入当日日志待办。
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

  /**
   * 总览页要的三件事：进度条（`summary`）、里程碑地图、年度对比。
   *
   * 🔴 与「记录列表」**分开取**，别合成一个 `fetchAll()`：
   *    首页只要记录、总览页只要这三样，**没有任何一个页面需要「一次全拿」**。
   *    （原来那个混着 `fetchRecords` 的 `fetchAll()` 已随本次拆分删掉 ——
   *     它唯一的调用方是首页，而首页现在只剩记录列表。）
   */
  async function fetchOverview() {
    await Promise.all([
      fetchSummary(),
      fetchMilestones(),
      fetchYearlyComparison(),
    ])
  }

  return {
    records, totalCount, loading, summary, milestones, dailyTrend,
    typeStats, yearlyComparison, calendarData, milestoneTimeline,
    fetchRecords, fetchSummary, fetchMilestones, fetchDailyTrend,
    fetchTypeStats, fetchYearlyComparison, fetchCalendar,
    fetchMilestoneTimeline, fetchOverview,
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
  const adjustments = ref<WeightGoalAdjustment[]>([])
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

  async function fetchAdjustments() {
    const res = await healthApi.getWeightAdjustments({ user_id: 1 })
    adjustments.value = res.data
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
      fetchAdjustments(),
      fetchRecords(),
    ])
  }

  return {
    records, stats, trend, goal, milestones, bodyInfo, adjustments, loading,
    fetchStats, fetchTrend, fetchGoal, createGoal,
    fetchMilestones, fetchBodyInfo, updateBodyInfo, fetchAdjustments,
    fetchRecords, createRecord, updateRecord, deleteRecord, loadAll,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板新、数据旧，看起来像「功能没做」）。
// ⚠️ 本模块导出**两个** store，不能直接 `acceptHMRUpdate(useA, hot)` + `acceptHMRUpdate(useB, hot)`：
//    它的回调会遍历新模块的**全部**导出，遇到 id 不同的那个就 `console.warn` + `invalidate()`
//    （整页刷新）—— 等于没加固，还多一条误导性警告。
//    ⇒ 各包一层，让每次回调只看得见自己那一个。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  const hmrHealthStore = acceptHMRUpdate(useHealthStore, import.meta.hot)
  const hmrWeightStore = acceptHMRUpdate(useWeightStore, import.meta.hot)
  import.meta.hot.accept((mod) => {
    // ⚠️ Vite 的签名是 `accept(cb?: (mod?: any) => void)` —— `mod` 类型上是**可选**的。
    //    真拿不到模块时直接不动，别把 `undefined` 喂给 rebuild（它会 `for...in` 一个 undefined）。
    if (!mod) return
    hmrHealthStore({ useHealthStore: mod.useHealthStore })
    hmrWeightStore({ useWeightStore: mod.useWeightStore })
  })
}
