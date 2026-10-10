/**
 * 物件资产状态（v3.60.0，P4-A）
 *
 * 🔴 这个 store 里**不允许出现任何算法或阈值**：
 *    年限换算、月折旧、净值、剩余月数、四项合计全部在后端算好下发。
 *    前端只做三件事 —— 展示、上色、「算不出来」时把原因说清楚。
 *    在这里补一个 `?? 0` 或一句「其实就是除一下」，
 *    就等于口径有了两份，改后端时必然漏改。
 *
 * ⚠️ 第二个必须理解的行为：`null` **不等于 0**。
 *    `current_value === null` 是「算不出来」（缺金额 / 缺日期 / 缺年限），
 *    而 `'0.00'` 是「真的折完了」的结论。
 *    四卡与明细表遇到 null 要显示「—」并把 `issues` 里的句子摆出来，
 *    绝不能掉成 0 —— 那会把「还没填数据」显示成「已经不值钱了」。
 *
 * ⚠️ 与 `survivalStore` **刻意分开、不共用**：字段与语义不同
 *    （那边是「还能撑多久 / 天」，这边是「值多少钱 / 元」），混用早晚出事。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as propertyApi from '../api/propertyApi'
import type {
  PropertyCategory,
  PropertyCategoryFormData,
  PropertyItem,
  PropertyItemFormData,
  PropertyMeta,
  PropertyMetricMeta,
  PropertySummary,
} from '../types/propertyTypes'
import type { RatioMeta } from '../types/wealthTypes'

export const usePropertyStore = defineStore('property', () => {
  // ─── 状态 ───
  const meta = ref<PropertyMeta | null>(null)
  /** 类别（含 `property_count`）—— 表单下拉、筛选、维护页都从它取 */
  const categories = ref<PropertyCategory[]>([])
  /**
   * 物件台账 —— 后端的默认序是**最近录入的在前**。
   *
   * ⚠️ 这里存的是「原样」，**不带任何排序**：按金额排由表格组件在
   *    `computed` 里做（未填金额恒排最后）。把排序结果写回 store
   *    会让「换了排序再刷新」出现两种顺序，且看不出是哪一步留下的。
   */
  const items = ref<PropertyItem[]>([])
  const summary = ref<PropertySummary | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  /**
   * 最近一次取数的失败原因 —— 空串 = 一切正常。
   *
   * ⚠️ 它存在的理由是「迁移没跑」是**可预期的部署状态，不是代码错误**：
   *    物件资产的两张表来自迁移 `wealth/0026_property`，
   *    表还没建时接口会 500，而界面上必须说清是「还没执行迁移」而不是
   *    「一件家当都没有」—— 后者会让人以为数据丢了。
   */
  const lastError = ref('')

  // ─── 派生（全部是「取出来」，一个数都不算） ───

  /**
   * key → 口径元信息；气泡用它取文案，取不到时返回 null（**不渲染空气泡**）。
   *
   * ⚠️ 这里顺手把 `target` 补成 null：本模块后端不下发它（不设绝对判定线），
   *    而气泡组件的 props 类型是财富侧那份 `RatioMeta`。补一个显式的 null
   *    比放宽组件类型安全 —— 后者会让别的模块也悄悄少一个字段。
   */
  const metricMetaByKey = computed<Record<string, RatioMeta>>(() => {
    const map: Record<string, RatioMeta> = {}
    for (const item of meta.value?.metric_meta ?? []) {
      map[item.key] = { ...(item as PropertyMetricMeta), target: null }
    }
    return map
  })

  const statusOptions = computed(() => meta.value?.statuses ?? [])
  const conditionOptions = computed(() => meta.value?.conditions ?? [])

  /**
   * 模块是否可用 —— 口径与四卡都取到了才算。
   *
   * ⚠️ 判据刻意是「**四卡拿到了**」而不是「列表非空」：
   *    一件家当都没有时四卡是一个全 0 的对象（这是**正确**的答案），
   *    而表还没建时四卡是 null。两者必须分得开。
   */
  const available = computed(() => summary.value !== null && meta.value !== null)

  /** 不可用时的说明 —— 优先说真实原因，没有则给一句可照做的默认话术 */
  const unavailableReason = computed(
    () => lastError.value || '数据尚未就绪 —— 物件资产的两张表来自迁移 wealth/0026_property，'
      + '还没执行的话接口会报错。',
  )

  /** 值 → 中文标签。词表来自后端，前端不写死「在用 / 闲置 / 已报废」 */
  const statusLabels = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const option of statusOptions.value) map[option.value] = option.label
    return map
  })

  const conditionLabels = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const option of conditionOptions.value) map[option.value] = option.label
    return map
  })

  const categoryById = computed<Record<number, PropertyCategory>>(() => {
    const map: Record<number, PropertyCategory> = {}
    for (const category of categories.value) map[category.id] = category
    return map
  })

  /**
   * 一件物件「为什么算不出」—— 把原因码翻成人话，用「；」连起来。
   *
   * ⚠️ 取不到文案时**原样返回原因码**，不返回空串：
   *    空串在界面上就是一个没有提示的「—」，比一串英文码更难排查。
   *    （后端有一条用例钉住「每个原因码都有中文文案」，这里只是最后一道兜底。）
   */
  function issueText(code: string): string {
    return meta.value?.issue_labels?.[code] ?? code
  }

  function issuesText(issues: { code: string; label?: string }[]): string {
    return issues.map((issue) => issue.label || issueText(issue.code)).join('；')
  }

  /** 一件物件的完整「算不出」说明 —— 缺什么、缺几件，一次说清 */
  function explain(item: PropertyItem): string {
    return issuesText(item.issues)
  }

  // ─── 取数 ───

  /**
   * 把异常说成一句能照做的话。
   *
   * ⚠️ 500 且文案里带 `doesn't exist` 时**换成明确的「迁移没跑」**：
   *    原始的 MySQL 报错（`Table 'xxx.wealth_property' doesn't exist`）
   *    贴到界面上没有任何可操作性，而且看着像数据被删了。
   */
  function describeError(error: unknown): string {
    const response = (error as { response?: { status?: number; data?: unknown } })?.response
    const raw = typeof response?.data === 'string'
      ? response.data
      : JSON.stringify(response?.data ?? '')
    if (raw.includes("doesn't exist") || raw.includes('1146')) {
      return '物件资产的表还没建 —— 请先执行迁移 wealth/0026_property（后端手动执行）。'
    }
    const status = response?.status ? `HTTP ${response.status}` : '请求失败'
    return `${status} —— 物件资产的数据暂时取不到，稍后重试；若持续如此请查看后端日志。`
  }

  async function fetchMeta() {
    try {
      const resp = await propertyApi.getPropertyMeta()
      meta.value = (resp.data as PropertyMeta) ?? null
    } catch (e) {
      console.error('获取物件资产口径失败:', e)
      meta.value = null
      lastError.value = describeError(e)
    }
  }

  async function fetchCategories() {
    try {
      const resp = await propertyApi.getPropertyCategories()
      // 后端返回裸数组；被全局分页包住时这里会拿到 undefined，兜底成空数组
      const rows = (resp.data as PropertyCategory[]) ?? []
      categories.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取物件类别失败:', e)
      categories.value = []
      lastError.value = describeError(e)
    }
  }

  async function fetchItems(params?: {
    category?: number
    status?: string
    condition?: string
    search?: string
  }) {
    try {
      const resp = await propertyApi.getPropertyItems(params)
      const rows = (resp.data as PropertyItem[]) ?? []
      items.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取物件台账失败:', e)
      items.value = []
      lastError.value = describeError(e)
    }
  }

  async function fetchSummary() {
    try {
      const resp = await propertyApi.getPropertySummary()
      summary.value = (resp.data as PropertySummary) ?? null
    } catch (e) {
      console.error('获取物件汇总失败:', e)
      summary.value = null
      lastError.value = describeError(e)
    }
  }

  /** 首屏：口径与类别先起（表单下拉要用），台账与四卡随后 */
  async function fetchAll() {
    loading.value = true
    lastError.value = ''
    try {
      await Promise.all([fetchMeta(), fetchCategories()])
      await Promise.all([fetchItems(), fetchSummary()])
    } finally {
      loading.value = false
    }
  }

  /**
   * 任何写入之后统一重拉：派生值全在后端算，前端没有自己的缓存要对齐。
   *
   * ⚠️ 尤其**必须重拉四卡** —— 增删改一件物件都会改变合计，
   *    只刷新列表会出现「明细变了、四卡还是旧的」这种自相矛盾。
   */
  async function refreshAll() {
    await Promise.all([fetchCategories(), fetchItems(), fetchSummary()])
  }

  // ─── 类别 ───

  async function saveCategory(data: PropertyCategoryFormData, id?: number) {
    saving.value = true
    try {
      const resp = id
        ? await propertyApi.updatePropertyCategory(id, data)
        : await propertyApi.createPropertyCategory(data)
      await refreshAll()
      return resp.data as PropertyCategory
    } finally {
      saving.value = false
    }
  }

  /** 删类别；其下有物件时后端 400 —— 由调用方把 `detail` 原样弹出来 */
  async function removeCategory(id: number) {
    saving.value = true
    try {
      await propertyApi.deletePropertyCategory(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  /** 初始化默认类别（幂等，**不预设任何物件**） */
  async function seedCategories(overwrite = false) {
    saving.value = true
    try {
      const resp = await propertyApi.seedPropertyCategories({ overwrite })
      await refreshAll()
      return resp.data
    } finally {
      saving.value = false
    }
  }

  // ─── 物件 ───

  async function saveItem(data: PropertyItemFormData, id?: number) {
    saving.value = true
    try {
      const resp = id
        ? await propertyApi.updatePropertyItem(id, data)
        : await propertyApi.createPropertyItem(data)
      await refreshAll()
      return resp.data as PropertyItem
    } finally {
      saving.value = false
    }
  }

  async function removeItem(id: number) {
    saving.value = true
    try {
      await propertyApi.deletePropertyItem(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  /**
   * 保存前试算 —— **不写库**，也不进 store 的任何缓存。
   *
   * ⚠️ 刻意不 try/catch：调用方需要知道它失败了。但失败**不是**阻断保存的理由 ——
   *    试算是护栏、不是闸门，调用方拿到异常时把提示收起来照常让用户保存。
   */
  async function previewItem(data: PropertyItemFormData): Promise<PropertyItem> {
    const resp = await propertyApi.previewPropertyItem(data)
    return resp.data as PropertyItem
  }

  return {
    // 状态
    meta,
    categories,
    items,
    summary,
    loading,
    saving,
    lastError,
    // 派生
    available,
    unavailableReason,
    metricMetaByKey,
    statusOptions,
    conditionOptions,
    statusLabels,
    conditionLabels,
    categoryById,
    // 文案
    issueText,
    issuesText,
    explain,
    // 取数
    fetchMeta,
    fetchCategories,
    fetchItems,
    fetchSummary,
    fetchAll,
    refreshAll,
    // 写入
    saveCategory,
    removeCategory,
    seedCategories,
    saveItem,
    removeItem,
    previewItem,
  }
})
