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

export function getRadarConfig() {
  return request({ url: '/summary/radar_config/', method: 'get' })
}

export function saveRadarConfig(data: Record<string, number | string>) {
  return request({ url: '/summary/radar_config/', method: 'patch', data })
}

export function getRadarConfigHistory() {
  return request({ url: '/summary/radar_config_history/', method: 'get' })
}

export function getYearlyDetail() {
  return request({ url: '/summary/yearly_detail/', method: 'get' })
}

export function getYears() {
  return request({ url: '/summary/years/', method: 'get' })
}

/**
 * 阶段对照：各人生阶段的七维覆盖率（**跨年**，不带 year 参数）
 *
 * 🔴 不带 year：阶段可以跨自然年（「三年赎回期」2026-11 → 2029-09），
 *    按年切会把它劈成三段，而「赎回期 vs 谋生期」本来就不是同一年内的事。
 */
export function getStageCompare() {
  return request({ url: '/summary/stage_compare/', method: 'get' })
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

// ── 身体-状态关联 ──────────────────────────────────────

export function getBodyMindData(params?: { weeks?: number }) {
  return request({ url: '/summary/body_mind/', method: 'get', params })
}

/**
 * 跨维度配对体检：每组给共同月数、系数、去掉极端月后是否还成立
 *
 * 只回答「有没有关系」，不回答「谁导致谁」—— 文案里不能出现因果断言。
 */
export function getPairCheck() {
  return request({ url: '/summary/pair_check/', method: 'get' })
}

/**
 * 年度回顾（叙事版）：把这一年讲成一篇有前后顺序的事实流
 *
 * 与 `/yearly_detail/` 的分工：那边是一张表，这边是叙事 ——
 * 只讲「什么时候发生了什么」，每段都引用一条真实记录。
 */
export function getYearRetro(year: number) {
  return request({ url: '/summary/year_retro/', method: 'get', params: { year } })
}

export function saveQuarterlyAnswers(params: { year: number; quarter: number }, data: Record<string, unknown> | Record<string, unknown>[]) {
  return request({ url: '/summary/quarterly_answers/', method: 'post', params, data })
}
