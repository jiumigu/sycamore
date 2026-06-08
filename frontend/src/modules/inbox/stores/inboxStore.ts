import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import * as inboxApi from '../api/inboxApi'
import type { InboxItem, InboxStats } from '../types/inboxTypes'

export const useInboxStore = defineStore('inbox', () => {
  const items = ref<InboxItem[]>([])
  const stats = ref<InboxStats | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const filterStatus = ref('pending')
  const filterCategory = ref('')
  const filterPriority = ref('')
  const searchQuery = ref('')
  const currentPage = ref(1)
  const pageSize = ref(10)
  const total = ref(0)

  const formVisible = ref(false)
  const detailVisible = ref(false)
  const convertVisible = ref(false)
  const selectedItem = ref<InboxItem | null>(null)
  const selectedIds = ref<Set<number>>(new Set())

  function extractList<T>(data: unknown): T[] {
    if (data && typeof data === 'object' && 'results' in (data as Record<string, unknown>)) {
      return Array.isArray((data as Record<string, unknown>).results)
        ? ((data as Record<string, unknown>).results as T[]).filter(Boolean)
        : []
    }
    return Array.isArray(data) ? (data as T[]).filter(Boolean) : []
  }

  async function fetchItems() {
    loading.value = true
    try {
      const params: Record<string, unknown> = {
        page: currentPage.value,
        page_size: pageSize.value,
      }
      if (filterStatus.value) params.status = filterStatus.value
      if (filterCategory.value) params.category = filterCategory.value
      if (filterPriority.value) params.priority = filterPriority.value
      if (searchQuery.value) params.search = searchQuery.value

      const res = await inboxApi.getInboxItems(params)
      items.value = extractList<InboxItem>(res.data)
      total.value = res.data?.count ?? 0
    } catch (e) {
      console.error('获取收件箱失败:', e)
      items.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(page: number) {
    currentPage.value = page
    fetchItems()
  }

  function resetPage() {
    currentPage.value = 1
  }

  /** 按当前筛选条件搜索（重置到第 1 页） */
  async function search() {
    resetPage()
    await fetchItems()
  }

  async function fetchStats() {
    try {
      const res = await inboxApi.getInboxStats()
      stats.value = res.data as InboxStats
    } catch (e) {
      console.error('获取统计失败:', e)
      stats.value = null
    }
  }

  async function createItem(data: Record<string, unknown>) {
    saving.value = true
    try {
      await inboxApi.createInboxItem(data)
      formVisible.value = false
      await Promise.all([fetchItems(), fetchStats()])
      ElMessage.success('创建成功')
    } catch (e) {
      ElMessage.error('创建失败，请重试')
      console.error('创建失败:', e)
    } finally {
      saving.value = false
    }
  }

  async function updateItem(id: number, data: Record<string, unknown>) {
    saving.value = true
    try {
      await inboxApi.updateInboxItem(id, data)
      detailVisible.value = false
      selectedItem.value = null
      await Promise.all([fetchItems(), fetchStats()])
      ElMessage.success('保存成功')
    } catch (e) {
      ElMessage.error('保存失败，请重试')
      console.error('更新失败:', e)
    } finally {
      saving.value = false
    }
  }

  async function deleteItem(id: number) {
    try {
      await inboxApi.deleteInboxItem(id)
      selectedIds.value.delete(id)
      await Promise.all([fetchItems(), fetchStats()])
    } catch (e) {
      console.error('删除失败:', e)
    }
  }

  async function completeItem(id: number, completion_note?: string) {
    const data = completion_note ? { completion_note } : undefined
    await inboxApi.completeInboxItem(id, data)
    await Promise.all([fetchItems(), fetchStats()])
  }

  async function convertItem(id: number, action: string, extra?: Record<string, unknown>) {
    try {
      await inboxApi.convertInboxItem(id, { action, ...extra })
      convertVisible.value = false
      selectedItem.value = null
      await Promise.all([fetchItems(), fetchStats()])
    } catch (e) {
      console.error('转换失败:', e)
    }
  }

  async function convertToGoal(itemIds: number[], goalName: string, year?: number, reward?: number) {
    saving.value = true
    try {
      const res = await inboxApi.convertToGoal({
        item_ids: itemIds,
        goal_name: goalName,
        year,
        reward_per_milestone: reward,
      })
      items.value = items.value.filter(i => !itemIds.includes(i.id))
      selectedIds.value = new Set()
      await fetchStats()
      return res.data
    } finally {
      saving.value = false
    }
  }

  async function batchAction(data: { ids: number[]; action: string }) {
    try {
      await inboxApi.batchAction(data as Parameters<typeof inboxApi.batchAction>[0])
      selectedIds.value = new Set()
      await Promise.all([fetchItems(), fetchStats()])
    } catch (e) {
      console.error('批量操作失败:', e)
    }
  }

  async function fetchAll() {
    await Promise.all([fetchItems(), fetchStats()])
  }

  const pendingCount = computed(() => stats.value?.pending ?? 0)
  const overdueCount = computed(() => stats.value?.overdue ?? 0)

  return {
    items, stats, loading, saving,
    filterStatus, filterCategory, filterPriority, searchQuery,
    formVisible, detailVisible, convertVisible,
    selectedItem, selectedIds,
    pendingCount, overdueCount,
    currentPage, pageSize, total,
    fetchItems, fetchStats, fetchAll,
    createItem, updateItem, deleteItem,
    completeItem, convertItem, convertToGoal, batchAction,
    handlePageChange, resetPage, search,
  }
})
