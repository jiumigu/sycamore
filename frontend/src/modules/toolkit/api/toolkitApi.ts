import request from '@/shared/utils/request'

export function getToolList(category?: string) {
  const params: Record<string, unknown> = {}
  if (category) params.category = category
  return request({ url: '/toolkit/tools/', method: 'get', params })
}

export function getToolDetail(toolKey: string) {
  return request({ url: `/toolkit/tools/${toolKey}/`, method: 'get' })
}

export function executeTool(toolKey: string, params: Record<string, unknown>) {
  return request({ url: '/toolkit/execute/', method: 'post', data: { tool_key: toolKey, params } })
}

export function getTaskStatus(executionId: number) {
  return request({ url: `/toolkit/task/${executionId}/`, method: 'get' })
}

export function getHistory(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/history/', method: 'get', params })
}

export function registerTools() {
  return request({ url: '/toolkit/register/', method: 'post' })
}

export function convertFile(formData: FormData) {
  return request({ url: '/toolkit/convert_file/', method: 'post', data: formData, headers: { 'Content-Type': 'multipart/form-data' } })
}

export function getAllCities() {
  return request({ url: '/toolkit/cities/', method: 'get' })
}

export function searchCity(q: string) {
  return request({ url: '/toolkit/cities/search/', method: 'get', params: { q } })
}

export function getProvinces() {
  return request({ url: '/toolkit/cities/provinces/', method: 'get' })
}

export function getCities(province: string) {
  return request({ url: '/toolkit/cities/cities/', method: 'get', params: { province } })
}

export function getDistricts(city: string) {
  return request({ url: '/toolkit/cities/districts/', method: 'get', params: { city } })
}

export function getTravelRoutes() {
  return request({ url: '/toolkit/travel-routes/', method: 'get' })
}

export function createTravelRoute(data: Record<string, unknown>) {
  return request({ url: '/toolkit/travel-routes/', method: 'post', data })
}

export function updateTravelRoute(id: number, data: Record<string, unknown>) {
  return request({ url: `/toolkit/travel-routes/${id}/`, method: 'put', data })
}

export function deleteTravelRoute(id: number) {
  return request({ url: `/toolkit/travel-routes/${id}/`, method: 'delete' })
}

// ────────── 环境校准 ──────────

export function getEnvironmentAudits(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/environment-audits/', method: 'get', params })
}

export function createEnvironmentAudit(data: Record<string, unknown>) {
  return request({ url: '/toolkit/environment-audits/', method: 'post', data })
}

export function deleteEnvironmentAudit(id: number) {
  return request({ url: `/toolkit/environment-audits/${id}/`, method: 'delete' })
}

// ────────── 职业能量审计 ──────────

export function getCareerEnergyAudits(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/career-energy-audits/', method: 'get', params })
}

export function createCareerEnergyAudit(data: Record<string, unknown>) {
  return request({ url: '/toolkit/career-energy-audits/', method: 'post', data })
}

export function deleteCareerEnergyAudit(id: number) {
  return request({ url: `/toolkit/career-energy-audits/${id}/`, method: 'delete' })
}
