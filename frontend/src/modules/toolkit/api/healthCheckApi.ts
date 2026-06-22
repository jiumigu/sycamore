import request from '@/shared/utils/request'
import type { HealthSelfCheck } from '../types/healthCheckTypes'

export function getHealthCheckList(params?: Record<string, unknown>) {
  return request<{ results: HealthSelfCheck[]; count: number }>({
    url: '/toolkit/health-self-checks/',
    method: 'get',
    params: { page_size: 100, ...params },
  })
}

export function getHealthCheckDetail(id: number) {
  return request<HealthSelfCheck>({ url: `/toolkit/health-self-checks/${id}/`, method: 'get' })
}

export function createHealthCheck(data: Record<string, unknown>) {
  return request<HealthSelfCheck>({ url: '/toolkit/health-self-checks/', method: 'post', data })
}

export function updateHealthCheck(id: number, data: Partial<HealthSelfCheck>) {
  return request<HealthSelfCheck>({ url: `/toolkit/health-self-checks/${id}/`, method: 'patch', data })
}

export function deleteHealthCheck(id: number) {
  return request({ url: `/toolkit/health-self-checks/${id}/`, method: 'delete' })
}
