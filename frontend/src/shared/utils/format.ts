/** 金额格式化工具（集成隐私脱敏） */

import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { maskAmountText } from '@/shared/utils/privacy'

// 惰性取 store：本模块的函数在 setup 之外也可能被调用（如 el-table formatter）
let _store: ReturnType<typeof usePrivacyStore> | null = null
function getStore() {
  if (!_store) {
    _store = usePrivacyStore()
  }
  return _store
}

/**
 * 数值 → 本地化金额串（千分位 + 固定精度），隐私模式下整串掩码。
 *
 * ⚠️ 负号保留：旧实现用 `Math.abs(value)` 会把负净值／负债显示成正数。
 * 需要连符号一起渲染（货币符号在前，`¥-1,234.50`）请用 `formatSignedAmount`。
 */
export function formatAmount(value: number | null | undefined, precision = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0.00'
  const raw = value.toLocaleString('zh-CN', {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  })
  return maskAmountText(raw, getStore().privacyMode)
}

/**
 * 带符号金额 —— 本项目**统一口径：货币符号在前、正负号紧随其后**。
 *   正数 `¥1,234.50` ／ 显式正号 `¥+1,234.50` ／ 负数 `¥-1,234.50`
 *
 * ⚠️ 不要写成 `-¥1,234.50`（符号在货币符号之前），全项目只有这一种口径。
 * 隐私模式下只掩码金额主体，符号位保留：既掩掉数值，又保留收／支方向。
 *
 * @param precision 小数位
 * @param showPlus  正数是否显式带 `+`（流水／账目类场景传 true）
 */
export function formatSignedAmount(
  value: number | null | undefined,
  precision = 2,
  showPlus = false,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return `¥${formatAmount(0, precision)}`
  }
  const sign = value < 0 ? '-' : showPlus ? '+' : ''
  return `¥${sign}${formatAmount(Math.abs(value), precision)}`
}
