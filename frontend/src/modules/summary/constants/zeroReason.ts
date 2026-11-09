/**
 * 维度为 0 的原因码 → 文案（唯一实现）
 *
 * 后端下发 `zero_reason`，前端只查表，绝不自己拼「因为…所以…」。
 * 新增原因码时改这里一处，MonthlyModal / ModuleBar 同步生效。
 */

/** 极简标签，用于窄位置（如进度条行尾） */
export const ZERO_REASON_TEXT: Record<string, string> = {
  no_data: '无记录',
  net_negative: '净流出',
}

/** 悬停解释，说明「为什么 0 分」而不是让用户猜 */
export const ZERO_REASON_HINT: Record<string, string> = {
  no_data: '该区间没有任何收支记录，不是「净收入 0 元」',
  net_negative: '净收入为负：本维度按 0 分计，亏损金额照实显示',
}

export function zeroReasonText(reason?: string | null): string {
  return reason ? (ZERO_REASON_TEXT[reason] ?? '') : ''
}

export function zeroReasonHint(reason?: string | null): string {
  return reason ? (ZERO_REASON_HINT[reason] ?? '') : ''
}
