import { defineStore } from 'pinia'
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
