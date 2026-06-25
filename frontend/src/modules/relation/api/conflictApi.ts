import request from '@/shared/utils/request'

export function getConflictList(params?: Record<string, unknown>) {
  return request({ url: '/relation/conflicts/', method: 'get', params })
}

export function createConflict(data: Record<string, unknown>) {
  return request({ url: '/relation/conflicts/', method: 'post', data })
}

export function updateConflict(id: number, data: Record<string, unknown>) {
  return request({ url: `/relation/conflicts/${id}/`, method: 'patch', data })
}

export function deleteConflict(id: number) {
  return request({ url: `/relation/conflicts/${id}/`, method: 'delete' })
}

export function getConflictStats(params?: Record<string, unknown>) {
  return request({ url: '/relation/conflicts/stats/', method: 'get', params })
}
