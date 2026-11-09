import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as sugarApi from '../api/sugarApi'
import type {
  EnergyLog, EnergyStats, EnergyTemplate, JoyTypeOptions, SugarRecord, SugarCategoryStats,
  SugarHappinessBands, SugarTemplate,
} from '../types/sugarTypes'

export const useSugarStore = defineStore('sugar', () => {
  const sugarList = ref<SugarRecord[]>([])
  const currentRecord = ref<SugarRecord | null>(null)
  const categories = ref<SugarCategoryStats[]>([])
  const totalReward = ref(0)
  const loading = ref(false)
  const submitting = ref(false)

  // ─── 分页状态 ───
  const currentPage = ref(1)
  const pageSize = ref(10)
  const total = ref(0)

  /** 最近一次生效的列表筛选（翻页时复用，避免翻页把筛选丢掉） */
  const lastListParams = ref<Record<string, unknown>>({})

  // ─── 快乐类型筛选项（下拉框唯一来源，见 types 里的说明） ───
  const joyTypeOptions = ref<JoyTypeOptions | null>(null)

  async function fetchJoyTypeOptions(params?: Record<string, unknown>) {
    try {
      const response = await sugarApi.getJoyTypeOptions(params)
      joyTypeOptions.value = response.data as JoyTypeOptions
      return joyTypeOptions.value
    } catch (error) {
      console.error('获取快乐类型选项失败:', error)
      // 取不到就让下拉为空 —— 不退回前端硬编码的五个标准型：
      // 那会让「旧词表」和「未标注」凭空消失，而且看起来一切正常。
      joyTypeOptions.value = null
      return null
    }
  }

  // ─── 统计汇总（来自 categories API） ───
  const statsSummary = ref<{
    total_count: number
    total_reward: number
    avg_happiness: number
  }>({ total_count: 0, total_reward: 0, avg_happiness: 0 })

  // ─── 小确幸模板 ───
  const templates = ref<SugarTemplate[]>([])
  const templateSubmitting = ref(false)

  // ─── 快乐程度档位表（后端唯一真源，前端零副本） ───
  // 取不到就是 null —— 那时界面上**只说分数、不编档位词**（见 happinessLabelOf）。
  const happinessBands = ref<SugarHappinessBands | null>(null)

  async function fetchHappinessBands() {
    try {
      const response = await sugarApi.getHappinessBands()
      happinessBands.value = response.data
      return response.data as SugarHappinessBands
    } catch (error) {
      console.error('获取快乐档位表失败:', error)
      happinessBands.value = null
      // 不往外抛：调用方（页面挂载）要的就是这个状态位，抛出去只会变成无人接的 rejection
      return null
    }
  }

  async function fetchSugarList(params?: Record<string, unknown>) {
    // 有参数才覆盖：翻页走的是 `handlePageChange` → `fetchSugarList()` 无参调用，
    // 若这里用空对象覆盖，第 2 页就会悄悄退回「全部记录」（筛选看起来像失效了）。
    if (params) lastListParams.value = { ...params }
    loading.value = true
    try {
      const response = await sugarApi.getSugarList({
        page: currentPage.value,
        page_size: pageSize.value,
        ...lastListParams.value,
      })
      const data = response.data
      if (data.results) {
        sugarList.value = data.results
        total.value = data.count ?? 0
      } else if (Array.isArray(data)) {
        sugarList.value = data
      }
      return data
    } catch (error) {
      console.error('获取小确幸列表失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(page: number) {
    currentPage.value = page
    // 不带参数 —— 筛选条件由 `lastListParams` 承接（见 fetchSugarList 里的说明）
    fetchSugarList()
  }

  async function fetchSugarById(id: number) {
    loading.value = true
    try {
      const response = await sugarApi.getSugarDetail(id)
      currentRecord.value = response.data
      return response.data
    } catch (error) {
      console.error('获取小确幸详情失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function createNewSugar(data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await sugarApi.createSugar(data)
      return response.data
    } catch (error) {
      console.error('创建小确幸失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function updateExistingSugar(id: number, data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await sugarApi.updateSugar(id, data)
      return response.data
    } catch (error) {
      console.error('更新小确幸失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function deleteExistingSugar(id: number) {
    try {
      await sugarApi.deleteSugar(id)
      sugarList.value = sugarList.value.filter(r => r.s_id !== id)
      return true
    } catch (error) {
      console.error('删除小确幸失败:', error)
      throw error
    }
  }

  async function fetchCategories(params?: Record<string, unknown>) {
    try {
      const response = await sugarApi.getSugarCategories(params)
      const data = response.data
      if (data.categories) {
        categories.value = data.categories
        statsSummary.value = data.summary || { total_count: 0, total_reward: 0, avg_happiness: 0 }
        totalReward.value = data.summary?.total_reward ?? 0
      } else if (Array.isArray(data)) {
        // 兼容旧格式（无分页）
        categories.value = data
        totalReward.value = data.reduce((sum: number, c: SugarCategoryStats) => sum + c.total_reward, 0)
      }
      return response.data
    } catch (error) {
      console.error('获取分类统计失败:', error)
      throw error
    }
  }

  // ─── 模板 CRUD ───

  async function fetchTemplates() {
    try {
      const response = await sugarApi.getSugarTemplates()
      templates.value = response.data.results || response.data
      return templates.value
    } catch (error) {
      console.error('获取小确幸模板失败:', error)
      throw error
    }
  }

  async function createTemplate(data: Record<string, unknown>) {
    templateSubmitting.value = true
    try {
      const response = await sugarApi.createSugarTemplate(data)
      templates.value.push(response.data)
      return response.data
    } catch (error) {
      console.error('创建小确幸模板失败:', error)
      throw error
    } finally {
      templateSubmitting.value = false
    }
  }

  async function updateTemplate(id: number, data: Record<string, unknown>) {
    templateSubmitting.value = true
    try {
      const response = await sugarApi.updateSugarTemplate(id, data)
      const idx = templates.value.findIndex(t => t.id === id)
      if (idx !== -1) templates.value[idx] = response.data
      return response.data
    } catch (error) {
      console.error('更新小确幸模板失败:', error)
      throw error
    } finally {
      templateSubmitting.value = false
    }
  }

  async function deleteTemplate(id: number) {
    try {
      await sugarApi.deleteSugarTemplate(id)
      templates.value = templates.value.filter(t => t.id !== id)
      return true
    } catch (error) {
      console.error('删除小确幸模板失败:', error)
      throw error
    }
  }

  return {
    sugarList, currentRecord, categories, totalReward, loading, submitting,
    fetchSugarList, fetchSugarById, createNewSugar,
    updateExistingSugar, deleteExistingSugar, fetchCategories,
    // ─── 分页 ───
    currentPage, pageSize, total, handlePageChange,
    // ─── 快乐类型筛选项 ───
    joyTypeOptions, fetchJoyTypeOptions,
    // ─── 统计汇总 ───
    statsSummary,
    // ─── 模板 ───
    templates, templateSubmitting,
    fetchTemplates, createTemplate, updateTemplate, deleteTemplate,
    // ─── 快乐档位表 ───
    happinessBands, fetchHappinessBands,
    // ─── 能量清单 ───
    energyTemplates, energyDailyLogs, energyStatsValue, energyLoading,
    fetchEnergyTemplates, completeEnergyTask, fetchEnergyStats, fetchEnergyDaily,
  }
})

// ─── 能量清单状态 ───
const energyTemplates = ref<EnergyTemplate[]>([])
const energyDailyLogs = ref<EnergyLog[]>([])
const energyStatsValue = ref<EnergyStats | null>(null)
const energyLoading = ref(false)

async function fetchEnergyTemplates() {
  const res = await sugarApi.getEnergyTemplates()
  energyTemplates.value = res.data
  return res.data
}

async function completeEnergyTask(data: Record<string, unknown>) {
  const res = await sugarApi.completeEnergyTask(data)
  await fetchEnergyDaily()
  await fetchEnergyStats()
  return res.data
}

async function fetchEnergyStats() {
  const res = await sugarApi.getEnergyStats()
  energyStatsValue.value = res.data
  return res.data
}

async function fetchEnergyDaily(date?: string) {
  const res = await sugarApi.getEnergyDaily(date)
  energyDailyLogs.value = res.data.items || []
  return res.data
}

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useSugarStore, import.meta.hot))
}
