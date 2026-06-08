import request from '@/shared/utils/request'

// ─── 每日记录 (OneDay) ───

export function getOneDayList(params?: Record<string, unknown>) {
  return request({ url: '/temporal/oneday/', method: 'get', params })
}

export function getOneDayDetail(id: number) {
  return request({ url: `/temporal/oneday/${id}/`, method: 'get' })
}

export function createOneDay(data: Record<string, unknown>) {
  return request({ url: '/temporal/oneday/', method: 'post', data })
}

export function updateOneDay(id: number, data: Record<string, unknown>) {
  return request({ url: `/temporal/oneday/${id}/`, method: 'put', data })
}

export function deleteOneDay(id: number) {
  return request({ url: `/temporal/oneday/${id}/`, method: 'delete' })
}

export function getOneDayStats() {
  return request({ url: '/temporal/oneday/stats/', method: 'get' })
}

export function getWeekCount() {
  return request<{ count: number }>({ url: '/temporal/oneday/week_count/', method: 'get' })
}

export function bulkDeleteOneDay(ids: number[]) {
  return request({ url: '/temporal/oneday/bulk_delete/', method: 'delete', data: { oids: ids } })
}

export function getYearlyHeatmap(year: number) {
  return request({ url: `/temporal/oneday/yearly_heatmap/?year=${year}`, method: 'get' })
}

// ─── 任务时间追踪 (Tasks) ───

export function getTaskList(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/', method: 'get', params })
}

export function getTaskDetail(id: number) {
  return request({ url: `/temporal/tasks/${id}/`, method: 'get' })
}

export function getTaskNames() {
  return request({ url: '/temporal/tasks/task_names/', method: 'get' })
}

export function importTaskCsv(data: FormData) {
  return request({ url: '/temporal/tasks/import_csv/', method: 'post', data, headers: { 'Content-Type': undefined } })
}

export function getTaskStats(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/stats/', method: 'get', params })
}

export function getTaskTrend(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/trend/', method: 'get', params })
}

export function getTaskBalance(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/balance/', method: 'get', params })
}

export function getTaskRanking(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/ranking/', method: 'get', params })
}

export function getTaskDistribution(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/distribution/', method: 'get', params })
}

export function getTaskCalendar(params?: Record<string, unknown>) {
  return request({ url: '/temporal/tasks/calendar/', method: 'get', params })
}

// ─── 周度时间追踪 ───

export function getWeeklyTracking(params?: Record<string, unknown>) {
  return request({ url: '/temporal/weekly-tracking/', method: 'get', params })
}

export function refreshWeeklyCache() {
  return request({ url: '/temporal/weekly-tracking/refresh/', method: 'post' })
}
