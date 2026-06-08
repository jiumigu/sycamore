import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '../api/conflictApi'
import * as relApi from '../api/relationshipApi'
import type { ConflictEvent, ConflictStats } from '../types/conflictTypes'
import type { Relationship } from '../types/relationshipTypes'

export const useConflictStore = defineStore('conflict', () => {
  const events = ref<ConflictEvent[]>([])
  const stats = ref<ConflictStats | null>(null)
  const contacts = ref<Relationship[]>([])
  const loading = ref(false)

  async function fetchEvents(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await api.getConflictList(params)
      events.value = res.data.results || res.data
      return res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchStats(params?: Record<string, unknown>) {
    const res = await api.getConflictStats(params)
    stats.value = res.data
    return res.data
  }

  async function fetchContacts() {
    const res = await relApi.getRelationshipList({ page_size: 200 })
    contacts.value = res.data.results || []
    return contacts.value
  }

  async function createEvent(data: Record<string, unknown>) {
    const res = await api.createConflict(data)
    await fetchEvents()
    await fetchStats()
    return res.data
  }

  async function fetchAll() {
    await Promise.all([
      fetchEvents(),
      fetchStats(),
      fetchContacts(),
    ])
  }

  return {
    events, stats, contacts, loading,
    fetchEvents, fetchStats, fetchContacts,
    createEvent, fetchAll,
  }
})
