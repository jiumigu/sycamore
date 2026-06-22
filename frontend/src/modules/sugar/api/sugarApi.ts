import request from '@/shared/utils/request'

export function getSugarList(params?: Record<string, unknown>) {
  return request({ url: '/sugar/records/', method: 'get', params })
}

export function getSugarDetail(id: number) {
  return request({ url: `/sugar/records/${id}/`, method: 'get' })
}

export function createSugar(data: Record<string, unknown>) {
  return request({ url: '/sugar/records/', method: 'post', data })
}

export function updateSugar(id: number, data: Record<string, unknown>) {
  return request({ url: `/sugar/records/${id}/`, method: 'put', data })
}

export function deleteSugar(id: number) {
  return request({ url: `/sugar/records/${id}/`, method: 'delete' })
}

export function getSugarCategories(params?: Record<string, unknown>) {
  return request({ url: '/sugar/categories/', method: 'get', params })
}

export function getJoyTypeStats(params?: Record<string, unknown>) {
  return request({ url: '/sugar/records/joy_type_stats/', method: 'get', params })
}

// ─── 小确幸模板 API ───

export function getSugarTemplates() {
  return request({ url: '/sugar/templates/', method: 'get' })
}

export function createSugarTemplate(data: Record<string, unknown>) {
  return request({ url: '/sugar/templates/', method: 'post', data })
}

export function updateSugarTemplate(id: number, data: Record<string, unknown>) {
  return request({ url: `/sugar/templates/${id}/`, method: 'put', data })
}

export function deleteSugarTemplate(id: number) {
  return request({ url: `/sugar/templates/${id}/`, method: 'delete' })
}

// ─── 能量清单 API ───

export function getEnergyTemplates() {
  return request({ url: '/sugar/energy/templates/', method: 'get' })
}

export function createEnergyTemplate(data: Record<string, unknown>) {
  return request({ url: '/sugar/energy/templates/', method: 'post', data })
}

export function completeEnergyTask(data: Record<string, unknown>) {
  return request({ url: '/sugar/energy/complete/', method: 'post', data })
}

export function getEnergyStats() {
  return request({ url: '/sugar/energy/stats/', method: 'get' })
}

export function getEnergyDaily(date?: string) {
  return request({ url: '/sugar/energy/daily/', method: 'get', params: date ? { date } : {} })
}

export function getEnergyTrend(days = 30) {
  return request({ url: '/sugar/energy/trend/', method: 'get', params: { days } })
}
