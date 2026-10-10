import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  AssetAccountItem, AssetAccountSummary, AssetAccountFormData,
  AssetSnapshotRow, AssetSnapshotFormData,
} from '../types/wealthTypes'

/**
 * 资产科目主数据 / 资产快照状态（P1-B）
 *
 * 与 cashflowStore 的关系：v3.60.5 起资产位置有了**唯一真源**
 * （`ratio_service.resolve_asset_*` —— 有新体系快照即用它、否则回落旧表），
 * 顶部全景/趋势与六项比率都从那里取。本 store 走 asset/* 接口读写
 * **科目主数据与快照明细行**，是同一份底层数据的录入与管理入口，
 * 所以这里也不去改 cashflowStore 的任何状态。
 *
 * v3.60.7 退役「双跑对账」：旧表 18 期已回填完毕、两边同源，
 * 比对退化成恒等式，故不再持有任何比对结果。
 *
 * 科目与快照分开取数：改一个科目不该触发快照列表重拉（反之亦然）。
 */
export const useAssetStore = defineStore('asset', () => {
  // ─── 状态 ───
  const accounts = ref<AssetAccountItem[]>([])
  const accountSummary = ref<AssetAccountSummary | null>(null)
  const snapshots = ref<AssetSnapshotRow[]>([])

  const loading = ref(false)
  const saving = ref(false)
  /** 快照列表期数（月度数据用「最近 N 期」而非分页） */
  const snapshotLimit = ref(24)

  // ─── 取数 ───
  async function fetchAccounts(includeInactive = true) {
    try {
      const [listResp, summaryResp] = await Promise.all([
        wealthApi.getAssetAccounts({ include_inactive: includeInactive ? 1 : 0 }),
        wealthApi.getAssetAccountSummary(),
      ])
      // 后端返回裸数组；若被全局分页包成 {count, results}，这里会拿到 undefined
      accounts.value = (listResp.data as AssetAccountItem[]) ?? []
      accountSummary.value = (summaryResp.data as AssetAccountSummary) ?? null
    } catch (e) {
      console.error('获取资产科目失败:', e)
    }
  }

  async function fetchSnapshots() {
    loading.value = true
    try {
      const resp = await wealthApi.getAssetSnapshots({ limit: snapshotLimit.value })
      snapshots.value = (resp.data as AssetSnapshotRow[]) ?? []
    } catch (e) {
      console.error('获取资产快照失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchAll() {
    await Promise.all([fetchAccounts(), fetchSnapshots()])
  }

  // ─── 科目写入 ───
  async function saveAccount(data: AssetAccountFormData) {
    saving.value = true
    try {
      if (data.id) {
        await wealthApi.updateAssetAccount(data)
      } else {
        await wealthApi.createAssetAccount(data)
      }
      await Promise.all([fetchAccounts(), fetchSnapshots()])
    } catch (e) {
      console.error('保存资产科目失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  async function removeAccount(id: number) {
    try {
      await wealthApi.deleteAssetAccount(id)
      await fetchAccounts()
    } catch (e) {
      console.error('删除资产科目失败:', e)
      throw e
    }
  }

  /** 从旧表列定义生成种子科目；overwrite=false 时不覆盖已改过的科目 */
  async function seedAccounts(overwrite = false) {
    saving.value = true
    try {
      const resp = await wealthApi.seedAssetAccounts(overwrite)
      await fetchAccounts()
      return resp.data
    } catch (e) {
      console.error('初始化科目失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  // ─── 快照写入 ───
  async function saveSnapshot(data: AssetSnapshotFormData, editingId?: number | null) {
    saving.value = true
    try {
      if (editingId) {
        await wealthApi.updateAssetSnapshot(editingId, data)
      } else {
        await wealthApi.createAssetSnapshot(data)
      }
      await Promise.all([fetchSnapshots(), fetchAccounts()])
    } catch (e) {
      console.error('保存资产快照失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  async function removeSnapshot(id: number) {
    try {
      await wealthApi.deleteAssetSnapshot(id)
      await fetchSnapshots()
    } catch (e) {
      console.error('删除资产快照失败:', e)
      throw e
    }
  }

  /** 取一期完整快照（含明细行）—— 编辑弹窗回填用 */
  async function loadSnapshot(id: number): Promise<AssetSnapshotRow | null> {
    try {
      const resp = await wealthApi.getAssetSnapshot(id)
      return (resp.data as AssetSnapshotRow) ?? null
    } catch (e) {
      console.error('获取快照详情失败:', e)
      return null
    }
  }

  function resetState() {
    accounts.value = []
    accountSummary.value = null
    snapshots.value = []
  }

  return {
    accounts, accountSummary, snapshots,
    loading, saving, snapshotLimit,
    fetchAccounts, fetchSnapshots, fetchAll,
    saveAccount, removeAccount, seedAccounts,
    saveSnapshot, removeSnapshot, loadSnapshot,
    resetState,
  }
})
