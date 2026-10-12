import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as goalApi from '../api/goalApi'
import type { Action } from '../types/goalTypes'

export const useGoalBoardStore = defineStore('goalBoard', () => {
  /** 当前勾选的目标 ID 列表 */
  const selectedGoalIds = ref<number[]>([])

  /** actionsCache: goalId → Action[] */
  const actionsCache = ref<Record<number, Action[]>>({})

  const hasSelectedGoals = computed(() => selectedGoalIds.value.length > 0)

  function getActionsByGoal(goalId: number): Action[] {
    return actionsCache.value[goalId] || []
  }

  function getActionsCount(goalId: number): number {
    return getActionsByGoal(goalId).length
  }

  async function loadActions(goalId: number) {
    try {
      const response = await goalApi.getActionList({ goal_id: goalId })
      const list = Array.isArray(response.data) ? response.data
        : response.data.results || []
      actionsCache.value = { ...actionsCache.value, [goalId]: list }
      return list
    } catch (error) {
      console.error('获取行为记录失败:', error)
      throw error
    }
  }

  async function addAction(goalId: number, data: { name: string; milestone?: number | null; note?: string | null; action_date?: string | null }) {
    const response = await goalApi.createAction({ goal: goalId, ...data })
    const action = response.data
    const list = actionsCache.value[goalId] || []
    actionsCache.value = { ...actionsCache.value, [goalId]: [action, ...list] }
    return action
  }

  async function batchAddActions(goalIds: number[], data: { name: string; milestone_id?: number | null; note?: string | null; action_date?: string | null }) {
    const response = await goalApi.batchCreateActions({ goal_ids: goalIds, ...data })
    const actions: Action[] = Array.isArray(response.data) ? response.data : []
    // 按 goal_id 分组后更新缓存
    const byGoal: Record<number, Action[]> = {}
    for (const a of actions) {
      if (!byGoal[a.goal]) byGoal[a.goal] = []
      byGoal[a.goal].push(a)
    }
    const next = { ...actionsCache.value }
    for (const gid of goalIds) {
      next[gid] = [...(byGoal[gid] || []), ...(next[gid] || [])]
    }
    actionsCache.value = next
    return actions
  }

  async function updateAction(actionId: number, goalId: number, data: { name?: string; note?: string | null; milestone?: number | null; action_date?: string | null }) {
    const response = await goalApi.updateAction(actionId, data)
    const updated = response.data
    const list = actionsCache.value[goalId]
    if (list) {
      actionsCache.value = {
        ...actionsCache.value,
        [goalId]: list.map(a => a.id === actionId ? updated : a),
      }
    }
    return updated
  }

  async function deleteAction(actionId: number, goalId: number) {
    await goalApi.deleteAction(actionId)
    const list = actionsCache.value[goalId]
    if (list) {
      actionsCache.value = {
        ...actionsCache.value,
        [goalId]: list.filter(a => a.id !== actionId),
      }
    }
  }

  function toggleGoalSelection(goalId: number) {
    const idx = selectedGoalIds.value.indexOf(goalId)
    if (idx >= 0) {
      selectedGoalIds.value = selectedGoalIds.value.filter(id => id !== goalId)
    } else {
      selectedGoalIds.value = [...selectedGoalIds.value, goalId]
    }
  }

  function clearSelection() {
    selectedGoalIds.value = []
  }

  function resetState() {
    selectedGoalIds.value = []
    actionsCache.value = {}
  }

  return {
    selectedGoalIds, actionsCache, hasSelectedGoals,
    getActionsByGoal, getActionsCount,
    loadActions, addAction, batchAddActions,
    updateAction, deleteAction,
    toggleGoalSelection, clearSelection, resetState,
  }
})

// 开发期热更新：Vite 只重建 `.vue`，**Pinia 的 store 实例不会重建** ——
// 改本文件之后，页面上跑的还是旧定义（模板是新的、数据逻辑是旧的，
// 看起来像「功能没做」。2026-10-10 实例：流水列表「共 笔」是空的 + 空态误报）。
// ⚠️ 生产构建里 `import.meta.hot` 是 undefined ⇒ 整段被 tree-shake，对线上零影响。
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useGoalBoardStore, import.meta.hot))
}
