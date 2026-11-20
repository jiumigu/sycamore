import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as readerApi from '../api/readerApi'
import type { ReaderGroup, ReaderInteraction, ReaderMonthlySummary, ReaderYearlyStats } from '../types/readerTypes'

export const useReaderStore = defineStore('reader', () => {
  const groups = ref<ReaderGroup[]>([])
  const interactions = ref<ReaderInteraction[]>([])
  const resonancePoints = ref<ReaderInteraction[]>([])
  const monthlySummaries = ref<ReaderMonthlySummary[]>([])
  const yearlyStats = ref<ReaderYearlyStats | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const selectedGroupId = ref<number | null>(null)

  // 🔴 上次拉复盘用的筛选条件：保存/删除后必须按同一条件重拉。
  //    否则子组件筛着 2026 年、store 却用无参重拉成「全部年份」，
  //    标题写着「2026年复盘记录」、表里躺着 2025 的行 —— 两处口径不同源，静默错。
  //    用 `{}` 表示「显式不筛」，与 `undefined`（不传=沿用上次）区分开。
  let summaryParams: Record<string, unknown> | undefined
  let statsParams: Record<string, unknown> | undefined

  const formVisible = ref(false)
  const groupFormVisible = ref(false)

  function extractList<T>(data: unknown): T[] {
    if (data && typeof data === 'object' && 'results' in (data as Record<string, unknown>)) {
      return Array.isArray((data as Record<string, unknown>).results)
        ? ((data as Record<string, unknown>).results as T[]).filter(Boolean)
        : []
    }
    return Array.isArray(data) ? (data as T[]).filter(Boolean) : []
  }

  async function fetchGroups() {
    try {
      const res = await readerApi.getReaderGroups()
      groups.value = extractList<ReaderGroup>(res.data)
    } catch (e) {
      console.error('获取读者群体失败:', e)
      groups.value = []
    }
  }

  async function createGroup(data: Record<string, unknown>) {
    saving.value = true
    try {
      await readerApi.createReaderGroup(data)
      groupFormVisible.value = false
      await fetchGroups()
    } finally {
      saving.value = false
    }
  }

  async function deleteGroup(id: number) {
    try {
      await readerApi.deleteReaderGroup(id)
      if (selectedGroupId.value === id) selectedGroupId.value = null
      await fetchGroups()
      await fetchInteractions()
    } catch (e) {
      console.error('删除群体失败:', e)
    }
  }

  async function fetchInteractions(groupId?: number) {
    loading.value = true
    try {
      const res = await readerApi.getReaderInteractions(groupId)
      interactions.value = extractList<ReaderInteraction>(res.data)
    } finally {
      loading.value = false
    }
  }

  async function createInteraction(data: Record<string, unknown>) {
    saving.value = true
    try {
      await readerApi.createReaderInteraction(data)
      formVisible.value = false
      await Promise.all([
        fetchInteractions(selectedGroupId.value || undefined),
        fetchResonancePoints(selectedGroupId.value || undefined),
        fetchGroups(),
      ])
    } finally {
      saving.value = false
    }
  }

  async function deleteInteraction(id: number) {
    try {
      await readerApi.deleteReaderInteraction(id)
      await Promise.all([
        fetchInteractions(selectedGroupId.value || undefined),
        fetchResonancePoints(selectedGroupId.value || undefined),
        fetchGroups(),
      ])
    } catch (e) {
      console.error('删除互动失败:', e)
    }
  }

  async function fetchResonancePoints(groupId?: number) {
    try {
      const res = await readerApi.getResonancePoints(groupId)
      resonancePoints.value = extractList<ReaderInteraction>(res.data)
    } catch (e) {
      console.error('获取共振点失败:', e)
    }
  }

  async function fetchMonthlySummaries(params?: Record<string, unknown>) {
    if (params !== undefined) summaryParams = params
    try {
      const res = await readerApi.getMonthlySummaries(summaryParams)
      monthlySummaries.value = extractList<ReaderMonthlySummary>(res.data)
    } catch (e) {
      console.error('获取月末复盘失败:', e)
      monthlySummaries.value = []
    }
  }

  async function fetchYearlyStats(params?: Record<string, unknown>) {
    if (params !== undefined) statsParams = params
    try {
      const res = await readerApi.getReaderYearlyStats(statsParams)
      yearlyStats.value = res.data
    } catch (e) {
      console.error('获取年度统计失败:', e)
      yearlyStats.value = null
    }
  }

  /**
   * 按年月找一条复盘记录（算「取关」要用上月总关注）。
   * 列表里只有当前筛选年，跨年（1 月要 12 月）会找不到 —— 这里按需补拉那一年并缓存，
   * 别让「找不到」和「上月总关注真是 0」混成同一个结果。
   */
  const monthCache = new Map<string, ReaderMonthlySummary>()
  async function findMonthSummary(
    year: number,
    month: number,
    groupId: number | null,
  ): Promise<ReaderMonthlySummary | null> {
    const key = `${year}-${month}-${groupId}`
    const pick = (rows: ReaderMonthlySummary[]) =>
      rows.find((s) => s.year === year && s.month === month && s.reader_group === groupId) ?? null
    const hit = pick(monthlySummaries.value) ?? monthCache.get(key)
    if (hit) return hit
    try {
      const res = await readerApi.getMonthlySummaries({ year })
      const rows = extractList<ReaderMonthlySummary>(res.data)
      for (const r of rows) monthCache.set(`${r.year}-${r.month}-${r.reader_group}`, r)
      return pick(rows)
    } catch (e) {
      console.error('获取上月复盘失败:', e)
      return null
    }
  }

  async function createMonthlySummary(data: Record<string, unknown>) {
    saving.value = true
    try {
      await readerApi.createMonthlySummary(data)
      monthCache.clear()
      await fetchMonthlySummaries()
      await fetchYearlyStats()
    } finally {
      saving.value = false
    }
  }

  async function updateMonthlySummary(id: number, data: Record<string, unknown>) {
    saving.value = true
    try {
      await readerApi.updateMonthlySummary(id, data)
      monthCache.clear()
      await fetchMonthlySummaries()
      await fetchYearlyStats()
    } finally {
      saving.value = false
    }
  }

  async function deleteMonthlySummary(id: number) {
    try {
      await readerApi.deleteMonthlySummary(id)
      monthCache.clear()
      await fetchMonthlySummaries()
      await fetchYearlyStats()
    } catch (e) {
      console.error('删除盘点失败:', e)
    }
  }

  async function fetchAll() {
    await Promise.all([
      fetchGroups(),
      fetchInteractions(),
      fetchResonancePoints(),
      fetchMonthlySummaries(),
      fetchYearlyStats(),
    ])
  }

  return {
    groups, interactions, resonancePoints,
    monthlySummaries, yearlyStats,
    loading, saving, selectedGroupId,
    formVisible, groupFormVisible,
    fetchGroups, createGroup, deleteGroup,
    fetchInteractions, createInteraction, deleteInteraction,
    fetchResonancePoints, fetchAll,
    fetchMonthlySummaries, fetchYearlyStats, findMonthSummary,
    createMonthlySummary, updateMonthlySummary, deleteMonthlySummary,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useReaderStore, import.meta.hot))
}
