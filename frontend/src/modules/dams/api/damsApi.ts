import request from '@/shared/utils/request'

export function getFileList(params?: Record<string, unknown>) {
  return request({ url: '/dams/files/', method: 'get', params })
}

export function getFileDetail(id: number) {
  return request({ url: `/dams/files/${id}/`, method: 'get' })
}

export function createFile(data: Record<string, unknown>) {
  return request({ url: '/dams/files/', method: 'post', data })
}

export function updateFile(id: number, data: Record<string, unknown>) {
  return request({ url: `/dams/files/${id}/`, method: 'put', data })
}

export function deleteFile(id: number) {
  return request({ url: `/dams/files/${id}/`, method: 'delete' })
}

export function getAttentionMap(params?: Record<string, unknown>) {
  return request({ url: '/dams/files/attention_map/', method: 'get', params })
}

export function markFileOrganized(id: number) {
  return request({ url: `/dams/files/${id}/mark_organized/`, method: 'post' })
}

export function getAccessLogList(params?: Record<string, unknown>) {
  return request({ url: '/dams/access-logs/', method: 'get', params })
}

export function createAccessLog(data: Record<string, unknown>) {
  return request({ url: '/dams/access-logs/', method: 'post', data })
}
