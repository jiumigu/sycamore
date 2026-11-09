import { apiErrorText } from '@/shared/utils/apiError'
import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as outputApi from '../api/outputApi'
import type { OutputRecord, OutputStats, OutputWindow } from '../types/outputTypes'

export const useOutputStore = defineStore('output', () => {
  const records = ref<OutputRecord[]>([])
  /** 后端 `count`（过滤后的全量）—— 分页条用它，不是 `records.length` */
  const total = ref(0)
  const stats = ref<OutputStats | null>(null)
  const loading = ref(false)
  const saving = ref(false)

  const filterCategory = ref('')
  const filterQuality = ref('')

  /**
   * 统计窗口：默认 **近 30 天**。
   * 🔴 以前这里有个只读的 `filterYear = 当前年`，界面上没有任何地方显示它，
   *    却把列表和统计一起悄悄缩到「今年」——而且未填日期的记录
   *    （`occurred_at=None`）会被 `__year` 永久排除。现在窗口是**用户看得见的选择**。
   */
  const window = ref<OutputWindow>('30d')

  const page = ref(1)
  const pageSize = ref(20)

  function listParams(): Record<string, string> {
    const params: Record<string, string> = {
      window: window.value,
      page: String(page.value),
      page_size: String(pageSize.value),
    }
    if (filterCategory.value) params.category = filterCategory.value
    if (filterQuality.value) params.quality = filterQuality.value
    return params
  }

  async function fetchRecords() {
    loading.value = true
    try {
      const res = await outputApi.getOutputRecords(listParams())
      // 分页返回 {count, results}；后端若关掉分页就是裸数组
      if (Array.isArray(res.data)) {
        records.value = res.data
        total.value = res.data.length
      } else {
        records.value = res.data.results || []
        total.value = res.data.count ?? records.value.length
      }
    } catch (e) {
      console.error('获取产出记录失败:', e)
      records.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const res = await outputApi.getOutputStats({ window: window.value })
      stats.value = res.data as OutputStats
    } catch (e) {
      console.error('获取产出统计失败:', e)
      // 取不到时置空，让页面显示「样本不足」而不是留上一次的数字
      stats.value = null
    }
  }

  /** 换窗口 / 换筛选 / 换每页条数 ⇒ 回第 1 页（旧页码在新条件下没有意义） */
  async function reload() {
    page.value = 1
    await Promise.all([fetchRecords(), fetchStats()])
  }

  async function goPage(p: number) {
    const lastPage = Math.max(1, Math.ceil(total.value / pageSize.value))
    page.value = Math.min(Math.max(1, p), lastPage)
    await fetchRecords()
  }

  async function changePageSize(size: number) {
    pageSize.value = size
    page.value = 1
    await fetchRecords()
  }

  async function createRecord(data: Record<string, unknown>) {
    saving.value = true
    try {
      await outputApi.createOutputRecord(data)
      await Promise.all([fetchRecords(), fetchStats()])
      ElMessage.success('记录已保存')
    } catch (e) {
      ElMessage.error(apiErrorText(e, '保存失败'))
      console.error('创建失败:', e)
    } finally {
      saving.value = false
    }
  }

  async function updateRecord(id: number, data: Record<string, unknown>) {
    saving.value = true
    try {
      await outputApi.updateOutputRecord(id, data)
      await Promise.all([fetchRecords(), fetchStats()])
      ElMessage.success('已更新')
    } catch (e) {
      ElMessage.error('更新失败')
      console.error('更新失败:', e)
    } finally {
      saving.value = false
    }
  }

  async function deleteRecord(id: number) {
    try {
      await outputApi.deleteOutputRecord(id)
      // 删掉本页最后一条 ⇒ 退到新的最后一页，不然留着空表 + 越界页码
      const lastPage = Math.max(1, Math.ceil(Math.max(0, total.value - 1) / pageSize.value))
      if (page.value > lastPage) page.value = lastPage
      await Promise.all([fetchRecords(), fetchStats()])
    } catch (e) {
      ElMessage.error('删除失败')
      console.error('删除失败:', e)
    }
  }

  async function fetchAll() {
    await Promise.all([fetchRecords(), fetchStats()])
  }

  function setWindow(w: OutputWindow) {
    window.value = w
    return reload()
  }

  return {
    records, total, stats, loading, saving,
    filterCategory, filterQuality, window, page, pageSize,
    fetchRecords, fetchStats, fetchAll, reload, goPage, changePageSize, setWindow,
    createRecord, updateRecord, deleteRecord,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」）。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useOutputStore, import.meta.hot))
}
