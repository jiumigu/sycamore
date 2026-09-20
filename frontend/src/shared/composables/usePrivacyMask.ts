/**
 * 隐私脱敏 composable —— 自动注入 privacyStore 状态
 *
 * 规则全部委托 `shared/utils/privacy.ts`（唯一真源），本文件只负责把
 * `privacyStore.privacyMode` 喂进去，不再自带任何掩码逻辑。
 */

import { computed } from 'vue'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import {
  maskName as maskNamePure,
  maskTags as maskTagsPure,
  maskLocation as maskLocationPure,
  maskText as maskTextPure,
  maskFreeText as maskFreeTextPure,
  maskRate as maskRatePure,
  maskAmountText,
  maskAmountByType as maskAmountByTypePure,
} from '@/shared/utils/privacy'

export function usePrivacyMask() {
  const store = usePrivacyStore()
  const isActive = computed(() => store.privacyMode)

  /** 已格式化金额串的掩码：'1,234.50' → '*,***.**'（不含 ¥） */
  function maskAmount(value: number | string | null | undefined): string {
    return maskAmountText(value, isActive.value)
  }

  function maskName(name: string | null | undefined): string {
    return maskNamePure(name, isActive.value)
  }

  function maskTags(tags: string | string[] | null | undefined): string {
    return maskTagsPure(tags, isActive.value)
  }

  function maskLocation(location: string | null | undefined): string {
    return maskLocationPure(location, isActive.value)
  }

  function maskText(text: string | null | undefined): string {
    return maskTextPure(text, isActive.value)
  }

  function maskFreeText(text: string | null | undefined): string {
    return maskFreeTextPure(text, isActive.value)
  }

  function maskRate(rate: number | string | null | undefined): string {
    return maskRatePure(rate, isActive.value)
  }

  function maskAmountByType(value: number | string | null | undefined, type: string): string {
    return maskAmountByTypePure(value, type, isActive.value)
  }

  return {
    isActive,
    maskAmount,
    maskName,
    maskTags,
    maskLocation,
    maskText,
    maskFreeText,
    maskRate,
    maskAmountByType,
  }
}
