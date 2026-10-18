/**
 * 「菜单项当前是否归档」的唯一实现
 *
 * 真源两处，合并出唯一判据：
 *   1. `menuConfig.allMenuItems[].defaultArchived` —— 无偏好记录时的默认态
 *   2. 后端菜单偏好的 `is_favorite` —— 用户在「菜单管理」里手动切换过的结果
 *
 * 判据：有偏好记录 ⇒ 以记录为准（`is_favorite === false` 即已归档）；
 *       无记录     ⇒ 回落到 `defaultArchived`。
 *
 * 消费方：LayoutSidebar（分组菜单 / 归档折叠区）、6 个默认归档模块页的顶部横幅。
 * 🔴 严禁各页自己判 `defaultArchived` —— 那会把「已经重新启用」的模块继续当归档，
 *    横幅就永远挂在那里（用户已实际踩到：旅行记录默认未归档，横幅却照样显示）。
 *
 * 偏好全应用只拉一次，多调用方共享同一份 ref；保存偏好后调 `refreshMenuArchive()`
 * 让侧边栏与各页横幅立刻跟上，不必刷新页面。
 */

import { ref, computed } from 'vue'
import { allMenuItems } from '@/shared/config/menuConfig'
import { getMenuPrefs } from '@/shared/api/coreApi'

/** menu_key -> is_favorite；null = 还没加载成功（≠ 空偏好，两者不可混用） */
const prefMap = ref<Record<string, boolean> | null>(null)

/** 进行中的请求（并发调用共享同一次，避免 6 个页面各发一遍） */
let inflight: Promise<void> | null = null

/** 拉取菜单偏好（幂等、并发安全） */
export function loadMenuPrefs(): Promise<void> {
  if (prefMap.value !== null) return Promise.resolve()
  if (!inflight) {
    inflight = getMenuPrefs()
      .then(res => {
        const raw = res.data
        const list = (Array.isArray(raw) ? raw : raw?.results ?? []) as Array<{
          menu_key: string
          is_favorite: boolean
        }>
        const map: Record<string, boolean> = {}
        list.forEach(p => { map[p.menu_key] = p.is_favorite })
        prefMap.value = map
      })
      .catch(e => {
        // 取不到偏好 ≠ 全部归档：按「无偏好记录」处理，统一回落到 defaultArchived
        console.error('加载菜单偏好失败，按默认归档态处理', e)
        prefMap.value = {}
      })
      .finally(() => { inflight = null })
  }
  return inflight
}

/** 丢弃缓存重新拉取（保存菜单偏好后调用） */
export function refreshMenuArchive(): Promise<void> {
  prefMap.value = null
  inflight = null
  return loadMenuPrefs()
}

/** 偏好是否已就绪 */
export function isMenuPrefsReady(): boolean {
  return prefMap.value !== null
}

/** 某个菜单项当前是否归档（判据本体，唯一一份） */
export function isMenuArchived(key: string): boolean {
  const map = prefMap.value
  if (map && key in map) return !map[key]
  const item = allMenuItems.find(m => m.key === key)
  return !!item?.defaultArchived
}

/**
 * 页面用：`const { ready, isArchived } = useMenuArchive('dance')`
 *
 * 模板写 `v-if="ready && isArchived"`：偏好未就绪时先不显示横幅，
 * 否则「已取消归档」的模块会先闪一下横幅再消失。
 */
export function useMenuArchive(key: string) {
  loadMenuPrefs()
  const ready = computed(() => prefMap.value !== null)
  const isArchived = computed(() => isMenuArchived(key))
  return { ready, isArchived }
}
