/** 隐私模式 — Store */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import { getProfile, updateProfile } from '@/core/privacy/api/privacyApi'

export const usePrivacyStore = defineStore('privacy', () => {
  const privacyMode = ref(false)
  const loaded = ref(false)

  async function fetchProfile() {
    try {
      const res = await getProfile()
      privacyMode.value = res.data.privacy_mode
      loaded.value = true
    } catch {
      privacyMode.value = false
      loaded.value = true
    }
  }

  async function togglePrivacyMode() {
    const newValue = !privacyMode.value
    try {
      await updateProfile({ privacy_mode: newValue })
      privacyMode.value = newValue
    } catch {
      // 静默失败，保留原值
    }
  }

  return { privacyMode, loaded, fetchProfile, togglePrivacyMode }
})
