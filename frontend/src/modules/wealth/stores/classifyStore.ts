import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  ClassifyRuleItem, ClassifyRuleSummary, ClassifyRuleFormData,
  ClassifyPreview, ClassifySummary, UnclassifiedCandidates, SeedClassifyResult,
  BillCategoryOptions,
} from '../types/wealthTypes'

/**
 * 账单项分类规则 / 归类结果状态（P1-C）
 *
 * 为什么单独一个 store，不并进 cashflowStore：
 *   这里管的是「账单**性质**」这把尺子（收入主动被动 / 支出固定可变 / 现金流五类），
 *   与资产盘点（cashflowStore）和负债台账（debtStore）是三个正交视角。
 *   混在一起会让「改一条规则要不要重拉资产快照」这种问题变得没有答案。
 *
 * 🔴 一个必须理解的行为：**改规则会让历史数字一起变**。
 *   分类结果不落库、按当前规则实时算 —— 这不是 bug，是刻意的口径
 *   （金额是历史事实、分类是当前视角，与 P1-B 资产快照同一条原则）。
 *   所以任何写操作之后都要重新拉 `summary` 与 `unclassified`，
 *   否则界面会显示改规则之前的世界。保存前请先看 `previewRule`。
 */
export const useClassifyStore = defineStore('classify', () => {
  // ─── 状态 ───
  const rules = ref<ClassifyRuleItem[]>([])
  const ruleSummary = ref<ClassifyRuleSummary | null>(null)
  /** 归类汇总（按期；yearmon 为空 = 全周期） */
  const summary = ref<ClassifySummary | null>(null)
  /** 未归类候选（「下一条规则该建在哪儿」） */
  const unclassified = ref<UnclassifiedCandidates | null>(null)
  /** 有数据的年月（倒序），空字符串代表「全周期」 */
  const periods = ref<string[]>([])
  /** 当前查看的期；'' = 全周期 */
  const yearmon = ref<string>('')

  /**
   * 快速记账的「分类 / 子分类」候选值。
   *
   * 🔴 这是分类体系的**唯一来源** —— 不允许任何组件在自己家里再写一份
   *    分类数组（`QuickBillForm.vue` 原来那份 17 项硬编码就是这么来的，
   *    跟真实账本完全对不上）。
   */
  const billOptions = ref<BillCategoryOptions | null>(null)

  const loading = ref(false)
  const saving = ref(false)
  const includeInactive = ref(false)

  // ─── 取数 ───
  async function fetchRules() {
    try {
      const resp = await wealthApi.getClassifyRules({
        include_inactive: includeInactive.value ? 1 : 0,
      })
      // 后端返回裸数组；若被全局分页包成 {count, results}，这里会拿到 undefined
      rules.value = (resp.data as ClassifyRuleItem[]) ?? []
    } catch (e) {
      console.error('获取分类规则失败:', e)
    }
  }

  async function fetchRuleSummary() {
    try {
      const resp = await wealthApi.getClassifyRuleSummary()
      ruleSummary.value = (resp.data as ClassifyRuleSummary) ?? null
    } catch (e) {
      console.error('获取规则结构汇总失败:', e)
    }
  }

  async function fetchPeriods() {
    try {
      const resp = await wealthApi.getClassifyPeriods()
      periods.value = (resp.data as string[]) ?? []
      // 首次进入默认落在最新一期；没有数据则退回全周期
      if (!yearmon.value && periods.value.length) {
        yearmon.value = periods.value[0]
      }
    } catch (e) {
      console.error('获取可选期失败:', e)
    }
  }

  async function fetchSummary() {
    try {
      const resp = await wealthApi.getClassifySummary(
        yearmon.value ? { yearmon: yearmon.value } : undefined,
      )
      summary.value = (resp.data as ClassifySummary) ?? null
    } catch (e) {
      console.error('获取归类汇总失败:', e)
    }
  }

  async function fetchUnclassified() {
    try {
      const resp = await wealthApi.getClassifyUnclassified(
        yearmon.value ? { yearmon: yearmon.value } : undefined,
      )
      unclassified.value = (resp.data as UnclassifiedCandidates) ?? null
    } catch (e) {
      console.error('获取未归类候选失败:', e)
    }
  }

  /**
   * 结果类取数：汇总 + 未归类候选一起拉。
   *
   * ⚠️ 两者必须同源同期，否则会出现「汇总说还有 3 万未归类，
   *    候选清单里却是另一个月的条目」——分开拉就一定会遇到。
   */
  async function fetchResults() {
    loading.value = true
    try {
      await Promise.all([fetchSummary(), fetchUnclassified()])
    } finally {
      loading.value = false
    }
  }

  async function fetchAll() {
    await Promise.all([fetchRules(), fetchRuleSummary(), fetchPeriods()])
    await fetchResults()
  }

  /**
   * 拉取快速记账的「分类 / 子分类」候选。
   *
   * ⚠️ **刻意不缓存**：候选是**账本的派生结果**，而账本每天都在长 ——
   *    今天用自由输入记过一个新子分类，明天它就该出现在候选里。
   *    所以调用方要在**每次打开录入界面时**拉一次（`DayDetailModal` 就是这么做的），
   *    而不是在页面初始化时拉一次了事。
   * ⚠️ 失败时**保留上一次的候选**（不清空）：拉不到新候选就退化成旧候选，
   *    总好过把下拉清空让人以为分类体系没了。
   */
  async function fetchBillOptions() {
    try {
      const resp = await wealthApi.getBillCategoryOptions()
      billOptions.value = (resp.data as BillCategoryOptions) ?? null
    } catch (e) {
      console.error('获取记账分类候选失败:', e)
    }
  }

  /** 切换查看期（'' = 全周期） */
  async function setPeriod(value: string) {
    yearmon.value = value
    await fetchResults()
  }

  // ─── 规则写入 ───
  async function saveRule(data: ClassifyRuleFormData) {
    saving.value = true
    try {
      if (data.id) {
        await wealthApi.updateClassifyRule(data.id, data)
      } else {
        await wealthApi.createClassifyRule(data)
      }
      // 规则一动，结果必然变 —— 必须重拉，否则界面停留在改规则之前的世界
      await Promise.all([fetchRules(), fetchRuleSummary()])
      await fetchResults()
    } catch (e) {
      console.error('保存分类规则失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  async function removeRule(id: number) {
    saving.value = true
    try {
      const resp = await wealthApi.deleteClassifyRule(id)
      await Promise.all([fetchRules(), fetchRuleSummary()])
      await fetchResults()
      return resp.data
    } catch (e) {
      console.error('删除分类规则失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  /** 停用 / 启用（改规则历史影响的替代方案：停用可追溯、可一键恢复） */
  async function toggleRule(rule: ClassifyRuleItem) {
    return saveRule({
      id: rule.id,
      rule_field: rule.rule_field,
      match_value: rule.match_value,
      is_active: !rule.is_active,
    })
  }

  async function seedRules(overwrite = false): Promise<SeedClassifyResult | null> {
    saving.value = true
    try {
      const resp = await wealthApi.seedClassifyRules(overwrite)
      await Promise.all([fetchRules(), fetchRuleSummary()])
      await fetchResults()
      return (resp.data as SeedClassifyResult) ?? null
    } catch (e) {
      console.error('初始化分类规则失败:', e)
      throw e
    } finally {
      saving.value = false
    }
  }

  /**
   * 影响预览（不写库）。
   *
   * 刻意**不放进状态**而是直接返回：预览是一次性的、跟着弹窗走，
   * 存进 store 会让「上次预览的结果」在新表单里残留，看着像已生效。
   */
  async function previewRule(data: ClassifyRuleFormData): Promise<ClassifyPreview | null> {
    try {
      const resp = await wealthApi.previewClassifyRule({
        ...data,
        yearmon: yearmon.value || undefined,
      } as ClassifyRuleFormData & { yearmon?: string })
      return (resp.data as ClassifyPreview) ?? null
    } catch (e) {
      console.error('影响预览失败:', e)
      throw e
    }
  }

  async function setIncludeInactive(value: boolean) {
    includeInactive.value = value
    await fetchRules()
  }

  function resetState() {
    rules.value = []
    ruleSummary.value = null
    summary.value = null
    unclassified.value = null
    periods.value = []
    yearmon.value = ''
    billOptions.value = null
  }

  return {
    rules, ruleSummary, summary, unclassified, periods, yearmon, billOptions,
    loading, saving, includeInactive,
    fetchRules, fetchRuleSummary, fetchPeriods, fetchSummary, fetchUnclassified,
    fetchBillOptions,
    fetchResults, fetchAll, setPeriod, setIncludeInactive,
    saveRule, removeRule, toggleRule, seedRules, previewRule,
    resetState,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useClassifyStore, import.meta.hot))
}
