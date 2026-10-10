/** 隐私模式 — API 层 */

import request from '@/shared/utils/request'

export interface ProfileData {
  privacy_mode: boolean
  logseq_path?: string
  /** 金句池长度上限（「系统设置」里可调；超过此字数的摘录不参与「每日金句」轮转） */
  quote_pool_max_len?: number
  /** 该配置的合法区间 [下限, 上限]，**由后端下发** —— 前端不硬编码阈值，只负责显示 */
  quote_pool_len_range?: [number, number]
}

export function getProfile() {
  return request<ProfileData>({ url: '/core/profile/', method: 'get' })
}

export function updateProfile(data: Partial<ProfileData>) {
  return request<ProfileData>({ url: '/core/profile/', method: 'patch', data })
}
