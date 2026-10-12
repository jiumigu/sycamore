import { acceptHMRUpdate, defineStore } from 'pinia'
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

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useConflictStore, import.meta.hot))
}
