/**
 * 日期时间格式化 —— 全项目唯一实现。
 *
 * 后端 `REST_FRAMEWORK.DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'`，且 `USE_TZ=True`
 * / `Asia/Shanghai`，下发的串**本身就是本地时间**：
 *
 *   "2026-10-27 21:14:23"
 *
 * 🔴 所以直接截取，**不要 `new Date(iso)` 再格式化**：无时区标记的串会被按
 *    本地解析还好，但一旦后端改发 UTC 或换 `toISOString()`，东八区就整整差 8 小时
 *    —— 而且是「看着很合理的错时间」，界面上完全看不出来。
 *
 * 顺手兼容 iso-8601（`2026-10-27T21:14:23+08:00`）：把 `T` 换成空格即可，
 * 截前 16 位不会碰到末尾的偏移量。
 */

/**
 * `2026-10-27 21:14`（到分钟）。
 *
 * 空值返回 `''` —— 「取不到」该显示成什么由调用点决定（如表格里的 `|| '-'`），
 * 不要在这里塞一个看起来像时间的占位。
 */
export function formatDateTime(iso?: string | null): string {
  if (!iso) return ''
  return iso.slice(0, 16).replace('T', ' ')
}

/**
 * 今天（**本地时区**）的 `YYYY-MM-DD`。
 *
 * 🔴 禁用 `new Date().toISOString().slice(0, 10)`：`toISOString()` 永远输出 UTC，
 *    北京时间 00:00–07:59 取到的是**昨天**。这个错不会报错、也不会让界面看着
 *    奇怪 —— 只是「我早上记的账落到了昨天」，事后对账才发现（v3.64.48 修）。
 *
 * 只到天：日期控件的值就是天，不掺时间。
 */
export function todayLocal(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
