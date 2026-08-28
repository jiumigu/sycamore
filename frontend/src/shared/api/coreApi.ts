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

// ── 菜单管理（动态侧边栏） ──

export interface MenuPref {
  id?: number
  menu_key: string
  is_favorite: boolean
  sort_order?: number
  updated_at?: string
}

export interface MenuGroupData {
  id?: number
  group_key: string
  group_name: string
  sort_order?: number
  is_visible?: boolean
}

export function getMenuPrefs() {
  return request({ url: '/core/menus/user_prefs/', method: 'get' })
}

export function batchUpdateMenus(updates: { menu_key: string; is_favorite: boolean; sort_order?: number }[]) {
  return request({ url: '/core/menus/batch_update/', method: 'post', data: { updates } })
}

export function getMenuGroups() {
  return request({ url: '/core/menu-groups/', method: 'get' })
}

export function createMenuGroup(data: { group_key: string; group_name: string; sort_order?: number }) {
  return request({ url: '/core/menu-groups/', method: 'post', data })
}

export function updateMenuGroup(id: number, data: Partial<MenuGroupData>) {
  return request({ url: `/core/menu-groups/${id}/`, method: 'patch', data })
}

export function deleteMenuGroup(id: number) {
  return request({ url: `/core/menu-groups/${id}/`, method: 'delete' })
}
