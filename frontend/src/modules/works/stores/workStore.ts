/** 作品 · store
 *
 * 🔴 独立 store（不塞进 selfrun）—— 本模块跨四个模块取来源，
 *    它不属于自我运转。两边的接合点只有一个：`works_count` 取数器。
 *
 * ⚠️ **接口层返回的是 axios 包装**（`request<T>` ⇒ `AxiosResponse<T>`）——
 *    取值一律 `res.data`；写成 `res` 只会得到整个响应对象，
 *    表现在页面上是「一条都没有」/「undefined 且不报错」。
 */
import { acceptHMRUpdate, defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '../api/workApi'
import type {
  PeriodType, Work, WorkCapture, WorkMeta, WorksOverview,
} from '../types/workTypes'

export const useWorkStore = defineStore('works', () => {
  const loading = ref(false)
  const works = ref<Work[]>([])
  const captures = ref<WorkCapture[]>([])
  const overview = ref<WorksOverview | null>(null)
  /** 🔴 枚举**由后端下发** —— 前端不抄第二份 */
  const meta = ref<WorkMeta | null>(null)

  /** 🔴 **模块就绪信号**（谁都能用它判「本模块到底能不能用」）。
   *
   *  ⚠️ 判据必须落在**一个必然要碰新表的请求**上 —— 用 `meta` 判是**错的**：
   *     `meta` 只读常量 + `core_system_preset`，**新表没建也回 200** ⇒
   *     界面会把「读不到作品库」显示成「这周 0 件」，看着像「你这周什么都没留下」。
   *     这正是本项目最怕的那种失败：**给一个看着合理的错值**。
   */
  const ready = ref(false)

  /** 收口台的期（固定按周 —— 它问的是「这周留下了什么」）。 */
  const periodType = ref<PeriodType>('weekly')

  // ── 派生（**只做筛选与分桶，不重算任何口径**）─────────────────
  /** 待提炼：还没被收进任何作品的（不限期 —— 上周没提炼的还在）。 */
  const pendingCaptures = computed(() =>
    captures.value.filter((c) => c.status === 'pending'),
  )
  /** 本期勾的（不论提炼与否）—— 扁条上的那个 M */
  const currentCaptures = computed(() =>
    captures.value.filter((c) => c.in_current_period),
  )
  /** 本期成形的作品 —— 扁条上的那个 N。
   *  ⚠️ 判据来自后端的 `in_current_period`，前端**不**自己比 `period_key` 字符串。 */
  const currentWorks = computed(() => works.value.filter((w) => w.in_current_period))

  const kindOptions = computed(() => meta.value?.kinds ?? [])
  const statusOptions = computed(() => meta.value?.statuses ?? [])
  const channelOptions = computed(() => meta.value?.channels ?? [])

  // ── actions ────────────────────────────────────────────────
  async function loadMeta() {
    const res = await api.getMeta()
    meta.value = res.data
  }

  async function loadOverview() {
    const res = await api.getOverview()
    overview.value = res.data
    ready.value = true
  }

  async function loadWorks() {
    const res = await api.getWorks({ period_type: periodType.value })
    works.value = res.data
  }

  async function loadCaptures() {
    const res = await api.getCaptures({ period_type: periodType.value })
    captures.value = res.data
  }

  /** 一次拉齐（页面进入时）。`meta` 只拉一次就够，重复拉不报错也不贵。 */
  async function loadAll() {
    loading.value = true
    try {
      await Promise.all([loadMeta(), loadOverview(), loadWorks(), loadCaptures()])
    } finally {
      loading.value = false
    }
  }

  async function createWork(data: Record<string, unknown>) {
    const res = await api.createWork(data)
    await Promise.all([loadWorks(), loadOverview()])
    return res.data.work
  }

  async function updateWork(id: number, data: Record<string, unknown>) {
    const res = await api.updateWork(id, data)
    await loadWorks()
    return res.data.work
  }

  async function removeWork(id: number) {
    const res = await api.deleteWork(id)
    // ⚠️ 删作品会把来源**放回待提炼** ⇒ 捕获列表也要重拉（不然收口台上看不见它们回来）
    await Promise.all([loadWorks(), loadCaptures(), loadOverview()])
    return res.data
  }

  async function composeWork(data: Record<string, unknown>) {
    const res = await api.compose(data)
    await Promise.all([loadWorks(), loadCaptures(), loadOverview()])
    return res.data.work
  }

  async function doCapture(data: {
    source_type: string; source_id: number; title: string; excerpt?: string
  }) {
    const res = await api.capture(data)
    await Promise.all([loadCaptures(), loadOverview()])
    return res.data
  }

  async function undoCapture(id: number) {
    const res = await api.uncapture(id)
    await Promise.all([loadCaptures(), loadOverview()])
    return res.data
  }

  return {
    loading, works, captures, overview, meta, periodType, ready,
    pendingCaptures, currentCaptures, currentWorks,
    kindOptions, statusOptions, channelOptions,
    loadMeta, loadOverview, loadWorks, loadCaptures, loadAll,
    createWork, updateWork, removeWork, composeWork, doCapture, undoCapture,
  }
})

if (import.meta.hot) {
  acceptHMRUpdate(useWorkStore, import.meta.hot)
}
