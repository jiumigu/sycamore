import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as treasureApi from '../api/treasureApi'
import type { GoodThing } from '../types/treasureTypes'

export const useTreasureStore = defineStore('treasure', () => {
  const thingList = ref<GoodThing[]>([])
  const loading = ref(false)

  async function fetchThingList(params?: Record<string, unknown>) {
    loading.value = true
    try {
      const res = await treasureApi.getThingList(params)
      thingList.value = Array.isArray(res.data) ? res.data
        : res.data.results || []
    } catch {
      thingList.value = []
    } finally {
      loading.value = false
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
    thingList, loading,
    fetchThingList, createThing, updateThing, deleteThing,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useTreasureStore, import.meta.hot))
}
