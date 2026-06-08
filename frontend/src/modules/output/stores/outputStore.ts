import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as outputApi from '../api/outputApi'
import type { OutputRecord, OutputStats } from '../types/outputTypes'

export const useOutputStore = defineStore('output', () => {
  const records = ref<OutputRecord[]>([])
  const stats = ref<OutputStats | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const filterCategory = ref('')
  const filterQuality = ref('')
  const filterYear = ref(new Date().getFullYear())

  async function fetchRecords() {
    loading.value = true
    try {
      const params: Record<string, string> = {}
      if (filterCategory.value) params.category = filterCategory.value
      if (filterQuality.value) params.quality = filterQuality.value
      if (filterYear.value) params.year = String(filterYear.value)

      const res = await outputApi.getOutputRecords(params)
      records.value = (res.data.results || res.data) as OutputRecord[]
    } catch (e) {
      console.error('获取产出记录失败:', e)
      records.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const params: Record<string, string> = {}
      if (filterYear.value) params.year = String(filterYear.value)
      const res = await outputApi.getOutputStats(params)
      stats.value = res.data as OutputStats
    } catch (e) {
      console.error('获取良品率统计失败:', e)
    }
  }

  async function createRecord(data: Record<string, unknown>) {
    saving.value = true
    try {
      await outputApi.createOutputRecord(data)
      await Promise.all([fetchRecords(), fetchStats()])
      ElMessage.success('记录已保存')
    } catch (e) {
      ElMessage.error('保存失败')
      console.error('创建失败:', e)
    } finally {
      saving.value = false
    }
  }

  async function updateRecord(id: number, data: Record<string, unknown>) {
    saving.value = true
    try {
      await outputApi.updateOutputRecord(id, data)
      await Promise.all([fetchRecords(), fetchStats()])
      ElMessage.success('已更新')
    } catch (e) {
      ElMessage.error('更新失败')
      console.error('更新失败:', e)
    } finally {
      saving.value = false
    }
  }

  async function deleteRecord(id: number) {
    try {
      await outputApi.deleteOutputRecord(id)
      records.value = records.value.filter(r => r.id !== id)
      await fetchStats()
    } catch (e) {
      console.error('删除失败:', e)
    }
  }

  async function fetchAll() {
    await Promise.all([fetchRecords(), fetchStats()])
  }

  return {
    records, stats, loading, saving,
    filterCategory, filterQuality, filterYear,
    fetchRecords, fetchStats, fetchAll,
    createRecord, updateRecord, deleteRecord,
  }
})
