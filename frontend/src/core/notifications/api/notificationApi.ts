/** 通知 — API 层 */

import request from '@/shared/utils/request'

export interface NotificationItem {
  id: number
  source_module: string
  source_object_id: number | null
  category: 'reminder' | 'alert' | 'info'
  title: string
  body: string
  action_url: string
  is_read: boolean
  created_at: string
}

export function getUnreadCount() {
  return request<{ count: number }>({ url: '/core/notifications/unread_count/', method: 'get' })
}

export function getNotifications() {
  return request<NotificationItem[] | { results: NotificationItem[] }>({
    url: '/core/notifications/',
    method: 'get',
    params: { page_size: 20 },
  })
}

/** 生成通知（后端 30 分钟节流，重复调用安全） */
export function generateNotifications(force = false) {
  return request<{ ran: boolean }>({
    url: '/core/notifications/generate/',
    method: 'post',
    params: force ? { force: 1 } : {},
  })
}

export function markRead(id: number) {
  return request<{ id: number; is_read: boolean }>({
    url: `/core/notifications/${id}/read/`,
    method: 'post',
  })
}

export function markAllRead() {
  return request<{ updated: number }>({ url: '/core/notifications/read_all/', method: 'post' })
}
