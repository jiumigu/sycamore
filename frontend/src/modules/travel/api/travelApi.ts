import request from '@/shared/utils/request'
import type { TravelFormData, TravelPlanInput } from '../types/travelTypes'

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

export function getTravelPlans(params?: Record<string, unknown>) {
  return request({ url: '/travel/plans/', method: 'get', params })
}

export function getTravelPlanDetail(id: number) {
  return request({ url: `/travel/plans/${id}/`, method: 'get' })
}

export function createTravelPlan(data: TravelPlanInput) {
  return request({ url: '/travel/plans/', method: 'post', data })
}

export function updateTravelPlan(id: number, data: TravelPlanInput) {
  return request({ url: `/travel/plans/${id}/`, method: 'put', data })
}

export function deleteTravelPlan(id: number) {
  return request({ url: `/travel/plans/${id}/`, method: 'delete' })
}

export function getTravelPlanItems(id: number) {
  return request({ url: `/travel/plans/${id}/items/`, method: 'get' })
}

export function getTravelPlanStats() {
  return request({ url: '/travel/plans/stats/', method: 'get' })
}

export function toggleTravelPlanItem(id: number, itemId: number) {
  return request({ url: `/travel/plans/${id}/toggle-item/`, method: 'post', data: { item_id: itemId } })
}
