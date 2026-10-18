import { acceptHMRUpdate, defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as treasureApi from '../api/treasureApi'
import type { GoodThing, TreasureMeta, TreasureOption } from '../types/treasureTypes'

export const useTreasureStore = defineStore('treasure', () => {
  const thingList = ref<GoodThing[]>([])
  const loading = ref(false)
  /**
   * 列表**取数失败**（区别于「一条都没有」）。
   *
   * 🔴 裸 `catch { thingList = [] }` 会把「接口挂了」画成「还没有记录」——
   *    用户看到的是「快添加一个吧」，于是去登记一条本来已经存在的记录。
   *    （迁移没执行时就是这个长相：Unknown column ⇒ 500 ⇒ 列表空。）
   */
  const loadError = ref(false)
  /** 口径与枚举（类别文案按侧各一套）—— 只在后端一份，前端不硬编码 */
  const meta = ref<TreasureMeta | null>(null)
  /** ⭐ 待补理由的条数：留空允许，但「留空」必须看得见 */
  const pendingCount = ref(0)

  /** meta 取不到时为 true ⇒ 界面显式提示，**不默默用一份前端默认文案顶上** */
  const metaUnavailable = computed(() => meta.value === null)

  async function fetchMeta() {
    try {
      const res = await treasureApi.getTreasureMeta()
      meta.value = res.data
    } catch {
      meta.value = null
    }
    return meta.value
  }

  /**
   * 某一侧的类别选项。
   *
   * ⚠️ 取不到时返回 **空数组**，不返回一份写死的前端默认值 ——
   *    后者会让「口径没取到」看起来像「这个模块本来就只有这些类别」。
   *    界面另有 `metaUnavailable` 提示，两条合起来才看得见问题。
   */
  function categoriesFor(recordType: string): TreasureOption[] {
    return meta.value?.categories_by_type?.[recordType] ?? []
  }

  async function fetchThingList(params?: Record<string, unknown>) {
    loading.value = true
    loadError.value = false
    try {
      const res = await treasureApi.getThingList(params)
      thingList.value = Array.isArray(res.data) ? res.data
        : res.data.results || []
    } catch {
      // ⚠️ 「取不到」与「没有」必须分得开 —— 置个标记让页面说出来
      thingList.value = []
      loadError.value = true
    } finally {
      loading.value = false
    }
  }

  /** 待补理由条数 —— 单独查一次（主列表可能正被别的条件筛着，数不准） */
  async function fetchPendingCount() {
    try {
      const res = await treasureApi.getThingList({ pending_reason: 1 })
      pendingCount.value = Array.isArray(res.data) ? res.data.length : 0
    } catch {
      pendingCount.value = 0
    }
  }

  async function createThing(data: Record<string, unknown>) {
    const res = await treasureApi.createThing(data)
    return res.data
  }

  async function updateThing(id: number, data: Record<string, unknown>) {
    const res = await treasureApi.updateThing(id, data)
    return res.data
  }

  async function deleteThing(id: number) {
    await treasureApi.deleteThing(id)
  }

  return {
    thingList, loading, loadError, meta, metaUnavailable, pendingCount,
    fetchMeta, categoriesFor, fetchThingList, fetchPendingCount,
    createThing, updateThing, deleteThing,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」）。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useTreasureStore, import.meta.hot))
}
