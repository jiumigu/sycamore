/**
 * 接口错误 → 人话（唯一实现）
 *
 * 🔴 为什么必须收口到一处：这条逻辑一旦各写各的，就会在同一件事上分叉 ——
 *    「500 该不该把调试页读给用户看」这种判断，分叉之后没人知道哪份是对的。
 *    （同项目判据：脱敏 / 金额格式化都只有一份实现）
 *
 * ── 两道闸门 ──
 *
 * ① **先按状态码分流。** 5xx 不是用户填错了：`DEBUG=True` 下 Django 回的是
 *    一整页 HTML Traceback（实测 20KB+）。把它塞进提示条，等于让用户读栈；
 *    而且那坨文本会把提示条撑满整屏、**盖住后面的按钮**（实测点不动）。
 *
 * ② **兜住任何非人话的长串。** 只留一句、限长。
 *
 * ⚠️ 4xx **必须原样透出** —— 「会变成负数」这类是用户能改的，
 *    兜成「保存失败」等于把可行动的信息丢掉（项目硬坑：只回「保存失败」= 用户只能瞎猜）。
 */

/** 从 DRF 的几种错误体里挑出一句人话 */
function pickMessage(data: unknown): string {
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>
    if (typeof record.detail === 'string') return record.detail
    for (const value of Object.values(record)) {
      if (typeof value === 'string') return value
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    }
  }
  return ''
}

/** 非人话（HTML / 栈）丢掉；人话留一句，最长 120 字 */
function truncate(text: string): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  if (!flat) return ''
  if (flat.startsWith('<') || /Traceback|Exception Value|Request Method/i.test(flat)) {
    return ''
  }
  return flat.length > 120 ? `${flat.slice(0, 120)}…` : flat
}

/** 5xx 的兜底文案：不是用户的问题，别让他去猜自己哪里填错了 */
export const SERVER_ERROR_TEXT = '服务端出错了（500）—— 请稍后重试；若刚升级过，先确认数据库迁移已执行'

/**
 * 把任意请求错误说成一句能给用户看的话。
 *
 * @param err axios 抛出的错误（未做类型约束，调用方拿到的多是 unknown）
 * @param fallback 实在取不到时用的兜底话术
 */
export function apiErrorText(err: unknown, fallback = '操作失败'): string {
  const box = err as {
    response?: { data?: unknown; status?: number }
    message?: string
  }
  const status = box?.response?.status
  if (typeof status === 'number' && status >= 500) return SERVER_ERROR_TEXT
  const picked = pickMessage(box?.response?.data)
  if (picked) return truncate(picked) || fallback
  return truncate(box?.message || '') || fallback
}
