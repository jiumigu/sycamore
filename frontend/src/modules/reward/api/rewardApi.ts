import request from '@/shared/utils/request'

export function getRewardPool() {
  return request({ url: '/reward/pool/', method: 'get' })
}

export function getRewardTransactions(params?: { type?: string; source_type?: string; page?: number; page_size?: number }) {
  return request({ url: '/reward/transactions/', method: 'get', params })
}

export function deleteTransaction(id: number) {
  return request({ url: `/reward/transactions/${id}/`, method: 'delete' })
}

export function addRewardTransaction(data: {
  amount: number
  source_type?: string
  transaction_type?: string
  description?: string
}) {
  return request({ url: '/reward/transactions/', method: 'post', data })
}

export function getRewardSourceStats() {
  return request({ url: '/reward/stats/sources/', method: 'get' })
}

// ────────── 礼物清单 ──────────

export function getGiftList(params?: { status?: string; category?: string }) {
  return request({ url: '/reward/gifts/', method: 'get', params })
}

export function getGiftDetail(id: number) {
  return request({ url: `/reward/gifts/${id}/`, method: 'get' })
}

export function createGift(data: Record<string, unknown>) {
  return request({ url: '/reward/gifts/', method: 'post', data })
}

export function updateGift(id: number, data: Record<string, unknown>) {
  return request({ url: `/reward/gifts/${id}/`, method: 'put', data })
}

export function patchGift(id: number, data: Record<string, unknown>) {
  return request({ url: `/reward/gifts/${id}/`, method: 'patch', data })
}

export function deleteGift(id: number) {
  return request({ url: `/reward/gifts/${id}/`, method: 'delete' })
}

export function redeemGift(id: number, data?: { actual_reward?: number }) {
  return request({ url: `/reward/gifts/${id}/redeem/`, method: 'post', data })
}

export function cancelGift(id: number) {
  return request({ url: `/reward/gifts/${id}/cancel/`, method: 'post' })
}

export function getGiftStats() {
  return request({ url: '/reward/gifts/stats/', method: 'get' })
}
