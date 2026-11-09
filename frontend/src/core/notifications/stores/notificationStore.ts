/** 通知 — Store */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  generateNotifications,
  getNotifications,
  getUnreadCount,
  markAllRead as apiMarkAllRead,
  markRead as apiMarkRead,
  type NotificationItem,
} from '@/core/notifications/api/notificationApi'

export const useNotificationStore = defineStore('notification', () => {
  const unreadCount = ref(0)
  const list = ref<NotificationItem[]>([])
  const loading = ref(false)
  /** 取不到时保留原因，**不要把它显示成「没有通知」**（§2 裸 catch） */
  const loadError = ref('')

  function pickRows(payload: unknown): NotificationItem[] {
    if (Array.isArray(payload)) return payload as NotificationItem[]
    const maybe = payload as { results?: NotificationItem[] } | null
    return maybe?.results ?? []
  }

  /** 只刷新角标（布局挂载时用，代价最小） */
  async function fetchUnreadCount() {
    try {
      const res = await getUnreadCount()
      unreadCount.value = res.data.count
    } catch {
      // 角标失败不打扰用户，但也不谎报成 0：保持上一次的值
    }
  }

  /** 打开通知中心时：先让后端生成（30 分钟节流），再取列表与角标 */
  async function refresh() {
    loading.value = true
    loadError.value = ''
    try {
      await generateNotifications()
      const [rowsRes, countRes] = await Promise.all([getNotifications(), getUnreadCount()])
      list.value = pickRows(rowsRes.data)
      unreadCount.value = countRes.data.count
    } catch (err) {
      loadError.value = err instanceof Error ? err.message : '通知加载失败'
    } finally {
      loading.value = false
    }
  }

  async function markRead(id: number) {
    const row = list.value.find((r) => r.id === id)
    if (row && row.is_read) return
    try {
      await apiMarkRead(id)
      if (row) row.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch {
      // 失败则不改本地状态 —— 刷新后以后端为准
    }
  }

  async function markAllRead() {
    try {
      const res = await apiMarkAllRead()
      if (res.data.updated > 0) {
        list.value.forEach((r) => { r.is_read = true })
        unreadCount.value = 0
      }
    } catch {
      // 同上
    }
  }

  return { unreadCount, list, loading, loadError, fetchUnreadCount, refresh, markRead, markAllRead }
})
