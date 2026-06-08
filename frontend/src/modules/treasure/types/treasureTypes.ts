export interface GoodThing {
  id: number
  user_id: number
  record_type: string
  record_type_display?: string
  name: string
  category: string
  category_display?: string
  scene: string
  why_good: string
  still_available: boolean
  where_to_find: string
  avoid_reason: string
  consequence: string
  tags: string
  rating: number
  created_at: string
  updated_at: string
}

export const RECORD_TYPE_OPTIONS = [
  { value: '好', label: '👍 好物' },
  { value: '歹', label: '👎 歹物' },
]

export const CATEGORY_OPTIONS = [
  { value: '吃', label: '🍽️ 吃' },
  { value: '穿', label: '👔 穿' },
  { value: '用', label: '🧴 用' },
  { value: '店', label: '🏪 好店' },
  { value: '地方', label: '📍 好地方' },
  { value: '方法', label: '💡 好方法' },
]

export const CATEGORY_EMOJI: Record<string, string> = {
  '吃': '🍽️',
  '穿': '👔',
  '用': '🧴',
  '店': '🏪',
  '地方': '📍',
  '方法': '💡',
}
