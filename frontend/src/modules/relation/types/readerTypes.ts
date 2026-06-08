export interface ReaderGroup {
  id: number
  name: string
  description: string
  total_energy: number
  interaction_count: number
  created_at: string
  updated_at: string
}

export interface ReaderInteraction {
  id: number
  reader_group: number
  reader_name: string
  interaction_type: 'comment' | 'like' | 'share' | 'follow' | 'unfollow' | 'reward'
  interaction_type_display: string
  content: string
  article_title: string
  energy_score: number
  tags: string
  interaction_date?: string
  created_at: string
}

export const INTERACTION_TYPE_OPTIONS = [
  { value: 'comment', label: '💬 留言' },
  { value: 'like', label: '❤️ 点赞' },
  { value: 'share', label: '🔄 转发' },
  { value: 'follow', label: '➕ 关注' },
  { value: 'unfollow', label: '➖ 取关' },
  { value: 'reward', label: '💰 打赏' },
]

export const ENERGY_COLORS: Record<string, string> = {
  high: '#10B981',
  medium: '#F59E0B',
  low: '#6B7280',
}

export function energyColor(score: number): string {
  if (score >= 3) return ENERGY_COLORS.high
  if (score >= 1) return ENERGY_COLORS.medium
  return ENERGY_COLORS.low
}

export interface ReaderMonthlySummary {
  id: number
  reader_group: number
  group_name: string
  year: number
  month: number
  new_followers: number
  new_unfollowers: number
  total_followers: number
  total_interactions: number
  high_energy_count: number
  top_article: string
  notes: string
  created_at: string
}

export interface ReaderYearlyStats {
  year: string | null
  total_new_followers: number
  total_new_unfollowers: number
  net_growth: number
  avg_monthly_interactions: number
  total_interactions: number
  best_month: { month: number; total_interactions: number; top_article: string } | null
  total_summaries: number
}
