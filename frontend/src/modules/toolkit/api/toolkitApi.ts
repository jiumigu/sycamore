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

// ────────── 身体健康自查 ──────────

export function getHealthSelfChecks(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/health-self-checks/', method: 'get', params })
}

export function createHealthSelfCheck(data: Record<string, unknown>) {
  return request({ url: '/toolkit/health-self-checks/', method: 'post', data })
}

export function deleteHealthSelfCheck(id: number) {
  return request({ url: `/toolkit/health-self-checks/${id}/`, method: 'delete' })
}

// ────────── 复盘记录 ──────────

export function getReviewRecords(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/review-records/', method: 'get', params })
}

export function createReviewRecord(data: Record<string, unknown>) {
  return request({ url: '/toolkit/review-records/', method: 'post', data })
}

export function updateReviewRecord(id: number, data: Record<string, unknown>) {
  return request({ url: `/toolkit/review-records/${id}/`, method: 'patch', data })
}

export function deleteReviewRecord(id: number) {
  return request({ url: `/toolkit/review-records/${id}/`, method: 'delete' })
}

// ────────── 时薪计算 ──────────

export function getHourlyWageList(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/hourly-wage/', method: 'get', params })
}

export function createHourlyWage(data: Record<string, unknown>) {
  return request({ url: '/toolkit/hourly-wage/', method: 'post', data })
}

export function deleteHourlyWage(id: number) {
  return request({ url: `/toolkit/hourly-wage/${id}/`, method: 'delete' })
}

// ────────── 自由支配额度计算 ──────────

export function getFreeSpendingList(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/free-spending/', method: 'get', params })
}

export function createFreeSpending(data: Record<string, unknown>) {
  return request({ url: '/toolkit/free-spending/', method: 'post', data })
}

export function deleteFreeSpending(id: number) {
  return request({ url: `/toolkit/free-spending/${id}/`, method: 'delete' })
}

// ────────── 标签管理器 ──────────

export function getTags() {
  return request({ url: '/toolkit/tags/', method: 'get' })
}

export function mergeTag(data: { action: string; old_tag: string; new_tag: string }) {
  return request({ url: '/toolkit/tags/', method: 'post', data })
}

// ────────── 语言训练 ──────────

export function getLanguageTrainingList(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/language-training/', method: 'get', params })
}

export function createLanguageTraining(data: Record<string, unknown>) {
  return request({ url: '/toolkit/language-training/', method: 'post', data })
}

export function updateLanguageTraining(id: number, data: Record<string, unknown>) {
  return request({ url: `/toolkit/language-training/${id}/`, method: 'patch', data })
}

export function deleteLanguageTraining(id: number) {
  return request({ url: `/toolkit/language-training/${id}/`, method: 'delete' })
}
