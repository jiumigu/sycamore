export interface ConflictEvent {
  id: number
  contact: number
  contact_name: string
  title: string
  description: string
  event_type: string
  emotion_level: number
  loss_amount: number | null
  loss_time: string
  event_date: string
  is_resolved: boolean
  resolution_note: string
  tags: string
  user_id: number
  created_at: string
  updated_at: string
}

export interface ConflictStats {
  total_count: number
  total_loss: number
  avg_emotion: number
  by_type: { event_type: string; count: number }[]
  by_month: { month: number; count: number }[]
}

export const EVENT_TYPE_OPTIONS = [
  { value: '经济损失', label: '💸 经济损失' },
  { value: '时间浪费', label: '⏰ 时间浪费' },
  { value: '情绪消耗', label: '😤 情绪消耗' },
  { value: '物品损坏', label: '📦 物品损坏' },
  { value: '失信违约', label: '🤝 失信违约' },
  { value: '其他', label: '其他' },
] as const
