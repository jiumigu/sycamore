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
  category?: string
  tags?: string
  goalTitle?: string
  goalDeadline?: string
  remindAt?: string
  rawId: number          // 后端对象真实 id（用于完成操作）
}
