import request from '@/shared/utils/request'

export function getHealthList(params?: Record<string, unknown>) {
  return request({ url: '/health/records/', method: 'get', params })
}

export function getHealthDetail(hid: number) {
  return request({ url: `/health/records/${hid}/`, method: 'get' })
}

export function createHealth(data: Record<string, unknown>) {
  return request({ url: '/health/records/', method: 'post', data })
}

export function updateHealth(hid: number, data: Record<string, unknown>) {
  return request({ url: `/health/records/${hid}/`, method: 'put', data })
}

export function deleteHealth(hid: number) {
  return request({ url: `/health/records/${hid}/`, method: 'delete' })
}

export function getHealthSummary() {
  return request({ url: '/health/records/summary/', method: 'get' })
}

export function getHealthMilestones() {
  return request({ url: '/health/records/milestones/', method: 'get' })
}

export function getHealthDailyTrend(days = 30) {
  return request({ url: '/health/records/daily_trend/', method: 'get', params: { days } })
}

export function getHealthCalendar(params?: Record<string, unknown>) {
  return request({ url: '/health/records/calendar/', method: 'get', params })
}

export function getHealthMilestoneTimeline() {
  return request({ url: '/health/records/milestone_timeline/', method: 'get' })
}

export function getHealthTypeStats() {
  return request({ url: '/health/records/type_stats/', method: 'get' })
}

export function getHealthYearlyComparison() {
  return request({ url: '/health/records/yearly_comparison/', method: 'get' })
}

// ─── 体重管理 ───

export function getWeightRecords(params?: Record<string, unknown>) {
  return request({ url: '/health/weight/records/', method: 'get', params })
}

export function createWeightRecord(data: Record<string, unknown>) {
  return request({ url: '/health/weight/records/', method: 'post', data })
}

export function updateWeightRecord(id: number, data: Record<string, unknown>) {
  return request({ url: `/health/weight/records/${id}/`, method: 'put', data })
}

export function deleteWeightRecord(id: number) {
  return request({ url: `/health/weight/records/${id}/`, method: 'delete' })
}

export function getWeightStats(params?: Record<string, unknown>) {
  return request({ url: '/health/weight/stats/', method: 'get', params })
}

export function getWeightTrend(params?: Record<string, unknown>) {
  return request({ url: '/health/weight/trend/', method: 'get', params })
}

export function getWeightGoal(params?: Record<string, unknown>) {
  return request({ url: '/health/weight/goal/', method: 'get', params })
}

export function createWeightGoal(data: Record<string, unknown>) {
  return request({ url: '/health/weight/goal/', method: 'post', data })
}

export function getWeightMilestones(params?: Record<string, unknown>) {
  return request({ url: '/health/weight/milestones/', method: 'get', params })
}

export function getWeightBodyInfo(params?: Record<string, unknown>) {
  return request({ url: '/health/weight/body-info/', method: 'get', params })
}

export function updateWeightBodyInfo(data: Record<string, unknown>) {
  return request({ url: '/health/weight/body-info/', method: 'put', data })
}

// ─── 好朋友跟踪 ───

export function getMenstrualRecords(params?: Record<string, unknown>) {
  return request({ url: '/health/menstrual/', method: 'get', params })
}

export function createMenstrualRecord(data: Record<string, unknown>) {
  return request({ url: '/health/menstrual/', method: 'post', data })
}

export function updateMenstrualRecord(id: number, data: Record<string, unknown>) {
  return request({ url: `/health/menstrual/${id}/`, method: 'put', data })
}

export function deleteMenstrualRecord(id: number) {
  return request({ url: `/health/menstrual/${id}/`, method: 'delete' })
}

export function getMenstrualStats() {
  return request({ url: '/health/menstrual/stats/', method: 'get' })
}

export function getMenstrualTrend() {
  return request({ url: '/health/menstrual/trend/', method: 'get' })
}
