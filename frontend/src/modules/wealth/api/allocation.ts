import request from '@/shared/utils/request'

export interface AllocationInput {
  category_id: number
  amount: number
  note?: string
}

export interface CommitmentInput {
  name: string
  amount: number
  due_date: string
  source?: string
  note?: string
}

/** 获取月度分配计划详情 */
export function getAllocationDetail(params: { year_month: string }) {
  return request({ url: '/wealth/allocation/detail/', method: 'get', params })
}

/** 创建/更新分配计划（幂等，可反复保存） */
export function createAllocationPlan(data: {
  year_month: string
  total_cash: number
  allocations: AllocationInput[]
  commitments: CommitmentInput[]
}) {
  return request({ url: '/wealth/allocation/create/', method: 'post', data })
}

/** 增量更新分配项 */
export function updateAllocations(data: { plan_id: number; allocations: AllocationInput[] }) {
  return request({ url: '/wealth/allocation/update-allocations/', method: 'post', data })
}

/** 记录某分类实际花费 */
export function recordSpending(data: {
  plan_id: number
  category_id: number
  amount: number
  note?: string
}) {
  return request({ url: '/wealth/allocation/record-spending/', method: 'post', data })
}

/** 保存自由决策 */
export function saveDecision(data: { plan_id: number; content: string; category?: string }) {
  return request({ url: '/wealth/allocation/save-decision/', method: 'post', data })
}

/** 获取可用分配类别 */
export function getAllocationCategories() {
  return request({ url: '/wealth/allocation/categories/', method: 'get' })
}
