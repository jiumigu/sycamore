/** 隐私脱敏 composable */

import { computed } from 'vue'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'

export function usePrivacyMask() {
  const store = usePrivacyStore()
  const isActive = computed(() => store.privacyMode)

  function maskAmount(value: number | string | null | undefined): string {
    if (!isActive.value || value == null || value === '') return String(value ?? '')
    const str = String(value)
    if (str.length <= 2) return '**'
    return str[0] + '*'.repeat(str.length - 2) + str[str.length - 1]
  }

  function maskName(name: string | null | undefined): string {
    if (!isActive.value || !name) return name ?? ''
    if (name.length <= 1) return '*'
    return name[0] + '**'
  }

  function maskLocation(location: string | null | undefined): string {
    if (!isActive.value || !location) return location ?? ''
    if (location.length <= 1) return '*'
    return location[0] + '*'
  }

  function maskText(text: string | null | undefined): string {
    if (!isActive.value || !text) return text ?? ''
    if (text.length <= 1) return '*'
    return text[0] + '*'.repeat(Math.min(text.length - 1, 4))
  }

  function unmasked<T>(value: T): T {
    if (!isActive.value) return value
    return value
  }

  return { isActive, maskAmount, maskName, maskLocation, maskText, unmasked }
}
