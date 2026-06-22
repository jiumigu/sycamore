/** 个人画像 — API 层 */

import request from '@/shared/utils/request'

export interface HealthProfile {
  latest_score: number | null
  score_trend: { date: string; value: number }[]
  latest_weight: number | null
  weight_trend: { date: string; value: number }[]
  check_count: number
}

export interface EnergyProfile {
  latest: {
    total_score: number | null
    work_score: number | null
    env_score: number | null
    growth_score: number | null
    body_score: number | null
    decision: string | null
  } | null
  trend: { date: string; total: number; work: number; env: number; growth: number; body: number }[]
  audit_count: number
}

export interface MoodProfile {
  total_records: number
  avg_happiness: number | null
  happiness_trend: { date: string; value: number }[]
  active_days: number
}

export interface RelationProfile {
  total_relations: number
  active_relations: number
  interactions_this_year: number
}

export interface OutputProfile {
  total_records: number
  good_rate: number | null
  by_category: { category: string; total: number; good: number; rate: number }[]
}

export interface InboxProfile {
  pending: number
  hesitating: number
  done_this_year: number
  total: number
  by_category: { category: string; count: number }[]
}

export interface DecisionProfile {
  total_decisions: number
  right_count: number
  wrong_count: number
  right_rate: number | null
  reviewed_count: number
  by_category: { category: string; count: number }[]
  top_bias: string
  bias_distribution: { bias: string; count: number }[]
}

export interface PersonalProfile {
  health: HealthProfile
  energy: EnergyProfile
  mood: MoodProfile
  relation: RelationProfile
  output: OutputProfile
  inbox: InboxProfile
  decision: DecisionProfile
}

export function getPersonalProfile(params?: { year?: number }) {
  return request<PersonalProfile>({ url: '/summary/profile/', method: 'get', params })
}
