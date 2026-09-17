import request from '@/shared/utils/request'
import type {
  RedemptionConfig, PoolInject, AttrRule, RedemptionStats, SyncResult,
} from '../types/redemptionTypes'

/** 读取赎回期配置 + 派生字段 */
export function getRedemption() {
  return request<RedemptionConfig>({ url: '/redemption/', method: 'get' })
}

/** 改起止 / 本金 */
export function updateRedemption(data: Partial<RedemptionConfig>) {
  return request<RedemptionConfig>({ url: '/redemption/', method: 'put', data })
}

/** 暂停追踪（可选指定恢复日） */
export function pauseTracking(data?: { resume_at?: string }) {
  return request({ url: '/redemption/pause/', method: 'post', data })
}

/** 恢复追踪 */
export function resumeTracking() {
  return request({ url: '/redemption/resume/', method: 'post' })
}

/** 现金池注入列表 */
export function listInjects() {
  return request<PoolInject[]>({ url: '/redemption/injects/', method: 'get' })
}

/** 新增现金池注入 */
export function createInject(data: Record<string, unknown>) {
  return request({ url: '/redemption/injects/', method: 'post', data })
}

/** 归因规则列表 */
export function listAttrRules() {
  return request<AttrRule[]>({ url: '/redemption/attr-rules/', method: 'get' })
}

/** 新增归因规则 */
export function createAttrRule(data: Record<string, unknown>) {
  return request({ url: '/redemption/attr-rules/', method: 'post', data })
}

/** 更新归因规则 */
export function updateAttrRule(id: number, data: Record<string, unknown>) {
  return request({ url: `/redemption/attr-rules/${id}/`, method: 'put', data })
}

/** 删除归因规则 */
export function deleteAttrRule(id: number) {
  return request({ url: `/redemption/attr-rules/${id}/`, method: 'delete' })
}

/** 合体统计 */
export function getRedemptionStats() {
  return request<RedemptionStats>({ url: '/redemption/stats/', method: 'get' })
}

/** 同步到资金推演（preview 仅返回 / apply 写入） */
export function syncScenario(mode: 'preview' | 'apply') {
  return request<SyncResult>({ url: '/redemption/sync-scenario/', method: 'post', data: { mode } })
}
