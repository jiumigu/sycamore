import request from '@/shared/utils/request'
import type { TravelRecord, TravelFormData } from '../types/travelTypes'

export function getTravelRecords(params?: Record<string, unknown>) {
  return request({ url: '/travel/records/', method: 'get', params })
}

export function getTravelRecordDetail(id: number) {
  return request({ url: `/travel/records/${id}/`, method: 'get' })
}

export function createTravelRecord(data: TravelFormData) {
  return request({ url: '/travel/records/', method: 'post', data })
}

export function updateTravelRecord(id: number, data: TravelFormData) {
  return request({ url: `/travel/records/${id}/`, method: 'put', data })
}

export function deleteTravelRecord(id: number) {
  return request({ url: `/travel/records/${id}/`, method: 'delete' })
}

export function getMapData(params?: Record<string, unknown>) {
  return request({ url: '/travel/map/data/', method: 'get', params })
}

export function getTravelStats(params?: Record<string, unknown>) {
  return request({ url: '/travel/stats/', method: 'get', params })
}

export function getProvinceList() {
  return request({ url: '/travel/provinces/', method: 'get' })
}

export function getYearList() {
  return request({ url: '/travel/years/', method: 'get' })
}
