/**
 * 脱敏工具函数（纯函数，由调用方传入 enabled 状态）
 *
 * 配合 localStorage 的 privacy_mode 键使用：
 *   const enabled = localStorage.getItem('privacy_mode') === '1'
 */

/** 人名脱敏：吴琦 → 吴* */
export function maskName(value: string, enabled: boolean): string {
  if (!enabled || !value || value.length <= 1) return value || ''
  return value[0] + '*'
}

/** 标签脱敏：始终显示为 *** */
export function maskTags(tags: string | string[], enabled: boolean): string {
  if (!enabled) return Array.isArray(tags) ? tags.join(', ') : tags || ''
  return '***'
}

/** 地点脱敏：福州鼓楼区 → 福州*** */
export function maskLocation(value: string, enabled: boolean): string {
  if (!enabled || !value || value.length <= 2) return value || ''
  return value.substring(0, 2) + '***'
}

/** 文本脱敏（场景/身份等）：大学社团活动认识 → 大学*** */
export function maskText(value: string, enabled: boolean): string {
  if (!enabled || !value || value.length <= 2) return value || ''
  return value.substring(0, 2) + '***'
}

/** 金额脱敏：¥50,000 → ¥*,***.** */
export function maskAmount(value: number | null | undefined, enabled: boolean): string {
  if (!enabled) {
    if (value == null) return '¥0'
    const n = Math.round(value)
    if (n >= 10000) return '¥' + (n / 10000).toFixed(1) + '万'
    return '¥' + n.toLocaleString()
  }
  return '¥*,***.**'
}

/**
 * 按交易类型脱敏金额：收入脱敏，支出不脱敏
 * @param value 金额数值
 * @param transactionType 交易类型：'收入' / '支出'
 * @param enabled 脱敏开关
 */
export function maskAmountByType(
  value: number | string | null | undefined,
  transactionType: string,
  enabled: boolean,
): string {
  const num = typeof value === 'string' ? parseFloat(value) : (value ?? 0)
  const formatted = num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  // 支出不脱敏
  if (transactionType === '支出') return `¥${formatted}`

  // 收入脱敏
  if (enabled && num !== 0) return '¥*,***.**'

  return `¥${formatted}`
}
