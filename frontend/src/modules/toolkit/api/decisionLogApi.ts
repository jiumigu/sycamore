/** 决策日志 — API 层 */

import request from '@/shared/utils/request'

export interface DecisionLog {
  id?: number
  title: string
  decision_date: string
  category: string
  background: string
  options: { name: string; pros: string; cons: string }[]
  chosen: string
  reason: string
  expected_outcome: string
  fear_factor: number
  actual_outcome: string
  was_right: boolean | null
  learned: string
  bias_found: string
  review_date: string | null
  created_at?: string
}

export function getDecisionLogs(params?: { year?: number; category?: string }) {
  return request<{ count: number; results: DecisionLog[] }>({
    url: '/toolkit/decision-logs/', method: 'get', params,
  })
}

export function getDecisionLog(id: number) {
  return request<DecisionLog>({ url: `/toolkit/decision-logs/${id}/`, method: 'get' })
}

export function createDecisionLog(data: DecisionLog) {
  return request<DecisionLog>({ url: '/toolkit/decision-logs/', method: 'post', data })
}

export function updateDecisionLog(id: number, data: Partial<DecisionLog>) {
  return request<DecisionLog>({ url: `/toolkit/decision-logs/${id}/`, method: 'patch', data })
}

export function deleteDecisionLog(id: number) {
  return request({ url: `/toolkit/decision-logs/${id}/`, method: 'delete' })
}
