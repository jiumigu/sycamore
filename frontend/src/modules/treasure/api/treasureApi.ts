import request from '@/shared/utils/request'

import type { LinkCandidateResult, TreasureMeta } from '../types/treasureTypes'

export function getThingList(params?: Record<string, unknown>) {
  return request({ url: '/treasure/things/', method: 'get', params })
}

export function getThingDetail(id: number) {
  return request({ url: `/treasure/things/${id}/`, method: 'get' })
}

export function createThing(data: Record<string, unknown>) {
  return request({ url: '/treasure/things/', method: 'post', data })
}

export function updateThing(id: number, data: Record<string, unknown>) {
  return request({ url: `/treasure/things/${id}/`, method: 'put', data })
}

export function deleteThing(id: number) {
  return request({ url: `/treasure/things/${id}/`, method: 'delete' })
}

/** 口径与枚举的唯一出口（类别文案按侧各一套，不在前端硬编码） */
export function getTreasureMeta() {
  return request<TreasureMeta>({ url: '/treasure/things/meta/', method: 'get' })
}

/**
 * 档案侧「输入即搜实物」。
 *
 * ⚠️ 返回的是 `{rows, total, limit}` 而**不是裸数组** —— 这里存在取数上限，
 *    「只给了前 N 条」必须能被说出来。
 */
export function getLinkCandidates(params: { search: string; limit?: number }) {
  return request<LinkCandidateResult>({
    url: '/treasure/things/link_candidates/',
    method: 'get',
    params,
  })
}
