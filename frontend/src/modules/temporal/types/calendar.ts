export interface CalendarEvent {
  id: string
  title: string
  date: string          // 开始日期 YYYY-MM-DD
  endDate?: string      // 可选：跨天结束日期（预留跨天日程）
  status: 'todo' | 'done'
  source: 'inbox' | 'milestone'
  sourceLabel: string
  // 详情字段（点击条目时展示）
  description?: string
  completedNote?: string
  /** 里程碑专有：完成时写的那句批阅（`self_review`）
   *
   * 🔴 与 `completedNote` 是**两列**，别合并：完成备注是事实（做了多少、什么结果），
   *    批阅是判断（难在哪、下次怎么改）。日程里那个「记录完成心得」框写的是后者。 */
  selfReview?: string
  category?: string
  tags?: string
  goalTitle?: string
  goalDeadline?: string
  remindAt?: string
  rawId: number          // 后端对象真实 id（用于完成操作）
}
