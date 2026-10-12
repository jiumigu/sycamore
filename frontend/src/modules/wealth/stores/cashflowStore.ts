import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  CashFlowOverview, AssetTrendItem, SnapshotListData,
  SnapshotFormData,
} from '../types/wealthTypes'

export const useCashflowStore = defineStore('cashflow', () => {
  // ─── 状态 ───
  const overview = ref<CashFlowOverview | null>(null)
  const trendData = ref<AssetTrendItem[]>([])
  const snapshotList = ref<SnapshotListData | null>(null)

  const overviewLoading = ref(false)
  const trendLoading = ref(false)
  const listLoading = ref(false)
  const saving = ref(false)

  // ─── 方法 ───
  async function fetchOverview(yearmon?: string) {
    overviewLoading.value = true
    try {
      const params = yearmon ? { yearmon } : undefined
      const resp = await wealthApi.getCashFlowOverview(params)
      overview.value = resp.data as CashFlowOverview
    } catch (e) {
      console.error('获取资产全景失败:', e)
    } finally {
      overviewLoading.value = false
    }
  }

  async function fetchTrend(months = 12) {
    trendLoading.value = true
    try {
      const resp = await wealthApi.getAssetTrend({ months })
      trendData.value = resp.data as AssetTrendItem[]
    } catch (e) {
      console.error('获取资产趋势失败:', e)
    } finally {
      trendLoading.value = false
    }
  }

  async function fetchSnapshotList(page = 1, pageSize = 12) {
    listLoading.value = true
    try {
      const resp = await wealthApi.getSnapshotList({ page, page_size: pageSize })
      snapshotList.value = resp.data as SnapshotListData
    } catch (e) {
      console.error('获取盘点列表失败:', e)
    } finally {
      listLoading.value = false
    }
  }

  async function saveSnapshot(data: SnapshotFormData) {
    saving.value = true
    try {
      await wealthApi.saveSnapshot(data as unknown as Record<string, unknown>)
      await Promise.all([
        fetchOverview(),
        fetchSnapshotList(),
      ])
    } catch (e) {
      console.error('保存盘点数据失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  async function updateSnapshot(data: SnapshotFormData) {
    saving.value = true
    try {
      await wealthApi.updateSnapshot(data as unknown as Record<string, unknown>)
      await Promise.all([
        fetchOverview(),
        fetchSnapshotList(),
      ])
    } catch (e) {
      console.error('更新盘点数据失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  async function removeSnapshot(baid: number) {
    try {
      await wealthApi.deleteSnapshot({ baid })
      await Promise.all([
        fetchOverview(),
        fetchSnapshotList(),
      ])
    } catch (e) {
      console.error('删除盘点记录失败:', e)
      throw e
    }
  }

  async function copyLastMonth(yearmon: string) {
    saving.value = true
    try {
      await wealthApi.copyLastSnapshot({ yearmon })
      await Promise.all([
        fetchOverview(),
        fetchSnapshotList(),
      ])
    } catch (e) {
      console.error('复制上月数据失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  function resetState() {
    overview.value = null
    trendData.value = []
    snapshotList.value = null
  }

  return {
    overview, trendData, snapshotList,
    overviewLoading, trendLoading, listLoading, saving,
    fetchOverview, fetchTrend, fetchSnapshotList,
    saveSnapshot, updateSnapshot, removeSnapshot,
    copyLastMonth, resetState,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useCashflowStore, import.meta.hot))
}
