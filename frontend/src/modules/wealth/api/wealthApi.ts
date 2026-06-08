import request from '@/shared/utils/request'
import type { CalendarQueryParams, CoverageInput, BillCreateData } from '../types/wealthTypes'

export function getCalendar(params?: CalendarQueryParams) {
  return request({ url: '/wealth/calendar/', method: 'get', params })
}

export function getWeeklySummary(weekIndex: number) {
  return request({ url: `/wealth/weekly_summary/${weekIndex}/`, method: 'get' })
}

export function getCurrentScenario() {
  return request({ url: '/wealth/scenario/current/', method: 'get' })
}

export function updateCurrentScenario(data: Record<string, unknown>) {
  return request({ url: '/wealth/scenario/current/', method: 'put', data })
}

export function calculateCoverage(data: CoverageInput) {
  return request({ url: '/wealth/calculate_coverage/', method: 'post', data })
}

export function getLifeSummary(params?: { user_id?: number }) {
  return request({ url: '/wealth/summary/', method: 'get', params })
}

export function getBillsByWeek(params: { week_index: number; user_id?: number }) {
  return request({ url: '/wealth/bills/by_week/', method: 'get', params })
}

export function initCalendar(data: { user_id?: number; birth_date?: string }) {
  return request({ url: '/wealth/calendar/init/', method: 'post', data })
}

/** 月度日历 */
export function getMonthlyCalendar(params: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/monthly_calendar/', method: 'get', params })
}

/** 单日明细 */
export function getDailyDetail(params: { date: string; user_id?: number }) {
  return request({ url: '/wealth/daily_detail/', method: 'get', params })
}

/** 月度汇总 */
export function getMonthlySummary(params: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/monthly_summary/', method: 'get', params })
}

/** 快速记账 */
export function createBill(data: BillCreateData) {
  return request({ url: '/wealth/bill/create/', method: 'post', data })
}

// ══════════════════════════════════════════
// 月度复盘 API
// ══════════════════════════════════════════

/** 月度复盘汇总 */
export function getMonthlyReview(params: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/review/monthly_summary/', method: 'get', params })
}

/** 收支趋势 */
export function getTrendData(params: { months?: number; user_id?: number }) {
  return request({ url: '/wealth/review/trend/', method: 'get', params })
}

/** 分类排行 */
export function getCategoryRanking(params: { year: number; month: number; type?: string; user_id?: number }) {
  return request({ url: '/wealth/review/category_ranking/', method: 'get', params })
}

/** 历史复盘列表 */
export function getMonthlyList(params: { page?: number; page_size?: number; user_id?: number }) {
  return request({ url: '/wealth/review/monthly_list/', method: 'get', params })
}

/** 获取复盘数据 */
export function getBalanceList(params: { yearmon: string }) {
  return request({ url: '/wealth/review/balance_list/', method: 'get', params })
}

/** 创建复盘数据 */
export function createBalanceList(data: Record<string, unknown>) {
  return request({ url: '/wealth/review/balance_list/', method: 'post', data })
}

/** 更新复盘数据 */
export function updateBalanceList(data: Record<string, unknown>) {
  return request({ url: '/wealth/review/balance_list/', method: 'put', data })
}

/** 同比环比分析 */
export function getCompareData(params: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/review/compare/', method: 'get', params })
}

/** 生成复盘数据 */
export function generateBalanceInfo(data: { year: number; month: number; user_id?: number }) {
  return request({ url: '/wealth/review/generate/', method: 'post', data })
}

// ══════════════════════════════════════════
// 现金盘点 API
// ══════════════════════════════════════════

/** 资产全景 */
export function getCashFlowOverview(params?: { yearmon?: string }) {
  return request({ url: '/wealth/cashflow/overview/', method: 'get', params })
}

/** 资产趋势 */
export function getAssetTrend(params?: { months?: number; user_id?: number }) {
  return request({ url: '/wealth/cashflow/trend/', method: 'get', params })
}

/** 盘点快照 CRUD */
export function saveSnapshot(data: Record<string, unknown>) {
  return request({ url: '/wealth/cashflow/snapshot/', method: 'post', data })
}

export function updateSnapshot(data: Record<string, unknown>) {
  return request({ url: '/wealth/cashflow/snapshot/', method: 'put', data })
}

export function deleteSnapshot(params: { baid: number }) {
  return request({ url: '/wealth/cashflow/snapshot/', method: 'delete', data: params })
}

/** 盘点历史列表 */
export function getSnapshotList(params?: { page?: number; page_size?: number }) {
  return request({ url: '/wealth/cashflow/snapshot/list/', method: 'get', params })
}

/** 复制上月数据 */
export function copyLastSnapshot(data: { yearmon: string }) {
  return request({ url: '/wealth/cashflow/copy/', method: 'post', data })
}

// ══════════════════════════════════════════
// 定期存款 API
// ══════════════════════════════════════════

/** 定期存款统计 */
export function getRegularStats() {
  return request({ url: '/wealth/regular/stats/', method: 'get' })
}

/** 到期提醒列表 */
export function getRegularExpiring(params?: { days?: number }) {
  return request({ url: '/wealth/regular/expiring/', method: 'get', params })
}

/** 定期存款列表 */
export function getRegularList(params?: { bankinfo?: string; flag?: number; keyword?: string }) {
  return request({ url: '/wealth/regular/list/', method: 'get', params })
}

/** 银行列表 */
export function getRegularBanks() {
  return request({ url: '/wealth/regular/banks/', method: 'get' })
}

/** 新增定期存款 */
export function createRegular(data: Record<string, unknown>) {
  return request({ url: '/wealth/regular/0/', method: 'post', data })
}

/** 获取单条存款详情 */
export function getRegularDetail(id: number) {
  return request({ url: `/wealth/regular/${id}/`, method: 'get' })
}

/** 更新定期存款 */
export function updateRegular(id: number, data: Record<string, unknown>) {
  return request({ url: `/wealth/regular/${id}/`, method: 'put', data })
}

/** 删除定期存款 */
export function deleteRegular(id: number) {
  return request({ url: `/wealth/regular/${id}/`, method: 'delete' })
}

/** 到期处理 */
export function processMature(id: number, data: Record<string, unknown>) {
  return request({ url: `/wealth/regular/${id}/mature/`, method: 'post', data })
}

/** 批量更新到期状态 */
export function updateRegularStatus() {
  return request({ url: '/wealth/regular/update_status/', method: 'post' })
}

/** 获取当前年龄周数（基于出生日期动态计算） */
export function getCurrentAgeWeek() {
  return request({ url: '/wealth/age-week/', method: 'get' })
}

/** 导入随手记 CSV 账单 */
export function importCSV(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request({
    url: '/wealth/import/csv/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
