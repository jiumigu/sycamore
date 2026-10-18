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
 * 「取不到」的金额占位符 —— 全项目只此一个常量。
 *
 * 🔴 别在界面里再写 `'—'` 字面量（更别写 `'-'` / `'--'`）：
 *    要判断「这格是不是空」时拿它比，改口径只改这里。
 */
export const EMPTY_AMOUNT = '—'

/**
 * 数值 → 本地化金额串（千分位 + 固定精度），隐私模式下整串掩码。
 *
 * 🔴 `null` / `undefined` / `NaN` ⇒ **`—`（取不到）**，不是 `0.00`。
 *    「取不到」与「0 元」是两件事：后者是一个**结论**（确实没有这笔钱），
 *    前者是「这一格没数据」。渲染成同一个样子，界面上就会长出一个
 *    **看着合理的错数** —— 2026-10-18 的 `non_liquid` 漏声明就是这样：
 *    后端没下发这个键，前端 `undefined` → `0.00`，看起来像「这笔钱真的不存在」，
 *    连着两轮被误判成「后端没重启」。
 *
 *    所以：要显示 0 就传 `0`；要把「缺省当 0」请在**调用点**显式写 `x ?? 0`
 *    —— 让「我确实当作 0」这个决定留在看得见的地方。
 *
 * ⚠️ 负号保留：旧实现用 `Math.abs(value)` 会把负净值／负债显示成正数。
 * 需要连符号一起渲染（货币符号在前，`¥-1,234.50`）请用 `formatSignedAmount`。
 */
export function formatAmount(value: number | null | undefined, precision = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY_AMOUNT
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
 *
 * 🔴 `null` / `undefined` / `NaN` ⇒ `—`（**不带 `¥`**）。
 *    写成 `¥—` 会让占位符看起来像一个金额，读起来比 `0.00` 更难辨认。
 */
export function formatSignedAmount(
  value: number | null | undefined,
  precision = 2,
  showPlus = false,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return EMPTY_AMOUNT
  }
  const sign = value < 0 ? '-' : showPlus ? '+' : ''
  return `¥${sign}${formatAmount(Math.abs(value), precision)}`
}
