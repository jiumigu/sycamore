import { defineStore } from 'pinia'
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
