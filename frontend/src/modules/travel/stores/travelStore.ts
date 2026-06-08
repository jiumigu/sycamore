import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../api/travelApi'
import type { TravelRecord, MapData, TravelStats } from '../types/travelTypes'

export const useTravelStore = defineStore('travel', () => {
  const records = ref<TravelRecord[]>([])
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(10)
  const mapData = ref<MapData | null>(null)
  const stats = ref<TravelStats | null>(null)
  const years = ref<number[]>([])
  const loading = ref(false)

  async function fetchRecords(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const mergedParams = {
        page: currentPage.value,
        page_size: pageSize.value,
        ...params,
      } as Record<string, unknown>
      const res = await api.getTravelRecords(mergedParams)
      if (res.data && 'results' in res.data) {
        records.value = res.data.results || []
        total.value = res.data.count ?? 0
      } else {
        records.value = res.data || []
        total.value = (res.data || []).length
      }
      return res.data
    } finally {
      loading.value = false
    }
  }

  function setPage(page: number) {
    currentPage.value = page
    fetchRecords()
  }

  async function fetchMapData(yearFrom?: number, yearTo?: number) {
    const params: Record<string, unknown> = {}
    if (yearFrom) params.year_from = yearFrom
    if (yearTo) params.year_to = yearTo
    const res = await api.getMapData(params)
    mapData.value = res.data
    return res.data
  }

  async function fetchStats(yearFrom?: number, yearTo?: number) {
    const params: Record<string, unknown> = {}
    if (yearFrom) params.year_from = yearFrom
    if (yearTo) params.year_to = yearTo
    const res = await api.getTravelStats(params)
    stats.value = res.data
    return res.data
  }

  async function fetchYears() {
    const res = await api.getYearList()
    years.value = (res.data || []).map((y: { year: number }) => y.year)
    return years.value
  }

  async function createRecord(data: Record<string, unknown>) {
    const res = await api.createTravelRecord(data as any)
    await fetchRecords()
    return res.data
  }

  async function updateRecord(id: number, data: Record<string, unknown>) {
    const res = await api.updateTravelRecord(id, data as any)
    await fetchRecords()
    return res.data
  }

  async function deleteRecord(id: number) {
    await api.deleteTravelRecord(id)
    await fetchRecords()
  }

  return {
    records, total, currentPage, pageSize, mapData, stats, years, loading,
    fetchRecords, setPage, fetchMapData, fetchStats, fetchYears,
    createRecord, updateRecord, deleteRecord,
  }
})
