/** 通知 — API 层 */

import request from '@/shared/utils/request'

export function getUnreadCount() {
  return request<{ count: number }>({ url: '/core/notifications/unread_count/', method: 'get' })
}
