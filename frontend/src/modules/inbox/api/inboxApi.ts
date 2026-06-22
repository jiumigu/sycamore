import request from '@/shared/utils/request'
import type { InboxItem, InboxStats, BatchActionPayload } from '../types/inboxTypes'

export function getInboxItems(params?: Record<string, unknown>) {
  return request<{ count: number; results: InboxItem[] }>({
    url: '/inbox/items/', method: 'get', params,
  })
}

export function createInboxItem(data: Record<string, unknown>) {
  return request<InboxItem>({ url: '/inbox/items/', method: 'post', data })
}

export function getInboxDetail(id: number) {
  return request<InboxItem>({ url: `/inbox/items/${id}/`, method: 'get' })
}

export function updateInboxItem(id: number, data: Record<string, unknown>) {
  return request<InboxItem>({ url: `/inbox/items/${id}/`, method: 'patch', data })
}

export function deleteInboxItem(id: number) {
  return request({ url: `/inbox/items/${id}/`, method: 'delete' })
}

export function completeInboxItem(id: number, data?: { completion_note?: string }) {
  return request<InboxItem>({ url: `/inbox/items/${id}/complete/`, method: 'post', data })
}

export function convertInboxItem(id: number, data: Record<string, unknown>) {
  return request<InboxItem>({ url: `/inbox/items/${id}/convert/`, method: 'post', data })
}

export function batchAction(data: BatchActionPayload) {
  return request({ url: '/inbox/items/batch/', method: 'post', data })
}

/** 获取今日待办（未完成且已到期） */
export function getTodayPending() {
  return request<{ count: number; results: InboxItem[] }>({
    url: '/inbox/items/today_pending/', method: 'get',
  })
}

export function getInboxStats() {
  return request<InboxStats>({ url: '/inbox/items/stats/', method: 'get' })
}

export function convertToGoal(data: {
  item_ids: number[]
  goal_name: string
  year?: number
  reward_per_milestone?: number
}) {
  return request<{
    goal_id: number
    goal_title: string
    milestone_count: number
    converted_count: number
  }>({ url: '/inbox/items/convert_to_goal/', method: 'post', data })
}
