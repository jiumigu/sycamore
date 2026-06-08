import request from '@/shared/utils/request'

export function getThingList(params?: Record<string, unknown>) {
  return request({ url: '/treasure/things/', method: 'get', params })
}

export function getThingDetail(id: number) {
  return request({ url: `/treasure/things/${id}/`, method: 'get' })
}

export function createThing(data: Record<string, unknown>) {
  return request({ url: '/treasure/things/', method: 'post', data })
}

export function updateThing(id: number, data: Record<string, unknown>) {
  return request({ url: `/treasure/things/${id}/`, method: 'put', data })
}

export function deleteThing(id: number) {
  return request({ url: `/treasure/things/${id}/`, method: 'delete' })
}
