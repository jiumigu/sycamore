/** Core — API 层 */

import request from '@/shared/utils/request'

export function backupDatabase() {
  return request({ url: '/core/backup/database/', method: 'post' })
}

export function quickRecord(data: { module: string; content: string }) {
  return request({ url: '/core/quick-record/', method: 'post', data })
}

export function globalSearch(q: string) {
  return request({ url: '/core/search/', method: 'get', params: { q } })
}

export interface SystemPreset {
  preset_type: string
  values: string[]
  updated_at?: string
}

export function getPresets() {
  return request({ url: '/core/presets/', method: 'get' })
}

export function getPresetByType(type: string) {
  return request({ url: '/core/presets/by_type/', method: 'get', params: { type } })
}

export function savePresetByType(data: { preset_type: string; values: string[] }) {
  return request({ url: '/core/presets/save_by_type/', method: 'post', data })
}
