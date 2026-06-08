/** 隐私模式 — API 层 */

import request from '@/shared/utils/request'

export interface ProfileData {
  privacy_mode: boolean
}

export function getProfile() {
  return request<ProfileData>({ url: '/core/profile/', method: 'get' })
}

export function updateProfile(data: Partial<ProfileData>) {
  return request<ProfileData>({ url: '/core/profile/', method: 'patch', data })
}
