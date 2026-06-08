import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as goalApi from '../api/goalApi'
import type { Goal, GoalListParams, GoalStats, GoalStatus, Milestone } from '../types/goalTypes'

export const useGoalStore = defineStore('goal', () => {
  const goalList = ref<Goal[]>([])
  const currentGoal = ref<Goal | null>(null)
  const stats = ref<GoalStats | null>(null)
  const loading = ref(false)
  const submitting = ref(false)
  const totalCount = ref(0)

  async function fetchGoalList(params?: GoalListParams) {
    loading.value = true
    try {
      const response = await goalApi.getGoalList(params as Record<string, unknown>)
      if (response.data.results) {
        goalList.value = response.data.results
        totalCount.value = response.data.count
      } else if (Array.isArray(response.data)) {
        goalList.value = response.data
        totalCount.value = response.data.length
      }
      return response.data
    } catch (error) {
      console.error('获取目标列表失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchGoalById(id: number) {
    loading.value = true
    try {
      const response = await goalApi.getGoalDetail(id)
      currentGoal.value = response.data
      return response.data
    } catch (error) {
      console.error('获取目标详情失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await goalApi.getGoalStats()
      stats.value = response.data
      return response.data
    } catch (error) {
      console.error('获取统计失败:', error)
      throw error
    }
  }

  async function createNewGoal(data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await goalApi.createGoal(data)
      return response.data
    } catch (error) {
      console.error('创建目标失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function updateExistingGoal(id: number, data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await goalApi.updateGoal(id, data)
      return response.data
    } catch (error) {
      console.error('更新目标失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function deleteExistingGoal(id: number) {
    try {
      await goalApi.deleteGoal(id)
      goalList.value = goalList.value.filter(g => g.id !== id)
      return true
    } catch (error) {
      console.error('删除目标失败:', error)
      throw error
    }
  }

  /**
   * 切换里程碑状态 — 乐观更新：先改本地数据再调 API
   * 返回完整响应（包含 milestone + goal_progress）
   */
  async function toggleMilestoneStatus(
    goalId: number, milestoneId: number, data: Record<string, unknown>,
  ) {
    // 乐观更新本地里程碑状态
    const goal = goalList.value.find(g => g.id === goalId)
    const ms = goal?.milestones?.find(m => m.id === milestoneId)
    if (ms && data.status) {
      ms.status = data.status as Milestone['status']
      if (data.completed_note !== undefined) ms.completed_note = data.completed_note as string
    }

    try {
      const response = await goalApi.toggleMilestone(goalId, milestoneId, data)
      // 用服务端数据修正本地缓存
      const result = response.data
      if (result.milestone && goal?.milestones) {
        const idx = goal.milestones.findIndex(m => m.id === milestoneId)
        if (idx !== -1) goal.milestones[idx] = result.milestone
      }
      if (result.goal_progress !== undefined && goal) {
        goal.progress_percentage = result.goal_progress
      }
      return result
    } catch (error) {
      // 回滚
      if (ms && data.status) {
        const prev = ms.status === 'completed' ? 'pending' : ms.status === 'pending' ? 'in-progress' : 'completed'
        ms.status = prev as Milestone['status']
      }
      console.error('切换里程碑状态失败:', error)
      throw error
    }
  }

  /**
   * 更新目标状态 — 乐观更新，失败回滚
   */
  async function updateGoalStatus(id: number, status: GoalStatus) {
    const goal = goalList.value.find(g => g.id === id)
    const prevStatus = goal?.status
    if (goal) goal.status = status

    try {
      await goalApi.patchGoal(id, { status })
    } catch (error) {
      if (goal && prevStatus) goal.status = prevStatus
      console.error('更新目标状态失败:', error)
      throw error
    }
  }

  /**
   * 更新里程碑（使用 MilestoneViewSet PATCH 端点）
   * 服务端返回 { milestone, goal_progress, goal_status }
   */
  async function updateMilestoneStatus(milestoneId: number, data: Record<string, unknown>, goalId: number) {
    // 乐观更新本地里程碑状态
    const goal = goalList.value.find(g => g.id === goalId)
    const ms = goal?.milestones?.find(m => m.id === milestoneId)
    if (ms) {
      if (data.status) ms.status = data.status as Milestone['status']
      if (data.completed_note !== undefined) ms.completed_note = data.completed_note as string | null
    }

    try {
      const response = await goalApi.patchMilestone(milestoneId, data)
      const result = response.data
      // 用服务端数据修正本地缓存
      if (result.milestone && goal?.milestones) {
        const idx = goal.milestones.findIndex(m => m.id === milestoneId)
        if (idx !== -1) goal.milestones[idx] = result.milestone
      }
      if (result.goal_progress !== undefined && goal) {
        goal.progress_percentage = result.goal_progress
      }
      return result
    } catch (error) {
      // 回滚 — 重新加载目标详情恢复正确状态
      if (goal && ms) {
        try {
          const detail = await goalApi.getGoalDetail(goalId)
          if (detail.data?.milestones) {
            goal.milestones = detail.data.milestones
          }
          if (detail.data?.progress_percentage !== undefined) {
            goal.progress_percentage = detail.data.progress_percentage
          }
        } catch { /* 静默 */ }
      }
      console.error('更新里程碑失败:', error)
      throw error
    }
  }

  async function quickCreateGoal(data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await goalApi.quickCreateGoal(data)
      return response.data
    } catch (error) {
      console.error('快速创建失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  async function cloneGoal(id: number, data: Record<string, unknown>) {
    submitting.value = true
    try {
      const response = await goalApi.cloneGoal(id, data)
      return response.data
    } catch (error) {
      console.error('复制目标失败:', error)
      throw error
    } finally {
      submitting.value = false
    }
  }

  function resetState() {
    goalList.value = []
    currentGoal.value = null
    stats.value = null
    loading.value = false
    submitting.value = false
    totalCount.value = 0
  }

  return {
    goalList, currentGoal, stats, loading, submitting, totalCount,
    fetchGoalList, fetchGoalById, fetchStats, createNewGoal,
    updateExistingGoal, deleteExistingGoal, toggleMilestoneStatus,
    updateGoalStatus, updateMilestoneStatus,
    quickCreateGoal, cloneGoal,
    resetState,
  }
})
