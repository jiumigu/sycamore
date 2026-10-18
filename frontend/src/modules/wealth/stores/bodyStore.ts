/**
 * 身上之物状态（v3.62.4）
 *
 * 🔴 这个 store 里**不允许出现任何判断或阈值**：
 *    `satisfaction_blank_reason`、四个计数、`linked_kind` 全部由后端算好下发。
 *    前端只做三件事 —— 展示、筛（按已下发的值）、把「空」的两种来由分开说。
 *    在这里补一个 `?? 'meh'` 或一句「其实就是看看挂没挂东西」，
 *    就等于口径有了两份，改后端时必然漏改。
 *
 * ⚠️ 第二个必须理解的行为：`satisfaction === null` **不等于**「凑合」。
 *    空的两种来由（`no_item` / `unrated`）由后端给，前端**只查表**：
 *    `no_item`（还没有东西在用，格子本来就该空）与
 *    `unrated`（有东西在用、但还没评过，该去评一次）采取的行动相反。
 *
 * ⚠️ 与 `propertyStore` **刻意分开、不共用**：那边是「已经买回来的」，
 *    这边是「还没找到的」—— 字段与产出口都不同，混用早晚出事。
 */

import { acceptHMRUpdate, defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as bodyApi from '../api/bodyApi'
import type {
  BodyBlankReasonOption,
  BodyMeta,
  BodyMetricMeta,
  BodyNeed,
  BodyNeedFormData,
  BodyPart,
  BodyPartFormData,
  BodySummary,
} from '../types/bodyTypes'
import type { RatioMeta } from '../types/wealthTypes'

export const useBodyStore = defineStore('body', () => {
  // ─── 状态 ───
  const meta = ref<BodyMeta | null>(null)
  /** 部位（含 `need_count`）—— 表单下拉、筛选、维护浮层都从它取 */
  const parts = ref<BodyPart[]>([])
  /** 位 —— 后端的默认序是「按部位自定义顺序 → 最近录入」 */
  const needs = ref<BodyNeed[]>([])
  const summary = ref<BodySummary | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  /**
   * 最近一次取数的失败原因 —— 空串 = 一切正常。
   *
   * ⚠️ 它存在的理由是「迁移没跑」是**可预期的部署状态，不是代码错误**：
   *    本模块的两张表来自迁移 `wealth/0028_body_need`，
   *    表还没建时接口会 500，而界面上必须说清是「还没执行迁移」而不是
   *    「一条都没有」—— 后者会让人以为数据丢了。
   */
  const lastError = ref('')

  // ─── 派生（全部是「取出来」，一个判断都不做） ───

  const metricMetaByKey = computed<Record<string, RatioMeta>>(() => {
    const map: Record<string, RatioMeta> = {}
    for (const item of meta.value?.metric_meta ?? []) {
      map[item.key] = { ...(item as BodyMetricMeta), target: null }
    }
    return map
  })

  const findStatusOptions = computed(() => meta.value?.find_statuses ?? [])
  const satisfactionOptions = computed(() => meta.value?.satisfactions ?? [])

  /** 值 → 中文标签。词表来自后端，前端不写死「待寻 / 寻找中 / 已找到」 */
  const findStatusLabels = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const option of findStatusOptions.value) map[option.value] = option.label
    return map
  })

  const satisfactionLabels = computed<Record<string, string>>(() => {
    const map: Record<string, string> = {}
    for (const option of satisfactionOptions.value) map[option.value] = option.label
    return map
  })

  /**
   * 原因码 → 那两种空的说明（`short` 格子里的字 / `label` 悬停的解释）。
   *
   * 🔴 前端**不自己写**「—」和「未评」这两个字：它们是后端下发的文案，
   *    写在前端就是第二份副本，改后端文案时它不会被改到。
   */
  const blankReasonByValue = computed<Record<string, BodyBlankReasonOption>>(() => {
    const map: Record<string, BodyBlankReasonOption> = {}
    for (const item of meta.value?.blank_reasons ?? []) map[item.value] = item
    return map
  })

  const partById = computed<Record<number, BodyPart>>(() => {
    const map: Record<number, BodyPart> = {}
    for (const part of parts.value) map[part.id] = part
    return map
  })

  const subtitle = computed(
    () => meta.value?.subtitle ?? '管的是「我该有什么、称不称心」，不是库存也不是价格',
  )

  /**
   * 模块是否可用 —— 口径与计数都取到了才算。
   *
   * ⚠️ 判据刻意是「**汇总拿到了**」而不是「列表非空」：
   *    一条都没有时汇总是个全 0 的对象（这是**正确**的答案），
   *    而表还没建时汇总是 null。两者必须分得开。
   */
  const available = computed(() => summary.value !== null && meta.value !== null)

  const unavailableReason = computed(
    () => lastError.value || '数据尚未就绪 —— 身上之物的两张表来自迁移 wealth/0028_body_need，'
      + '还没执行的话接口会报错。',
  )

  /** 还没搞定的条数 —— 顶部那张卡念的就是它，与清单筛选同源（后端同一判据） */
  const pendingCount = computed(() => summary.value?.pending_count ?? 0)

  // ─── 取数 ───

  /**
   * 把异常说成一句能照做的话。
   *
   * ⚠️ 500 且文案里带 `doesn't exist` 时**换成明确的「迁移没跑」**：
   *    原始的 MySQL 报错贴到界面上没有任何可操作性，而且看着像数据被删了。
   */
  function describeError(error: unknown): string {
    const response = (error as { response?: { status?: number; data?: unknown } })?.response
    const raw = typeof response?.data === 'string'
      ? response.data
      : JSON.stringify(response?.data ?? '')
    if (raw.includes("doesn't exist") || raw.includes('1146')) {
      return '身上之物的表还没建 —— 请先执行迁移 wealth/0028_body_need（后端手动执行）。'
    }
    const status = response?.status ? `HTTP ${response.status}` : '请求失败'
    return `${status} —— 身上之物的数据暂时取不到，稍后重试；若持续如此请查看后端日志。`
  }

  async function fetchMeta() {
    try {
      const resp = await bodyApi.getBodyMeta()
      meta.value = (resp.data as BodyMeta) ?? null
    } catch (e) {
      console.error('获取身上之物口径失败:', e)
      meta.value = null
      lastError.value = describeError(e)
    }
  }

  async function fetchParts() {
    try {
      const resp = await bodyApi.getBodyParts()
      // 后端返回裸数组；被全局分页包住时这里会拿到 undefined，兜底成空数组
      const rows = (resp.data as BodyPart[]) ?? []
      parts.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取部位失败:', e)
      parts.value = []
      lastError.value = describeError(e)
    }
  }

  async function fetchNeeds() {
    try {
      const resp = await bodyApi.getBodyNeeds()
      const rows = (resp.data as BodyNeed[]) ?? []
      needs.value = Array.isArray(rows) ? rows : []
    } catch (e) {
      console.error('获取身上之物清单失败:', e)
      needs.value = []
      lastError.value = describeError(e)
    }
  }

  async function fetchSummary() {
    try {
      const resp = await bodyApi.getBodySummary()
      summary.value = (resp.data as BodySummary) ?? null
    } catch (e) {
      console.error('获取身上之物汇总失败:', e)
      summary.value = null
      lastError.value = describeError(e)
    }
  }

  /** 首屏：口径与部位先起（表单下拉要用），清单与计数随后 */
  async function fetchAll() {
    loading.value = true
    lastError.value = ''
    try {
      await Promise.all([fetchMeta(), fetchParts()])
      await Promise.all([fetchNeeds(), fetchSummary()])
    } finally {
      loading.value = false
    }
  }

  /**
   * 任何写入之后统一重拉：派生值全在后端算，前端没有自己的缓存要对齐。
   *
   * ⚠️ 尤其**必须重拉计数** —— 改一个位的进度就会改变「还没搞定」那个数，
   *    只刷新列表会出现「明细变了、卡还是旧的」这种自相矛盾。
   *    ⚠️ 也**必须重拉部位** —— `need_count` 会随位的增删变（它就是那个
   *    「为什么这个部位删不掉」的答案，停留在旧值会让用户白点一次删除）。
   */
  async function refreshAll() {
    await Promise.all([fetchParts(), fetchNeeds(), fetchSummary()])
  }

  // ─── 部位 ───

  async function savePart(data: BodyPartFormData, id?: number) {
    saving.value = true
    try {
      const resp = id
        ? await bodyApi.updateBodyPart(id, data)
        : await bodyApi.createBodyPart(data)
      await refreshAll()
      return resp.data as BodyPart
    } finally {
      saving.value = false
    }
  }

  /** 删部位；其下有位时后端 400 —— 由调用方把 `detail` 原样弹出来 */
  async function removePart(id: number) {
    saving.value = true
    try {
      await bodyApi.deleteBodyPart(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  /** 初始化默认部位（幂等，**不预设任何位**） */
  async function seedParts(overwrite = false) {
    saving.value = true
    try {
      const resp = await bodyApi.seedBodyParts({ overwrite })
      await refreshAll()
      return resp.data
    } finally {
      saving.value = false
    }
  }

  // ─── 位 ───

  async function saveNeed(data: BodyNeedFormData, id?: number) {
    saving.value = true
    try {
      const resp = id
        ? await bodyApi.updateBodyNeed(id, data)
        : await bodyApi.createBodyNeed(data)
      await refreshAll()
      return resp.data as BodyNeed
    } finally {
      saving.value = false
    }
  }

  /** 行内改一个字段（进度 / 满意）—— 不做「乐观更新」，成功后以服务端返回为准 */
  async function patchNeed(id: number, data: Partial<BodyNeedFormData>) {
    saving.value = true
    try {
      const resp = await bodyApi.updateBodyNeed(id, data)
      await refreshAll()
      return resp.data as BodyNeed
    } finally {
      saving.value = false
    }
  }

  async function removeNeed(id: number) {
    saving.value = true
    try {
      await bodyApi.deleteBodyNeed(id)
      await refreshAll()
    } finally {
      saving.value = false
    }
  }

  return {
    // 状态
    meta,
    parts,
    needs,
    summary,
    loading,
    saving,
    lastError,
    // 派生
    available,
    unavailableReason,
    metricMetaByKey,
    findStatusOptions,
    satisfactionOptions,
    findStatusLabels,
    satisfactionLabels,
    blankReasonByValue,
    partById,
    subtitle,
    pendingCount,
    // 取数
    fetchMeta,
    fetchParts,
    fetchNeeds,
    fetchSummary,
    fetchAll,
    refreshAll,
    // 写入
    savePart,
    removePart,
    seedParts,
    saveNeed,
    patchNeed,
    removeNeed,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」）。⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒
// 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useBodyStore, import.meta.hot))
}
