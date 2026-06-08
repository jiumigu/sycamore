import request from '@/shared/utils/request'

export function getRelationshipList(params?: Record<string, unknown>) {
  return request({ url: '/relation/relationships/', method: 'get', params })
}

export function getRelationshipDetail(id: number) {
  return request({ url: `/relation/relationships/${id}/`, method: 'get' })
}

export function createRelationship(data: Record<string, unknown>) {
  return request({ url: '/relation/relationships/', method: 'post', data })
}

export function updateRelationship(id: number, data: Record<string, unknown>) {
  return request({ url: `/relation/relationships/${id}/`, method: 'put', data })
}

export function deleteRelationship(id: number) {
  return request({ url: `/relation/relationships/${id}/`, method: 'delete' })
}

// Interactions
export function getInteractionList(params?: Record<string, unknown>) {
  return request({ url: '/relation/interactions/', method: 'get', params })
}

export function createInteraction(data: Record<string, unknown>) {
  return request({ url: '/relation/interactions/', method: 'post', data })
}

export function updateInteraction(id: number, data: Record<string, unknown>) {
  return request({ url: `/relation/interactions/${id}/`, method: 'put', data })
}

export function deleteInteraction(id: number) {
  return request({ url: `/relation/interactions/${id}/`, method: 'delete' })
}

// Stats
export function getStatsOverview() {
  return request({ url: '/relation/stats/overview/', method: 'get' })
}

export function getQualityDistribution() {
  return request({ url: '/relation/stats/quality_distribution/', method: 'get' })
}

export function getEnergyTrend(days = 90) {
  return request({ url: '/relation/stats/energy_trend/', method: 'get', params: { days } })
}

export function getInteractionFrequency(months = 6) {
  return request({ url: '/relation/stats/interaction_frequency/', method: 'get', params: { months } })
}

export function getDueReminders() {
  return request({ url: '/relation/stats/due_reminders/', method: 'get' })
}

export function getLocationStats() {
  return request({ url: '/relation/stats/location_stats/', method: 'get' })
}

export function getMetPlaces() {
  return request({ url: '/relation/relationships/met_places/', method: 'get' })
}
