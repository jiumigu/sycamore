import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sampleApi } from '../api'
import type { LifeSample, LifeSampleForm, ScanResult, Stats, SyncResult } from '../types'

export type SampleQueryParams = { search?: string; type?: string; status?: string; relevance?: string; tag?: string }

export const useSampleStore = defineStore('life-sample', () => {
  const samples = ref<LifeSample[]>([])
  const stats = ref<Stats | null>(null)
  const loading = ref(false)
  const allTags = ref<string[]>([])
  const syncing = ref(false)

  async function fetchSamples(params?: SampleQueryParams) {
    loading.value = true
    try {
      const res = await sampleApi.getList(params)
      samples.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    const res = await sampleApi.getStats()
    stats.value = res.data
  }

  async function fetchTags() {
    const res = await sampleApi.getTags()
    allTags.value = res.data
  }

  async function loadAll(params?: SampleQueryParams) {
    await Promise.all([fetchSamples(params), fetchStats(), fetchTags()])
  }

  async function createSample(data: Partial<LifeSampleForm>) {
    const res = await sampleApi.create(data)
    await loadAll()
    return res.data
  }

  async function updateSample(id: number, data: Partial<LifeSampleForm>) {
    const res = await sampleApi.update(id, data)
    await loadAll()
    return res.data
  }

  async function deleteSample(id: number) {
    await sampleApi.delete(id)
    await loadAll()
  }

  async function scanObsidian(): Promise<ScanResult[]> {
    const res = await sampleApi.scanObsidian()
    return res.data
  }

  async function syncFromObsidian(): Promise<SyncResult> {
    syncing.value = true
    try {
      const res = await sampleApi.syncFromObsidian()
      await loadAll()
      return res.data
    } finally {
      syncing.value = false
    }
  }

  function getSampleTypeLabel(type: string): string {
    const labels: Record<string, string> = {
      acquaintance: '熟人',
      online: '网友',
      historical: '历史人物',
      celebrity: '知名人士',
      fictional: '虚构人物',
    }
    return labels[type] || type
  }

  return {
    samples,
    stats,
    loading,
    allTags,
    syncing,
    fetchSamples,
    fetchStats,
    fetchTags,
    loadAll,
    createSample,
    updateSample,
    deleteSample,
    scanObsidian,
    syncFromObsidian,
    getSampleTypeLabel,
  }
})
