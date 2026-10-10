/**
 * 物件资产 · 错误文案提取（v3.60.0）
 *
 * 后端把「为什么不行」写在两处，这里把它们都取出来：
 *    `{ detail: '「家电」下还有 2 件物件，不能直接删除…' }`  ← 服务层抛的 ValueError
 *    `{ scrapped_date: ['报废日期不能早于购买日期'] }`       ← 序列化器字段校验
 *
 * 🔴 **必须把 `detail` 原样弹给用户**，不要换成「操作失败」：
 *    本模块的 400 里有三条是「可照做的提示」（还有几件物件、
 *    报废日不能早于购买日、已存在同名类别），换成一句笼统的失败
 *    等于把「下一步该干什么」也一起丢掉了。
 */

export function extractApiMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: unknown } })?.response?.data
  if (typeof data === 'string' && data) return data
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>
    if (typeof record.detail === 'string' && record.detail) return record.detail
    // 字段级校验：取第一个字段的第一句话 —— 表单一次只让人改一处
    for (const value of Object.values(record)) {
      if (Array.isArray(value) && value.length) return String(value[0])
      if (typeof value === 'string' && value) return value
    }
  }
  return fallback
}
