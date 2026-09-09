/** 决策追踪器 — API 层（长期观察型决策：追踪 + 日常记录 + 到期报告） */

import request from '@/shared/utils/request'

export type Tendency = 'continue' | 'quit' | 'uncertain'
export type Intensity = '低' | '中' | '高'

export interface DecisionTracker {
  id: number
  topic: string
  background: string
  start_date: string
  end_date: string
  status: '观察中' | '已到期' | '已决策' | '已归档'
  final_decision: string
  decision_date: string | null
  review_note: string
  created_at?: string
  updated_at?: string
  record_count?: number
  /** 距结束天数（负数=已过期），后端计算 */
  days_left?: number
}

export interface DecisionRecord {
  id: number
  tracker: number
  record_date: string
  tendency: Tendency
  reason: string
  intensity: Intensity
  created_at?: string
}

export interface DecisionReport {
  tracker: {
    id: number
    topic: string
    background: string
    start_date: string
    end_date: string
    status: string
  }
  total_records: number
  record_days: number
  tendency_stats: Array<{ tendency: Tendency; label: string; count: number; percent: number }>
  monthly_trend: Array<{ month: string; continue: number; quit: number; uncertain: number }>
  reasons: Record<Tendency, Array<{ record_date: string; intensity: Intensity; reason: string }>>
}

/** 列表（分页） */
export function getDecisionTrackers(params?: { status?: string; page?: number }) {
  return request<{ count: number; results: DecisionTracker[] }>({
    url: '/toolkit/decision-trackers/', method: 'get', params,
  })
}

export function createDecisionTracker(data: Partial<DecisionTracker>) {
  return request<DecisionTracker>({ url: '/toolkit/decision-trackers/', method: 'post', data })
}

export function updateDecisionTracker(id: number, data: Partial<DecisionTracker>) {
  return request<DecisionTracker>({ url: `/toolkit/decision-trackers/${id}/`, method: 'patch', data })
}

export function deleteDecisionTracker(id: number) {
  return request({ url: `/toolkit/decision-trackers/${id}/`, method: 'delete' })
}

/** 某追踪的全部日常记录 */
export function getTrackerRecords(trackerId: number) {
  return request<DecisionRecord[]>({ url: `/toolkit/decision-trackers/${trackerId}/records/`, method: 'get' })
}

/** 新增一条日常记录 */
export function createDecisionRecord(data: Partial<DecisionRecord>) {
  return request<DecisionRecord>({ url: '/toolkit/decision-records/', method: 'post', data })
}

/** 删除一条日常记录（记错了可删） */
export function deleteDecisionRecord(id: number) {
  return request({ url: `/toolkit/decision-records/${id}/`, method: 'delete' })
}

/** 到期汇总报告 */
export function getDecisionReport(trackerId: number) {
  return request<DecisionReport>({ url: `/toolkit/decision-trackers/${trackerId}/report/`, method: 'get' })
}

/** 做出决定 */
export function decideTracker(id: number, data: { final_decision: string; decision_date?: string }) {
  return request<DecisionTracker>({ url: `/toolkit/decision-trackers/${id}/decide/`, method: 'post', data })
}

/** 归档（可带事后回看） */
export function archiveTracker(id: number, data?: { review_note?: string }) {
  return request<DecisionTracker>({ url: `/toolkit/decision-trackers/${id}/archive/`, method: 'post', data })
}
