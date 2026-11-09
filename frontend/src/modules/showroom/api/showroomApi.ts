import request from '@/shared/utils/request'

import type { ShowroomMedia, ShowroomMeta, ShowroomPreview, ShowroomProfile } from '../types/showroomTypes'

export function getProfile() {
  return request<ShowroomProfile>({ url: '/showroom/profile/', method: 'get' })
}

export function updateProfile(data: Partial<ShowroomProfile>) {
  return request<ShowroomProfile>({ url: '/showroom/profile/', method: 'put', data })
}

export function getMeta() {
  return request<ShowroomMeta>({ url: '/showroom/meta/', method: 'get' })
}

export function getPreview() {
  return request<ShowroomPreview>({ url: '/showroom/preview/', method: 'get' })
}

export function getCases() {
  return request({ url: '/showroom/cases/', method: 'get' })
}

export function createCase(data: Record<string, unknown>) {
  return request({ url: '/showroom/cases/', method: 'post', data })
}

export function updateCase(id: number, data: Record<string, unknown>) {
  return request({ url: `/showroom/cases/${id}/`, method: 'patch', data })
}

export function deleteCase(id: number) {
  return request({ url: `/showroom/cases/${id}/`, method: 'delete' })
}

export function getSkills() {
  return request({ url: '/showroom/skills/', method: 'get' })
}

export function createSkill(data: Record<string, unknown>) {
  return request({ url: '/showroom/skills/', method: 'post', data })
}

export function updateSkill(id: number, data: Record<string, unknown>) {
  return request({ url: `/showroom/skills/${id}/`, method: 'patch', data })
}

export function deleteSkill(id: number) {
  return request({ url: `/showroom/skills/${id}/`, method: 'delete' })
}

export function getWorks() {
  return request({ url: '/showroom/works/', method: 'get' })
}

export function createWork(data: Record<string, unknown>) {
  return request({ url: '/showroom/works/', method: 'post', data })
}

export function updateWork(id: number, data: Record<string, unknown>) {
  return request({ url: `/showroom/works/${id}/`, method: 'patch', data })
}

export function deleteWork(id: number) {
  return request({ url: `/showroom/works/${id}/`, method: 'delete' })
}

/** 作品库候选（选作品进馆）—— 复用 works 模块的列表接口，展厅不另造取数口。 */
export function getWorkCandidates(params?: Record<string, unknown>) {
  return request({ url: '/works/items/', method: 'get', params })
}

/** 上传展厅媒体（图片 / 视频），multipart 字段 file；type 由后端按扩展名判定 */
export function uploadShowroomMedia(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request<{ url: string; type: ShowroomMedia['type'] }>({
    url: '/showroom/media/',
    method: 'post',
    data: fd,
    timeout: 120000,
  })
}
