import request from '@/shared/utils/request'
import type { ReaderGroup, ReaderInteraction } from '../types/readerTypes'

export function getReaderGroups() {
  return request<ReaderGroup[]>({ url: '/relation/reader-groups/', method: 'get' })
}

export function createReaderGroup(data: Record<string, unknown>) {
  return request<ReaderGroup>({ url: '/relation/reader-groups/', method: 'post', data })
}

export function updateReaderGroup(id: number, data: Record<string, unknown>) {
  return request<ReaderGroup>({ url: `/relation/reader-groups/${id}/`, method: 'put', data })
}

export function deleteReaderGroup(id: number) {
  return request({ url: `/relation/reader-groups/${id}/`, method: 'delete' })
}

export function getReaderInteractions(groupId?: number) {
  return request<ReaderInteraction[]>({
    url: '/relation/reader-interactions/',
    method: 'get',
    params: groupId ? { group_id: groupId } : {},
  })
}

export function createReaderInteraction(data: Record<string, unknown>) {
  return request<ReaderInteraction>({ url: '/relation/reader-interactions/', method: 'post', data })
}

export function deleteReaderInteraction(id: number) {
  return request({ url: `/relation/reader-interactions/${id}/`, method: 'delete' })
}

export function getResonancePoints(groupId?: number) {
  return request<ReaderInteraction[]>({
    url: '/relation/reader-interactions/resonance_points/',
    method: 'get',
    params: groupId ? { group_id: groupId } : {},
  })
}

export function getMonthlySummaries(params?: Record<string, unknown>) {
  return request({ url: '/relation/reader-monthly-summaries/', method: 'get', params })
}

export function createMonthlySummary(data: Record<string, unknown>) {
  return request({ url: '/relation/reader-monthly-summaries/', method: 'post', data })
}

export function updateMonthlySummary(id: number, data: Record<string, unknown>) {
  return request({ url: `/relation/reader-monthly-summaries/${id}/`, method: 'put', data })
}

export function deleteMonthlySummary(id: number) {
  return request({ url: `/relation/reader-monthly-summaries/${id}/`, method: 'delete' })
}

export function getReaderYearlyStats(params?: Record<string, unknown>) {
  return request({ url: '/relation/reader-monthly-summaries/stats/', method: 'get', params })
}
