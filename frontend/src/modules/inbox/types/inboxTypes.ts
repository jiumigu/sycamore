export interface InboxItem {
  id: number
  content: string
  description: string | null
  category: string
  category_display: string
  tags: string | null
  status: string
  status_display: string
  source: string
  source_display: string
  target_type: string | null
  target_id: number | null
  completion_note?: string
  hesitate_reason?: string
  due_date: string | null
  remind_at: string | null
  processed_at: string | null
  priority: string
  priority_display: string
  user_id: number
  created_at: string
  updated_at: string
  process_logs?: InboxProcessLog[]
}

export interface InboxProcessLog {
  id: number
  inbox: number
  action: string
  action_display: string
  target_type: string | null
  target_id: number | null
  notes: string | null
  user_id: number
  created_at: string
}

export interface InboxStats {
  total: number
  pending: number
  hesitating: number
  completed: number
  processed: number
  by_category: Record<string, number>
  by_priority: Record<string, number>
}

export interface BatchActionPayload {
  ids: number[]
  action: 'complete' | 'archive' | 'delete' | 'convert_to_goal' | 'convert_to_milestone' | 'convert_to_sugar'
  target_type?: string
  target_id?: number
}

export const CATEGORY_OPTIONS = [
  { value: 'todo', label: '待办', icon: '✅' },
  { value: 'idea', label: '想法', icon: '💡' },
  { value: 'pain', label: '痛点', icon: '😫' },
  { value: 'reminder', label: '提醒', icon: '⏰' },
  { value: 'work', label: '工作', icon: '💼' },
  { value: 'other', label: '其他', icon: '📌' },
] as const

export const PRIORITY_OPTIONS = [
  { value: 'high', label: '高', color: '#EF4444' },
  { value: 'medium', label: '中', color: '#F59E0B' },
  { value: 'low', label: '低', color: '#6B7280' },
] as const

export const STATUS_OPTIONS = [
  { value: 'pending', label: '待处理', color: '#3B82F6' },
  { value: 'hesitating', label: '犹豫中', color: '#F59E0B' },
  { value: 'processed', label: '已处理', color: '#8B5CF6' },
  { value: 'done', label: '已完成', color: '#10B981' },
  { value: 'archived', label: '已归档', color: '#9CA3AF' },
] as const
