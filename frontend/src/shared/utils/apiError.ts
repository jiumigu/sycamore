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
 *
 * ── 全仓纪律（v3.64.8 起）──
 *
 * 🔴 **禁止再出现 `ElMessage.error('保存失败')` 这类手写字面量**。它把后端已经算好的
 *    原因整个丢掉，用户只能盲猜哪一格填错了。一律写成 `apiErrorText(err, '兜底话术')`，
 *    且 `catch` 必须接住 `err` —— `catch {` 不带参数等于源头就断了。
 *    2026-10-30 做过一轮清零（27 处），新增代码照此办理。
 *
 * ⚠️ `catch` 若同时捕获「用户点取消确认框」，取消必须先被识别并提前 return ——
 *    否则 `apiErrorText('cancel')` 取不到 message，会退化成兜底文案，
 *    把「我自己点的取消」说成「保存失败」。
 */

/**
 * DRF 用这几个 key 装「整表级」错误，它们**不是字段名**，
 * 显示成「non_field_errors：xxx」只会让用户更懵。
 */
const NON_FIELD_KEYS = new Set(['detail', 'non_field_errors'])

/** 从错误值里取第一句 —— DRF 的字段错误是 `['消息']`，也有直接给字符串的 */
function firstLine(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  return ''
}

/** 从 DRF 的几种错误体里挑出一句人话 */
function pickMessage(data: unknown): string {
  if (typeof data === 'string') return data
  if (!data || typeof data !== 'object') return ''
  const record = data as Record<string, unknown>

  // `detail` 是整表级错误，最明确，先认它
  if (typeof record.detail === 'string') return record.detail

  // 🔴 字段级错误要**带上字段名**。
  //    2026-10-16 的现场：映射码超长，后端回 `{"code": ["映射码最长 20 个字符…"]}`，
  //    但这条链上多处只显示「消息」本身 —— 一句话掉进提示条，用户不知道是
  //    哪一格填错了。带上 key 至少能定位；正解是后端给中文 error_messages，
  //    让消息自己说清字段名（见 AssetAccountFormSerializer）。
  for (const [key, value] of Object.entries(record)) {
    const text = firstLine(value)
    if (!text) continue
    return NON_FIELD_KEYS.has(key) ? text : `${key}：${text}`
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
