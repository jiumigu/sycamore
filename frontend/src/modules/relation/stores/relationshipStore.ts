import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../api/relationshipApi'
import type {
  Relationship, Interaction, StatsOverview, QualityDistribution,
  EnergyTrendItem, InteractionFrequency, DueReminder, LocationStatsData,
} from '../types/relationshipTypes'

export const useRelationshipStore = defineStore('relationship', () => {
  const relationships = ref<Relationship[]>([])
  const totalCount = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(12)
  const loading = ref(false)
  const overview = ref<StatsOverview | null>(null)
  const qualityDistribution = ref<QualityDistribution[]>([])
  const energyTrend = ref<EnergyTrendItem[]>([])
  const interactionFrequency = ref<InteractionFrequency[]>([])
  const dueReminders = ref<DueReminder[]>([])
  const locationStats = ref<LocationStatsData | null>(null)

  async function fetchRelationships(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await api.getRelationshipList({
        page: currentPage.value,
        page_size: pageSize.value,
        ...params,
      })
      if (res.data.results) {
        relationships.value = res.data.results
        totalCount.value = res.data.count
      } else if (Array.isArray(res.data)) {
        relationships.value = res.data
        totalCount.value = res.data.length
      }
      return res.data
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(page: number) {
    currentPage.value = page
    fetchRelationships()
  }

  async function fetchOverview() {
    const res = await api.getStatsOverview()
    overview.value = res.data
    return res.data
  }

  async function fetchQualityDistribution() {
    const res = await api.getQualityDistribution()
    qualityDistribution.value = res.data
    return res.data
  }

  async function fetchEnergyTrend(days = 90) {
    const res = await api.getEnergyTrend(days)
    energyTrend.value = res.data
    return res.data
  }

  async function fetchInteractionFrequency(months = 6) {
    const res = await api.getInteractionFrequency(months)
    interactionFrequency.value = res.data
    return res.data
  }

  async function fetchDueReminders() {
    const res = await api.getDueReminders()
    dueReminders.value = res.data
    return res.data
  }

  async function fetchLocationStats() {
    const res = await api.getLocationStats()
    locationStats.value = res.data
    return res.data
  }

  async function fetchAll() {
    await Promise.all([
      fetchRelationships(),
      fetchOverview(),
      fetchQualityDistribution(),
      fetchEnergyTrend(),
      fetchInteractionFrequency(),
      fetchDueReminders(),
    ])
  }

  return {
    relationships, totalCount, currentPage, pageSize, loading,
    overview, qualityDistribution, energyTrend, interactionFrequency,
    dueReminders, locationStats,
    fetchRelationships, handlePageChange,
    fetchOverview, fetchQualityDistribution,
    fetchEnergyTrend, fetchInteractionFrequency, fetchDueReminders,
    fetchLocationStats, fetchAll,
  }
})
