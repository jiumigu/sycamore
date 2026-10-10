import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  LiabilityItem, LiabilitySummary, LiabilityFormData,
  ReceivableItem, ReceivableSummary, ReceivableFormData,
} from '../types/wealthTypes'

/**
 * 负债明细 / 应收账龄台账状态（P1-A）
 *
 * 与 cashflowStore 分开：那边管快照盘点（每月一次），这边管逐笔台账（随时增删改），
 * 生命周期与刷新时机不同 —— 合并会导致「改一笔负债触发全页重拉」。
 */
export const useDebtStore = defineStore('debt', () => {
  // ─── 状态 ───
  const liabilityList = ref<LiabilityItem[]>([])
  const liabilitySummary = ref<LiabilitySummary | null>(null)
  const receivableList = ref<ReceivableItem[]>([])
  const receivableSummary = ref<ReceivableSummary | null>(null)

  const loading = ref(false)
  const saving = ref(false)

  // ─── 取数 ───
  async function fetchLiabilities(params?: { status?: string; category?: string }) {
    loading.value = true
    try {
      const [listResp, summaryResp] = await Promise.all([
        wealthApi.getLiabilityList(params),
        wealthApi.getLiabilitySummary(),
      ])
      liabilityList.value = listResp.data as LiabilityItem[]
      liabilitySummary.value = summaryResp.data as LiabilitySummary
    } catch (e) {
      console.error('获取负债台账失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchReceivables(params?: { status?: string; aging_bucket?: string }) {
    loading.value = true
    try {
      const [listResp, summaryResp] = await Promise.all([
        wealthApi.getReceivableList(params),
        wealthApi.getReceivableSummary(),
      ])
      receivableList.value = listResp.data as ReceivableItem[]
      receivableSummary.value = summaryResp.data as ReceivableSummary
    } catch (e) {
      console.error('获取应收台账失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchAll() {
    await Promise.all([fetchLiabilities(), fetchReceivables()])
  }

  // ─── 写入 ───
  async function saveLiability(data: LiabilityFormData) {
    saving.value = true
    try {
      if (data.id) {
        await wealthApi.updateLiability(data)
      } else {
        await wealthApi.createLiability(data)
      }
      await fetchLiabilities()
    } catch (e) {
      console.error('保存负债记录失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  async function removeLiability(id: number) {
    try {
      await wealthApi.deleteLiability(id)
      await fetchLiabilities()
    } catch (e) {
      console.error('删除负债记录失败:', e)
      throw e
    }
  }

  async function saveReceivable(data: ReceivableFormData) {
    saving.value = true
    try {
      if (data.id) {
        await wealthApi.updateReceivable(data)
      } else {
        await wealthApi.createReceivable(data)
      }
      await fetchReceivables()
    } catch (e) {
      console.error('保存应收记录失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  async function removeReceivable(id: number) {
    try {
      await wealthApi.deleteReceivable(id)
      await fetchReceivables()
    } catch (e) {
      console.error('删除应收记录失败:', e)
      throw e
    }
  }

  function resetState() {
    liabilityList.value = []
    liabilitySummary.value = null
    receivableList.value = []
    receivableSummary.value = null
  }

  return {
    liabilityList, liabilitySummary, receivableList, receivableSummary,
    loading, saving,
    fetchLiabilities, fetchReceivables, fetchAll,
    saveLiability, removeLiability, saveReceivable, removeReceivable,
    resetState,
  }
})
