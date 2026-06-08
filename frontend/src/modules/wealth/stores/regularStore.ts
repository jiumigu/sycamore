import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type { RegularItem, RegularStats, ExpiringItem } from '../types/wealthTypes'

export const useRegularStore = defineStore('regular', () => {
  // ─── 状态 ───
  const stats = ref<RegularStats | null>(null)
  const list = ref<RegularItem[]>([])
  const expiringItems = ref<ExpiringItem[]>([])
  const banks = ref<string[]>([])

  const loading = ref(false)
  const saving = ref(false)

  // 筛选条件
  const filterBank = ref('')
  const filterFlag = ref(0)
  const filterKeyword = ref('')

  // 表单弹窗
  const formVisible = ref(false)
  const editingItem = ref<RegularItem | null>(null)

  // 到期处理弹窗
  const matureVisible = ref(false)
  const matureTarget = ref<RegularItem | null>(null)

  // ─── 方法 ───
  async function fetchStats() {
    try {
      const resp = await wealthApi.getRegularStats()
      stats.value = resp.data as RegularStats
    } catch (e) {
      console.error('获取定期存款统计失败:', e)
    }
  }

  async function fetchList() {
    loading.value = true
    try {
      const params: Record<string, string | number> = {}
      if (filterBank.value) params.bankinfo = filterBank.value
      if (filterFlag.value >= 0) params.flag = filterFlag.value
      if (filterKeyword.value) params.keyword = filterKeyword.value

      const resp = await wealthApi.getRegularList(params)
      list.value = resp.data as RegularItem[]
    } catch (e) {
      console.error('获取定期存款列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchExpiring(days = 30) {
    try {
      const resp = await wealthApi.getRegularExpiring({ days })
      expiringItems.value = resp.data as ExpiringItem[]
    } catch (e) {
      console.error('获取到期提醒失败:', e)
    }
  }

  async function fetchBanks() {
    try {
      const resp = await wealthApi.getRegularBanks()
      banks.value = resp.data as string[]
    } catch (e) {
      console.error('获取银行列表失败:', e)
    }
  }

  async function fetchAll() {
    await Promise.all([
      fetchStats(),
      fetchList(),
      fetchExpiring(),
      fetchBanks(),
    ])
  }

  function resetFilters() {
    filterBank.value = ''
    filterFlag.value = 0
    filterKeyword.value = ''
  }

  function openForm(item?: RegularItem) {
    editingItem.value = item || null
    formVisible.value = true
  }

  function closeForm() {
    formVisible.value = false
    editingItem.value = null
  }

  async function saveForm(data: Record<string, unknown>) {
    saving.value = true
    try {
      if (editingItem.value) {
        await wealthApi.updateRegular(editingItem.value.id, data)
      } else {
        await wealthApi.createRegular(data)
      }
      closeForm()
      await fetchAll()
    } catch (e) {
      console.error('保存定期存款失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  async function removeItem(id: number) {
    try {
      await wealthApi.deleteRegular(id)
      await fetchAll()
    } catch (e) {
      console.error('删除定期存款失败:', e)
      throw e
    }
  }

  function openMature(item: RegularItem) {
    matureTarget.value = item
    matureVisible.value = true
  }

  function closeMature() {
    matureVisible.value = false
    matureTarget.value = null
  }

  async function processMature(data: Record<string, unknown>) {
    saving.value = true
    try {
      if (matureTarget.value) {
        await wealthApi.processMature(matureTarget.value.id, data)
      }
      closeMature()
      await fetchAll()
    } catch (e) {
      console.error('到期处理失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  function resetState() {
    stats.value = null
    list.value = []
    expiringItems.value = []
    banks.value = []
    resetFilters()
    closeForm()
    closeMature()
  }

  return {
    stats, list, expiringItems, banks,
    loading, saving,
    filterBank, filterFlag, filterKeyword,
    formVisible, editingItem,
    matureVisible, matureTarget,
    fetchStats, fetchList, fetchExpiring, fetchBanks, fetchAll,
    resetFilters, openForm, closeForm, saveForm, removeItem,
    openMature, closeMature, processMature, resetState,
  }
})
