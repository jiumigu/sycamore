import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as foodApi from '../api/foodApi'
import type { FoodRecord, FoodRecordList, FoodStats } from '../types/foodTypes'

export const useFoodStore = defineStore('food', () => {
  const records = ref<FoodRecordList[]>([])
  const currentRecord = ref<FoodRecord | null>(null)
  const stats = ref<FoodStats | null>(null)
  const maps = ref<Record<string, unknown>[]>([])
  const tags = ref<{ name: string; count: number }[]>([])
  const loading = ref(false)
  const submitting = ref(false)

  async function fetchRecords(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await foodApi.getFoodList(params)
      const data = res.data
      if (data.results) {
        records.value = data.results
      } else if (Array.isArray(data)) {
        records.value = data
      }
      return data
    } catch (error) {
      console.error('获取美食列表失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const res = await foodApi.getFoodStats()
      stats.value = res.data
    } catch { /* ignore */ }
  }

  async function createRecord(data: Record<string, unknown>) {
    submitting.value = true
    try {
      const res = await foodApi.createFood(data)
      return res.data
    } catch (error) {
      console.error('创建美食记录失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function updateRecord(id: number, data: Record<string, unknown>) {
    submitting.value = true
    try {
      const res = await foodApi.updateFood(id, data)
      return res.data
    } catch (error) {
      console.error('更新美食记录失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function deleteRecord(id: number) {
    try {
      await foodApi.deleteFood(id)
      records.value = records.value.filter(r => r.id !== id)
    } catch (error) {
      console.error('删除美食记录失败:', error)
      throw error
    }
  }

  async function refreshAll() {
    await Promise.all([
      fetchRecords(),
      fetchStats(),
    ])
  }

  return {
    records, currentRecord, stats, maps, tags, loading, submitting,
    fetchRecords, fetchStats, createRecord, updateRecord, deleteRecord, refreshAll,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useFoodStore, import.meta.hot))
}
