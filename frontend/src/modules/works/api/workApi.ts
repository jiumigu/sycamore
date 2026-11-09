/** 作品 · 接口层
 *
 * 🔴 两条约定（与后端 `views.py` 对齐）：
 *
 * 1. **列表端点返回裸数组**（后端 `pagination_class = None`）——
 *    别写成 `res.data.results`，那会得到 `undefined` 而**不报错**，
 *    页面表现是「一条都没有」，看着像「功能没做」。
 * 2. **期标识由后端下发** —— 请求里带 `period_type`，
 *    返回里的 `period_key` / `in_current_period` 直接用，前端不自己算 ISO 周。
 */
import request from '@/shared/utils/request'
import type { MediaItem } from '@/shared/types/media'
import type {
  PeriodType, Work, WorkCapture, WorkMeta, WorksOverview, Written,
} from '../types/workTypes'

// ══════════════════════════════════════════════════════════════
// 作品
// ══════════════════════════════════════════════════════════════

export function getWorks(params?: { kind?: string; status?: string; period_type?: PeriodType }) {
  return request<Work[]>({ url: '/works/items/', method: 'get', params })
}

export function createWork(data: Record<string, unknown>) {
  return request<{ work: Work; written: Written }>({
    url: '/works/items/', method: 'post', data,
  })
}

export function updateWork(id: number, data: Record<string, unknown>) {
  return request<{ work: Work; written: Written }>({
    url: `/works/items/${id}/`, method: 'patch', data,
  })
}

export function deleteWork(id: number) {
  return request<{ detail: string; written: Written }>({
    url: `/works/items/${id}/`, method: 'delete',
  })
}

// ══════════════════════════════════════════════════════════════
// 待提炼（打勾）
// ══════════════════════════════════════════════════════════════

export function getCaptures(params?: {
  status?: string; source_type?: string; period_type?: PeriodType
}) {
  return request<WorkCapture[]>({ url: '/works/captures/', method: 'get', params })
}

/** 打一个勾。**幂等**：同一来源重复调不会新建第二条（第二次回 200 + `created:false`）。 */
export function capture(data: {
  source_type: string; source_id: number; title: string; excerpt?: string
}) {
  return request<{ capture: WorkCapture; created: boolean; written: Written }>({
    url: '/works/captures/', method: 'post', data,
  })
}

export function uncapture(id: number) {
  return request<{ detail: string; written: Written }>({
    url: `/works/captures/${id}/`, method: 'delete',
  })
}

// ══════════════════════════════════════════════════════════════
// 合成
// ══════════════════════════════════════════════════════════════

export function compose(data: Record<string, unknown>) {
  return request<{ work: Work; written: Written }>({
    url: '/works/compose/', method: 'post', data,
  })
}

// ══════════════════════════════════════════════════════════════
// 媒体上传
// ══════════════════════════════════════════════════════════════

/** 上传作品媒体（图片 / 视频），multipart 字段 file；type 由后端按扩展名判定 */
export function uploadWorkMedia(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request<{ url: string; type: MediaItem['type'] }>({
    url: '/works/media/',
    method: 'post',
    data: fd,
    timeout: 120000,
  })
}

// ══════════════════════════════════════════════════════════════
// 计数 / 枚举 / 出口去向
// ══════════════════════════════════════════════════════════════

export function getOverview() {
  return request<WorksOverview>({ url: '/works/overview/', method: 'get' })
}

export function getMeta() {
  return request<WorkMeta>({ url: '/works/meta/', method: 'get' })
}

export function getChannels() {
  return request<{ values: string[] }>({ url: '/works/channels/', method: 'get' })
}

export function saveChannels(values: string[]) {
  return request<{ values: string[]; written: Written }>({
    url: '/works/channels/', method: 'put', data: { values },
  })
}
