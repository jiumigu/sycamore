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

export function getQuoteStats() {
  return request({ url: '/toolkit/quotes/stats/', method: 'get' })
}
