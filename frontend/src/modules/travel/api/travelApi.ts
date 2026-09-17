import request from '@/shared/utils/request'
import type { ConsolidatePayload, PlanFromRouteInput, TravelFormData, TravelPlanInput, TravelWish } from '../types/travelTypes'

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

// ===== 旅行心愿单 =====
export function getWishes(params?: Record<string, unknown>) {
  return request({ url: '/travel/wishes/', method: 'get', params })
}

export function createWish(data: Partial<TravelWish>) {
  return request({ url: '/travel/wishes/', method: 'post', data })
}

export function updateWish(id: number, data: Partial<TravelWish>) {
  return request({ url: `/travel/wishes/${id}/`, method: 'patch', data })
}

export function deleteWish(id: number) {
  return request({ url: `/travel/wishes/${id}/`, method: 'delete' })
}

export function getWishStats() {
  return request({ url: '/travel/wishes/stats/', method: 'get' })
}

export function markWishVisited(id: number) {
  return request({ url: `/travel/wishes/${id}/mark_visited/`, method: 'post' })
}

export function recordWishVisit(id: number, data: {
  visited_at?: string
  visit_rating?: number | null
  visit_notes?: string
  worth_revisit?: boolean
  visit_plan?: number | null
}) {
  return request({ url: `/travel/wishes/${id}/record_visit/`, method: 'post', data })
}

export function addWishToPlan(id: number, data: { plan_id?: number; start_date?: string }) {
  return request({ url: `/travel/wishes/${id}/add_to_plan/`, method: 'post', data })
}

// ===== 行程日志 =====
export function getTripLog(params?: { from?: string; to?: string; plan?: number; city?: string }) {
  return request({ url: '/travel/trip-log/', method: 'get', params })
}

export function consolidateTripDay(data: ConsolidatePayload) {
  return request({ url: '/travel/trip-log/consolidate/', method: 'post', data })
}

// ===== 路线 → 计划 =====
export function getRoutePreview(data: { destinations: string[] }) {
  return request({ url: '/travel/plans/route-preview/', method: 'post', data })
}

export function createPlanFromRoute(data: PlanFromRouteInput) {
  return request({ url: '/travel/plans/from-route/', method: 'post', data })
}
