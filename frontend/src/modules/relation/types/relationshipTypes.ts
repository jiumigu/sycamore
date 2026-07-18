export interface Relationship {
  id: number
  name: string
  alias: string
  met_date: string | null
  met_place: string
  met_scene: string
  identity_then: string
  they_give_me: string
  i_give_them: string
  current_status: string
  current_quality: string
  notes: string
  tags: string
  user_id: number
  created_at: string
  updated_at: string
  quality_label: string
  quality_color: string
  quality_icon: string
  status_label: string
  interaction_count: number
  total_energy: number
  avg_energy: number | null
  relation_type: string
  last_interaction: string | null
}

export interface Interaction {
  id: number
  relationship: number
  happened_at: string
  method: string
  method_label: string
  energy_score: number
  energy_label: string
  summary: string
  quality_shift: string
  quality_shift_label: string
  next_reminder: string
  my_action?: string
  user_id: number
  created_at: string
}

export interface StatsOverview {
  total_relationships: number
  nourishing_count: number
  neutral_count: number
  draining_count: number
  harmful_count: number
  monthly_interactions: number
  last_month_interactions: number
  monthly_change: number
  total_energy: number
}

export interface QualityDistribution {
  quality: string
  count: number
  label: string
}

export interface EnergyTrendItem {
  period: string
  total_energy: number
  count: number
}

export interface InteractionFrequency {
  period: string
  count: number
  unique_people: number
}

export interface DueReminder {
  id: number
  name: string
  quality: string
  tags: string
  last_interaction: string | null
  days_since: number | null
}

export const QUALITY_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  nourishing: { label: '滋养型', color: '#10B981', icon: '🌱' },
  neutral: { label: '中性', color: '#9CA3AF', icon: '⚪' },
  draining: { label: '消耗型', color: '#F59E0B', icon: '⚡' },
  toxic: { label: '有害型', color: '#EF4444', icon: '⚠️' },
}

export const STATUS_OPTIONS = [
  { value: 'active', label: '保持联系' },
  { value: 'distant', label: '已疏远' },
  { value: 'paused', label: '暂停联系' },
  { value: 'ended', label: '已结束' },
]

export const METHOD_OPTIONS = [
  { value: 'meet', label: '☕ 见面' },
  { value: 'call', label: '📞 电话' },
  { value: 'wechat', label: '💬 微信' },
  { value: 'other', label: '📧 其他' },
]

export const SHIFT_OPTIONS = [
  { value: 'improved', label: '感觉变好了' },
  { value: 'declined', label: '感觉变差了' },
  { value: 'same', label: '差不多' },
]

export const RELATION_TYPE_LABELS: Record<string, string> = {
  nourishing: '滋养型', neutral: '中性', draining: '消耗型', toxic: '有害型',
}

export const RELATION_TYPE_TAG: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  nourishing: 'success', neutral: 'info', draining: 'warning', toxic: 'danger',
}

export function energyLabel(score: number): string {
  if (score >= 8) return '太棒了！'
  if (score >= 5) return '很开心'
  if (score >= 1) return '还不错'
  if (score === 0) return '一般般'
  if (score >= -4) return '有点累'
  if (score >= -7) return '很消耗'
  return '极度痛苦'
}

export function energyColor(score: number): string {
  if (score > 0) return '#10B981'
  if (score === 0) return '#9CA3AF'
  return '#EF4444'
}

// ─── 认识地点分析 ───

export interface LocationStatsItem {
  name: string
  total: number
  nourishing: number
  neutral: number
  draining: number
  toxic: number
  nourishing_rate: number
}

export interface LocationStatsSummary {
  total_locations: number
  total_people: number
  best_location: string | null
  best_nourishing_rate: number
}

export interface LocationStatsData {
  locations: LocationStatsItem[]
  summary: LocationStatsSummary
}

// ─── 读者互动 ───

export interface ReaderInteraction {
  id: number
  reader_group: number
  reader_name: string
  interaction_type: string
  interaction_type_display: string
  content: string
  article_title: string
  energy_score: number
  tags: string
  interaction_date: string
  created_at: string
}

export const INTERACTION_TYPE_OPTIONS = [
  { value: 'comment', label: '💬 留言' },
  { value: 'like', label: '❤️ 点赞' },
  { value: 'share', label: '🔄 转发' },
  { value: 'follow', label: '➕ 关注' },
  { value: 'reward', label: '💰 打赏' },
]

export const ENERGY_OPTIONS = [
  { value: 1, label: '+1 有点意思' },
  { value: 3, label: '+3 很有共鸣' },
  { value: 5, label: '+5 醍醐灌顶' },
]
