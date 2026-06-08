/** 通知 — Store */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import { getUnreadCount } from '@/core/notifications/api/notificationApi'

export const useNotificationStore = defineStore('notification', () => {
  const unreadCount = ref(0)

  async function fetchUnreadCount() {
    try {
      const res = await getUnreadCount()
      unreadCount.value = res.data.count
    } catch {
      unreadCount.value = 0
    }
  }

  return { unreadCount, fetchUnreadCount }
})
