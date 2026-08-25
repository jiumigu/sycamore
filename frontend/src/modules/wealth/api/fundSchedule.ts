import request from '@/shared/utils/request'
import type { ReserveItem } from '../types/wealthTypes'

/** 获取资金排程历史列表（分页 {count, results}） */
export function getFundScheduleList(params?: { page?: number; page_size?: number }) {
  return request({ url: '/wealth/fund-schedule/', method: 'get', params })
}

/** 创建资金排程快照（每次保存新增一条历史记录） */
export function createFundSchedule(data: { plan_name: string; cash_on_hand: number; reserve_items: ReserveItem[] }) {
  return request({ url: '/wealth/fund-schedule/', method: 'post', data })
}

/** 获取资金排程快照详情 */
export function getFundScheduleDetail(id: number) {
  return request({ url: `/wealth/fund-schedule/${id}/`, method: 'get' })
}

/** 删除资金排程快照 */
export function deleteFundSchedule(id: number) {
  return request({ url: `/wealth/fund-schedule/${id}/`, method: 'delete' })
}

/** 获取固定开销历史记录（供「导入固定开销」选择；跨模块仅依赖 shared request，不引用 toolkit 模块内部） */
export function getFixedExpenseList(params?: { page?: number; page_size?: number }) {
  return request({ url: '/toolkit/fixed-expenses/', method: 'get', params: { page_size: 100, ...params } })
}
