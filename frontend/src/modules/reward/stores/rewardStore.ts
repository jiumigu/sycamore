import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as rewardApi from '../api/rewardApi'
import type { RewardPool, RewardTransaction, RewardSourceStats } from '../types/rewardTypes'

export const useRewardStore = defineStore('reward', () => {
  const pool = ref<RewardPool>({ balance: 0, total_earned: 0, total_withdrawn: 0 })
  const sourceStats = ref<RewardSourceStats | null>(null)
  const transactions = ref<RewardTransaction[]>([])
  const txTotal = ref(0)
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
      // 金额由后端保证是 number（`RewardTransactionSerializer` 显式声明了
      // AmountNumberField）。这里**不再**做 `Number()` 转换：调用点补转换
      // 只会让「后端吐字符串」重新变成静默故障（v3.63.18 的礼物价格即此型）。
      transactions.value = data.items || []
      txTotal.value = data.total || 0
    } catch {
      transactions.value = []
      txTotal.value = 0
    }
  }

  async function refreshAll() {
    loading.value = true
    await Promise.all([
      fetchPool(),
      fetchSourceStats(),
      fetchTransactions(),
    ])
    loading.value = false
  }

  return {
    pool, sourceStats, transactions, txTotal, loading,
    fetchPool, fetchSourceStats, fetchTransactions, refreshAll,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useRewardStore, import.meta.hot))
}
