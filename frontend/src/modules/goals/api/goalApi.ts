import request from '@/shared/utils/request'

export function getGoalList(params?: Record<string, unknown>) {
  return request({ url: '/goals/goals/', method: 'get', params })
}

export function getGoalDetail(id: number) {
  return request({ url: `/goals/goals/${id}/`, method: 'get' })
}

export function createGoal(data: Record<string, unknown>) {
  return request({ url: '/goals/goals/', method: 'post', data })
}

export function updateGoal(id: number, data: Record<string, unknown>) {
  return request({ url: `/goals/goals/${id}/`, method: 'put', data })
}

export function patchGoal(id: number, data: Record<string, unknown>) {
  return request({ url: `/goals/goals/${id}/`, method: 'patch', data })
}

export function deleteGoal(id: number) {
  return request({ url: `/goals/goals/${id}/`, method: 'delete' })
}

export function bulkDeleteGoals(ids: number[]) {
  return request({ url: '/goals/goals/bulk_delete/', method: 'delete', data: { ids } })
}

export function getGoalStats() {
  return request({ url: '/goals/goals/stats/', method: 'get' })
}

export function toggleMilestone(goalId: number, milestoneId: number, data: Record<string, unknown>) {
  return request({
    url: `/goals/goals/${goalId}/toggle_milestone/`,
    method: 'post',
    data: { milestone_id: milestoneId, ...data },
  })
}

/** 更新里程碑字段（复用 toggle_milestone 端点） */
export function updateMilestone(goalId: number, milestoneId: number, data: Record<string, unknown>) {
  return toggleMilestone(goalId, milestoneId, data)
}

/** 里程碑 ViewSet PATCH 端点 */
export function patchMilestone(id: number, data: Record<string, unknown>) {
  return request({ url: `/goals/milestones/${id}/`, method: 'patch', data })
}

/** 创建里程碑 */
export function createMilestone(data: Record<string, unknown>) {
  return request({ url: '/goals/milestones/', method: 'post', data })
}

/** 获取里程碑列表 */
export function getMilestoneList(params?: Record<string, unknown>) {
  return request({ url: '/goals/milestones/', method: 'get', params })
}

export function recalculateProgress(id: number) {
  return request({ url: `/goals/goals/${id}/recalculate/`, method: 'post' })
}

export function quickCreateGoal(data: Record<string, unknown>) {
  return request({ url: '/goals/goals/quick_create/', method: 'post', data })
}

export function cloneGoal(id: number, data: Record<string, unknown>) {
  return request({ url: `/goals/goals/${id}/clone/`, method: 'post', data })
}

export function createAction(data: Record<string, unknown>) {
  return request({ url: '/goals/actions/', method: 'post', data })
}

export function batchCreateActions(data: Record<string, unknown>) {
  return request({ url: '/goals/actions/batch/', method: 'post', data })
}

export function updateAction(id: number, data: Record<string, unknown>) {
  return request({ url: `/goals/actions/${id}/`, method: 'patch', data })
}

export function deleteAction(id: number) {
  return request({ url: `/goals/actions/${id}/`, method: 'delete' })
}

export function getActionList(params?: Record<string, unknown>) {
  return request({ url: '/goals/actions/', method: 'get', params })
}

/** 今日打卡 */
export function checkinAction(actionId: number) {
  return request({ url: `/goals/actions/${actionId}/checkin/`, method: 'post' })
}

/** 打卡统计数据 */
export function getCheckinStats(actionId: number) {
  return request({ url: `/goals/actions/${actionId}/checkin_stats/`, method: 'get' })
}

/** 获取今日未完成的行为 */
export function getTodayPending() {
  return request({ url: '/goals/actions/today_pending/', method: 'get' })
}

export function getReviewList(params?: Record<string, unknown>) {
  return request({ url: '/goals/reviews/', method: 'get', params })
}

export function createReview(data: Record<string, unknown>) {
  return request({ url: '/goals/reviews/', method: 'post', data })
}

export function updateReview(id: number, data: Record<string, unknown>) {
  return request({ url: `/goals/reviews/${id}/`, method: 'put', data })
}

export function deleteReview(id: number) {
  return request({ url: `/goals/reviews/${id}/`, method: 'delete' })
}

// ────────── 产出记录（良品率） ──────────

export function createOutputRecord(data: Record<string, unknown>) {
  return request({ url: '/goals/outputs/', method: 'post', data })
}
