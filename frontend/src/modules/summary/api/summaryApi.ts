/** 综合进度看板 — API 层 */

import request from '@/shared/utils/request'

export function getYearlyOverview(params?: { year?: number }) {
  return request({ url: '/summary/overview/', method: 'get', params })
}

export function getMonthlyDetail(params?: { year?: number; month?: number }) {
  return request({ url: '/summary/monthly_detail/', method: 'get', params })
}

export function getTrend(params?: { year?: number }) {
  return request({ url: '/summary/trend/', method: 'get', params })
}

export function getRadar(params?: { year?: number }) {
  return request({ url: '/summary/radar/', method: 'get', params })
}

export function getYears() {
  return request({ url: '/summary/years/', method: 'get' })
}

export function getModuleDetail(params: { module: string; year?: number; month?: number }) {
  return request({ url: '/summary/module_detail/', method: 'get', params })
}

export function getRandomRetro() {
  return request<{ type: string; content: string; date: string }>({
    url: '/summary/random_retro/', method: 'get',
  })
}

// ── 季度决策工作台 ──────────────────────────────────────

export function getQuarterlyReport(params: { year: number; quarter: number }) {
  return request({ url: '/summary/quarterly_report/', method: 'get', params })
}

export function getQuarterlyInsights(params: { year: number; quarter: number }) {
  return request({ url: '/summary/quarterly_insights/', method: 'get', params })
}

export function getQuarterlyQuestions(params: { year: number; quarter: number }) {
  return request({ url: '/summary/quarterly_questions/', method: 'get', params })
}

export function getQuarterlyAnswers(params: { year: number; quarter: number }) {
  return request({ url: '/summary/quarterly_answers/', method: 'get', params })
}

export function saveQuarterlyAnswers(params: { year: number; quarter: number }, data: Record<string, unknown> | Record<string, unknown>[]) {
  return request({ url: '/summary/quarterly_answers/', method: 'post', params, data })
}
