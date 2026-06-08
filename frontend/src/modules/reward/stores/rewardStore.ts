import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as rewardApi from '../api/rewardApi'
import type { RewardPool, RewardTransaction, RewardSourceStats, GiftList, GiftStats } from '../types/rewardTypes'

export const useRewardStore = defineStore('reward', () => {
  const pool = ref<RewardPool>({ balance: 0, total_earned: 0, total_withdrawn: 0 })
  const sourceStats = ref<RewardSourceStats | null>(null)
  const transactions = ref<RewardTransaction[]>([])
  const txTotal = ref(0)
  const gifts = ref<GiftList[]>([])
  const giftStats = ref<GiftStats | null>(null)
  const loading = ref(false)

  async function fetchPool() {
    try {
      const res = await rewardApi.getRewardPool()
      pool.value = res.data
    } catch { /* ignore */ }
  }

  async function fetchSourceStats() {
    try {
      const res = await rewardApi.getRewardSourceStats()
      sourceStats.value = res.data
    } catch { /* ignore */ }
  }

  async function fetchTransactions(params?: { type?: string; source_type?: string; page?: number; page_size?: number }) {
    try {
      const res = await rewardApi.getRewardTransactions(params || { page: 1, page_size: 1000 })
      const data = res.data
      transactions.value = (data.items || []).map((tx: RewardTransaction) => ({
        ...tx,
        amount: Number(tx.amount) || 0,
        balance_before: Number(tx.balance_before) || 0,
        balance_after: Number(tx.balance_after) || 0,
      }))
      txTotal.value = data.total || 0
    } catch {
      transactions.value = []
      txTotal.value = 0
    }
  }

  async function fetchGifts(params?: { status?: string; category?: string }) {
    try {
      const res = await rewardApi.getGiftList(params)
      gifts.value = (res.data || []).map((g: GiftList) => ({
        ...g,
        progress: Number(g.progress) || 0,
        needed: Number(g.needed) || 0,
      }))
    } catch {
      gifts.value = []
    }
  }

  async function fetchGiftStats() {
    try {
      const res = await rewardApi.getGiftStats()
      giftStats.value = res.data
    } catch { /* ignore */ }
  }

  async function refreshAll() {
    loading.value = true
    await Promise.all([
      fetchPool(),
      fetchSourceStats(),
      fetchTransactions(),
      fetchGifts(),
      fetchGiftStats(),
    ])
    loading.value = false
  }

  return {
    pool, sourceStats, transactions, txTotal, gifts, giftStats, loading,
    fetchPool, fetchSourceStats, fetchTransactions, fetchGifts, fetchGiftStats, refreshAll,
  }
})
