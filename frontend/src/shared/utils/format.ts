/** 金额格式化工具（集成隐私脱敏） */

import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'

let _store: ReturnType<typeof usePrivacyStore> | null = null
function getStore() {
  if (!_store) {
    _store = usePrivacyStore()
  }
  return _store
}

function maskIfNeeded(raw: string): string {
  if (!getStore().privacyMode) return raw
  if (raw.length <= 2) return '**'
  return raw[0] + '*'.repeat(raw.length - 2) + raw[raw.length - 1]
}

export function formatAmount(
  value: number | null | undefined,
  precision = 2,
): string {
  if (value === null || value === undefined) return '0.00'
  const raw = Math.abs(value).toLocaleString('zh-CN', {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  })
  return maskIfNeeded(raw)
}
