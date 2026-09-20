/**
 * 脱敏工具 —— 全站唯一规则源（纯函数，由调用方传入 enabled 状态）
 *
 * 状态来源：后端 `core_user_profile.privacy_mode` → `privacyStore.privacyMode`。
 * 组件内优先用 `usePrivacyMask()`（自动注入该状态）；这里的纯函数供 composable
 * 与不方便取 store 的场景（如 el-table 的 formatter）调用。
 *
 * 统一口径（此前有三份并行实现、规则互不相同，已收敛到本文件）：
 *   人名  保留首字：吴琦 → 吴**
 *   地点  保留首字：福州鼓楼区 → 福***
 *   文本  保留首字：大学社团活动 → 大***
 *   整段  ***（备注、付出、标签等）
 *   金额  整串掩码：*,***.**（不保留任何位——旧实现保留末位会泄漏精度位）
 *   利率  *.**%
 * 星号数量固定，不泄漏原始长度。
 */

/** 整段掩码 */
export const MASK_TEXT = '***'
/** 人名掩码后缀 */
export const MASK_NAME = '**'
/** 金额掩码（不含 ¥，便于调用方自行拼接） */
export const MASK_AMOUNT = '*,***.**'
/** 紧凑场景（日历格等窄容器）用的短金额掩码 */
export const MASK_AMOUNT_COMPACT = '*,***'
/** 利率掩码 */
export const MASK_RATE = '*.**%'

/** 保留首字符的通用掩码：首字 + 固定后缀 */
function maskHead(value: unknown, enabled: boolean, suffix: string): string {
  if (value === null || value === undefined) return ''
  const str = String(value)
  if (!str) return ''
  if (!enabled) return str
  return str.slice(0, 1) + suffix
}

/** 数值 → 千分位金额串（不做脱敏） */
function plainAmount(value: number | string | null | undefined): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (num === null || num === undefined || Number.isNaN(num)) return '0'
  return num.toLocaleString('zh-CN')
}

/** 人名脱敏：吴琦 → 吴** */
export function maskName(value: string | null | undefined, enabled: boolean): string {
  return maskHead(value, enabled, MASK_NAME)
}

/** 标签脱敏：始终显示为 *** */
export function maskTags(tags: string | string[] | null | undefined, enabled: boolean): string {
  if (!enabled) return Array.isArray(tags) ? tags.join(', ') : tags ?? ''
  return MASK_TEXT
}

/** 地点脱敏：福州鼓楼区 → 福*** */
export function maskLocation(value: string | null | undefined, enabled: boolean): string {
  return maskHead(value, enabled, MASK_TEXT)
}

/** 文本脱敏（场景/身份等）：大学社团活动 → 大*** */
export function maskText(value: string | null | undefined, enabled: boolean): string {
  return maskHead(value, enabled, MASK_TEXT)
}

/** 整段掩码（备注、付出、原因等）：不保留任何字符 */
export function maskFreeText(value: string | null | undefined, enabled: boolean): string {
  if (!enabled) return value ?? ''
  return MASK_TEXT
}

/** 利率脱敏：3.25 → *.**% */
export function maskRate(value: number | string | null | undefined, enabled: boolean): string {
  if (!enabled) {
    if (value === null || value === undefined || value === '') return '-'
    return `${value}%`
  }
  return MASK_RATE
}

/**
 * 已格式化金额串的掩码：1,234.50 → *,***.**（不含 ¥）
 * 供 `usePrivacyMask().maskAmount()` 与需要自行拼接 ¥ 的场景使用。
 */
export function maskAmountText(_formatted: unknown, enabled: boolean): string {
  if (!enabled) return String(_formatted ?? '')
  return MASK_AMOUNT
}

/** 金额脱敏（含 ¥，可直接渲染）：50000 → ¥50,000 ／ 隐私模式 → ¥*,***.** */
export function maskAmount(value: number | string | null | undefined, enabled: boolean): string {
  if (enabled) return `¥${MASK_AMOUNT}`
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (num === null || num === undefined || Number.isNaN(num)) return '¥0'
  const n = Math.round(num)
  if (Math.abs(n) >= 10000) return `¥${(n / 10000).toFixed(1)}万`
  return `¥${n.toLocaleString('zh-CN')}`
}

/**
 * 按交易类型脱敏金额：收入脱敏，支出不脱敏
 *
 * ⚠️ 不变量：「支出不脱敏」是刻意设计（便于核对开销），不要改成全掩。
 * @param value 金额数值
 * @param transactionType 交易类型：'收入' / '支出'
 * @param enabled 脱敏开关
 */
export function maskAmountByType(
  value: number | string | null | undefined,
  transactionType: string,
  enabled: boolean,
): string {
  const parsed = typeof value === 'string' ? parseFloat(value) : (value ?? 0)
  const num = Number.isNaN(parsed) ? 0 : parsed
  const formatted = num.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

  // 支出不脱敏
  if (transactionType === '支出') return `¥${formatted}`

  // 收入脱敏
  if (enabled && num !== 0) return `¥${MASK_AMOUNT}`

  return `¥${formatted}`
}

/** 金额的简式显示（不含 ¥，掩码时返回短掩码串）：日历格等紧凑场景用 */
export function maskAmountCompact(
  value: number | string | null | undefined,
  enabled: boolean,
): string {
  if (enabled) return MASK_AMOUNT_COMPACT
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (num === null || num === undefined || Number.isNaN(num)) return '0'
  return plainAmount(Math.round(num))
}
