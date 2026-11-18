import request from '@/shared/utils/request'

export function getSugarList(params?: Record<string, unknown>) {
  return request({ url: '/sugar/records/', method: 'get', params })
}

export function getSugarDetail(id: number) {
  return request({ url: `/sugar/records/${id}/`, method: 'get' })
}

export function createSugar(data: Record<string, unknown>) {
  return request({ url: '/sugar/records/', method: 'post', data })
}

export function updateSugar(id: number, data: Record<string, unknown>) {
  return request({ url: `/sugar/records/${id}/`, method: 'put', data })
}

export function deleteSugar(id: number) {
  return request({ url: `/sugar/records/${id}/`, method: 'delete' })
}

export function getSugarCategories(params?: Record<string, unknown>) {
  return request({ url: '/sugar/categories/', method: 'get', params })
}

export function getJoyTypeStats(params?: Record<string, unknown>) {
  return request({ url: '/sugar/records/joy_type_stats/', method: 'get', params })
}

/**
 * 快乐类型筛选项（下拉框唯一来源）。
 *
 * 传 `year` / `month` / `category` 让每个选项带上「当期有多少条」；
 * ⚠️ **不要传 `joy_type`** —— 后端会故意忽略它，但前端也不该假装自己在筛，
 *    否则读代码的人会以为「选了类型之后其它选项的条数会变 0」是预期行为。
 */
export function getJoyTypeOptions(params?: Record<string, unknown>) {
  return request({ url: '/sugar/records/joy_types/', method: 'get', params })
}

/**
 * 标签筛选项（标签下拉框唯一来源）。
 *
 * 传 `year` / `month` / `category` / `joy_type` 让每个选项带上「当期有多少条」；
 * ⚠️ **不要传 `tag`** —— 后端会故意忽略它，但前端也不该假装自己在筛。
 *
 * 与 `getJoyTypeOptions` 同构：选项集合取全库，条数跟着筛选走。
 */
export function getTagOptions(params?: Record<string, unknown>) {
  return request({ url: '/sugar/records/tags/', method: 'get', params })
}

/**
 * 快乐程度档位表（后端唯一真源）。
 *
 * 录入弹窗要在**拖滑块时**立刻显示档位词，那时还没有记录、拿不到 `reward_label`，
 * 所以整张表必须下发一次。前端**不许**自己抄一份边界（曾经抄过四份，抄出了
 * 「弹窗说非常开心、列表说很高兴」）。
 */
export function getHappinessBands() {
  return request({ url: '/sugar/records/happiness_bands/', method: 'get' })
}

// ─── 小确幸模板 API ───

export function getSugarTemplates() {
  return request({ url: '/sugar/templates/', method: 'get' })
}

export function createSugarTemplate(data: Record<string, unknown>) {
  return request({ url: '/sugar/templates/', method: 'post', data })
}

export function updateSugarTemplate(id: number, data: Record<string, unknown>) {
  return request({ url: `/sugar/templates/${id}/`, method: 'put', data })
}

export function deleteSugarTemplate(id: number) {
  return request({ url: `/sugar/templates/${id}/`, method: 'delete' })
}
