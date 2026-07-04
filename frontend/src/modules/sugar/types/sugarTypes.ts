export interface SugarRecord {
  s_id: number
  years: number | null
  month: number | null
  title: string
  level_of_happiness: number
  time: string
  category: string | null
  category_display?: string | null
  tags: string | null
  joy_type: string
  notes: string | null
  reward_amount: number
  reward_synced: boolean
  reward_label?: string
  created_at: string
  updated_at: string
}

export interface SugarListParams {
  year?: number
  month?: number
  category?: string
  min_happiness?: number
  search?: string
  ordering?: string
}

export interface SugarCategoryStats {
  category: string
  count: number
  total_reward: number
}

export const CATEGORY_OPTIONS = [
  { value: 'food', label: '美食', icon: '🍜' },
  { value: 'travel', label: '旅行', icon: '✈️' },
  { value: 'learn', label: '学习', icon: '📚' },
  { value: 'social', label: '社交', icon: '💬' },
  { value: 'leisure', label: '休闲', icon: '🎮' },
  { value: 'work', label: '工作', icon: '💼' },
  { value: 'health', label: '健康', icon: '🏃' },
  { value: 'other', label: '其他', icon: '💭' },
]

export const REWARD_LABELS: Record<string, { desc: string; icon: string; color: string }> = {
  '小开心': { desc: '1.0 - 3.0', icon: '😊', color: '#9CA3AF' },
  '开心': { desc: '3.1 - 5.0', icon: '🙂', color: '#60A5FA' },
  '很高兴': { desc: '5.1 - 7.0', icon: '😄', color: '#34D399' },
  '超开心': { desc: '7.1 - 8.5', icon: '🥰', color: '#FBBF24' },
  '幸福爆炸': { desc: '8.6 - 10.0', icon: '🤩', color: '#F97316' },
}

// ─── 能量清单 ───

export interface EnergyTemplate {
  id: number
  content: string
  default_energy: number
  category: string
  category_label: string
  icon: string
  estimated_seconds: number
  estimated_minutes: number
  is_system: boolean
  is_active: boolean
  sort_order: number
}

export interface EnergyLog {
  id: number
  template: number | null
  template_icon: string
  content: string
  energy_gained: number
  is_custom: boolean
  completed_at: string
  reward_processed: boolean
  created_at: string
}

export interface EnergyStats {
  today: { total_energy: number; completed_count: number }
  week: { total_energy: number; completed_count: number }
  month: { total_energy: number; completed_count: number }
  streak: { current: number; longest: number }
}

export interface EnergyTrendPoint {
  date: string
  total_energy: number
}

// ─── 小确幸模板 ───

export interface SugarTemplate {
  id: number
  user_id: number
  category: string
  category_display: string
  name: string
  icon: string
  points: number
  duration: string
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export const SUGAR_TEMPLATE_CATEGORIES: Record<string, { label: string; icon: string }> = {
  daily: { label: '日常', icon: '🌱' },
  creative: { label: '创意', icon: '✨' },
  social: { label: '社交', icon: '💬' },
  relax: { label: '放松', icon: '🧘' },
}

export const ENERGY_CATEGORY_CONFIG: Record<string, { label: string; icon: string }> = {
  daily: { label: '日常', icon: '🌱' },
  creative: { label: '创意', icon: '✨' },
  social: { label: '社交', icon: '💬' },
  relax: { label: '放松', icon: '🧘' },
}

// ─── 快乐类型 ───

export interface JoyTypeStat {
  joy_type: string
  count: number
  percentage: number
  total_happiness: number
  avg_happiness: number
}

export interface JoyTypeStats {
  joy_types: JoyTypeStat[]
  total: number
}

export const JOY_TYPE_OPTIONS = [
  { value: '感官型', label: '感官型 — 五感满足', icon: '🌿' },
  { value: '秩序型', label: '秩序型 — 掌控感', icon: '📋' },
  { value: '联结型', label: '联结型 — 关系满足', icon: '💬' },
  { value: '意外型', label: '意外型 — 惊喜感', icon: '🎁' },
  { value: '独处型', label: '独处型 — 内在空间', icon: '🧘' },
]

export const JOY_TYPE_COLORS: Record<string, string> = {
  '感官型': '#10B981',
  '秩序型': '#3B82F6',
  '联结型': '#EF4444',
  '意外型': '#F59E0B',
  '独处型': '#8B5CF6',
}
