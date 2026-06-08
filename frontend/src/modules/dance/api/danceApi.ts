import request from '@/shared/utils/request'

export function getDanceList(params?: Record<string, unknown>) {
  return request({ url: '/hobby/dance/records/', method: 'get', params })
}

export function getDanceDetail(id: number) {
  return request({ url: `/hobby/dance/records/${id}/`, method: 'get' })
}

export function createDance(data: Record<string, unknown>) {
  return request({ url: '/hobby/dance/records/', method: 'post', data })
}

export function updateDance(id: number, data: Record<string, unknown>) {
  return request({ url: `/hobby/dance/records/${id}/`, method: 'put', data })
}

export function deleteDance(id: number) {
  return request({ url: `/hobby/dance/records/${id}/`, method: 'delete' })
}

export function getDanceStats() {
  return request({ url: '/hobby/dance/records/stats/', method: 'get' })
}

export function getDanceTrend(params?: Record<string, unknown>) {
  return request({ url: '/hobby/dance/records/trend/', method: 'get', params })
}

export function getDanceTeachers() {
  return request({ url: '/hobby/dance/records/teachers/', method: 'get' })
}

export function getDanceTypes() {
  return request({ url: '/hobby/dance/records/types/', method: 'get' })
}

export function getDanceScoreTrend() {
  return request({ url: '/hobby/dance/records/score_trend/', method: 'get' })
}

export function getDanceCalendar(params?: Record<string, unknown>) {
  return request({ url: '/hobby/dance/records/calendar/', method: 'get', params })
}
