import request from '@/shared/utils/request'
import type { OutputRecord, OutputStats } from '../types/outputTypes'

export function getOutputRecords(params?: Record<string, string>) {
  return request<{ count: number; results: OutputRecord[] }>({
    url: '/goals/outputs/', method: 'get', params,
  })
}

export function createOutputRecord(data: Record<string, unknown>) {
  return request<OutputRecord>({ url: '/goals/outputs/', method: 'post', data })
}

export function updateOutputRecord(id: number, data: Record<string, unknown>) {
  return request<OutputRecord>({ url: `/goals/outputs/${id}/`, method: 'put', data })
}

export function deleteOutputRecord(id: number) {
  return request({ url: `/goals/outputs/${id}/`, method: 'delete' })
}

export function getOutputStats(params?: Record<string, string>) {
  return request<OutputStats>({ url: '/goals/outputs/stats/', method: 'get', params })
}
