import request from '@/shared/utils/request'
import type { Quote, QuoteFormData } from '../types/quoteTypes'

export function getQuoteList(params?: Record<string, unknown>) {
  return request({ url: '/toolkit/quotes/', method: 'get', params })
}

export function getQuoteDetail(id: number) {
  return request({ url: `/toolkit/quotes/${id}/`, method: 'get' })
}

export function createQuote(data: QuoteFormData) {
  return request({ url: '/toolkit/quotes/', method: 'post', data })
}

export function updateQuote(id: number, data: Partial<QuoteFormData>) {
  return request({ url: `/toolkit/quotes/${id}/`, method: 'patch', data })
}

export function deleteQuote(id: number) {
  return request({ url: `/toolkit/quotes/${id}/`, method: 'delete' })
}

export function getRandomQuote() {
  return request({ url: '/toolkit/quotes/random/', method: 'get' })
}

/**
 * 取一条金句：**长度不超上限的池 + 冷落优先**（汇总总览与仪表盘共用，不再用 random/）。
 *
 * 与 random/ 的区别：random/ 是全池等概率随机，太长的整段问答也会被抽中、
 * 而卡片只截前 200 字 ⇒ 显示成一段读不完的断句。本接口只从
 * 「正文字数 ≤ 当前上限」的池里取（上限在「系统管理 → 系统设置」里可调），
 * 且按「被推得最少的先推」轮转。
 *
 * ⚠️ 上限**不在前端写第二份** —— 判断某条摘录在不在池内，读响应里的 `in_golden_pool`。
 * ⚠️ 池为空时后端返回 **204**（无响应体）⇒ `res.data` 是 `''`，
 * 调用方要按「无金句」处理，别当对象用。
 */
export function getNextQuote() {
  return request({ url: '/toolkit/quotes/next/', method: 'get' })
}

export function getQuoteStats() {
  return request({ url: '/toolkit/quotes/stats/', method: 'get' })
}
