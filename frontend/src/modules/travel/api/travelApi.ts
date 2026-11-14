import request from '@/shared/utils/request'
import type {
  ConsolidatePayload,
  PlanFromRouteInput,
  TravelFormData,
  TravelPlanInput,
  TravelPlanItemInput,
  TravelPlanPatch,
  TravelPlanStopInput,
  TravelWish,
} from '../types/travelTypes'

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

/**
 * 改计划基本信息用 **PATCH**，不用 PUT。
 *
 * 🔴 PUT 是非 partial 的：没传的字段会被当成「传了默认值」——
 *    只改名会把 `status` 悄悄重置成「计划中」、`notes` 清空（模型 `default` 生效）。
 *    这正是「看着保存成功、实际改了别的东西」的典型。
 */
export function updateTravelPlan(id: number, data: TravelPlanPatch) {
  return request({ url: `/travel/plans/${id}/`, method: 'patch', data })
}

export function deleteTravelPlan(id: number) {
  return request({ url: `/travel/plans/${id}/`, method: 'delete' })
}

// ===== 站点（路线上的有序城市） =====
export function addPlanStop(planId: number, data: TravelPlanStopInput) {
  return request({ url: `/travel/plans/${planId}/stops/`, method: 'post', data })
}

export function updatePlanStop(
  planId: number,
  stopId: number,
  data: Partial<TravelPlanStopInput>,
) {
  return request({ url: `/travel/plans/${planId}/stops/${stopId}/`, method: 'patch', data })
}

export function deletePlanStop(planId: number, stopId: number) {
  return request({ url: `/travel/plans/${planId}/stops/${stopId}/`, method: 'delete' })
}

/**
 * 重排站点：`order` 必须是**该计划全部站点的 id**（整份给）。
 *
 * 只给一半会留下空洞顺序（1,3,7），下一次加站又要猜一次该用什么 order。
 */
export function reorderPlanStops(planId: number, order: number[]) {
  return request({ url: `/travel/plans/${planId}/stops/reorder/`, method: 'post', data: { order } })
}

export function addPlanItem(planId: number, data: TravelPlanItemInput) {
  return request({ url: `/travel/plans/${planId}/items/`, method: 'post', data })
}

export function deletePlanItem(planId: number, itemId: number) {
  return request({ url: `/travel/plans/${planId}/items/${itemId}/`, method: 'delete' })
}

/** 把条目挪到别站 / 挪到「路上」（`stop: null`，必须显式传） */
export function movePlanItem(planId: number, itemId: number, stop: number | null) {
  return request({
    url: `/travel/plans/${planId}/items/${itemId}/move/`,
    method: 'post',
    data: { stop },
  })
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
