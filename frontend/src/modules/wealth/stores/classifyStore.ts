import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wealthApi from '../api/wealthApi'
import type {
  ClassifyRuleItem, ClassifyRuleSummary, ClassifyRuleFormData,
  ClassifyPreview, ClassifySummary, UnclassifiedCandidates, SeedClassifyResult,
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
  }

  return {
    rules, ruleSummary, summary, unclassified, periods, yearmon,
    loading, saving, includeInactive,
    fetchRules, fetchRuleSummary, fetchPeriods, fetchSummary, fetchUnclassified,
    fetchResults, fetchAll, setPeriod, setIncludeInactive,
    saveRule, removeRule, toggleRule, seedRules, previewRule,
    resetState,
  }
})
