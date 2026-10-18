/**
 * 身上之物（v3.62.4）接口封装
 *
 * ⚠️ 列表端点全是**裸数组**（后端显式 `pagination_class = None`）。
 *    如果哪天被 DRF 全局分页包成 `{count, results}`，前端按数组消费会**静默变空** ——
 *    看起来像「一条都没有」，实际是格式变了。store 里对每个数组都做了兜底。
 *
 * ⚠️ 刻意**不提供** `?ordering=`：排序在后端定死（部位的自定义顺序 → 最近录入）。
 *    本模块没有任何派生数值列，开这个口子只会让前端多一份可以漂移的口径。
 */

import request from '@/shared/utils/request'
import type {
  BodyMeta,
  BodyNeed,
  BodyNeedFormData,
  BodyPart,
  BodyPartFormData,
  BodySeedResult,
  BodySummary,
} from '../types/bodyTypes'

// ── 部位（轻量主数据） ──

/** 部位列表 —— 后端返回**裸数组** */
export function getBodyParts() {
  return request({ url: '/wealth/body/parts/', method: 'get' })
}

export function createBodyPart(data: BodyPartFormData) {
  return request({ url: '/wealth/body/parts/', method: 'post', data })
}

export function updateBodyPart(id: number, data: Partial<BodyPartFormData>) {
  return request({ url: `/wealth/body/parts/${id}/`, method: 'patch', data })
}

/**
 * 删一个部位 —— 其下还有位时后端返回 **400 + 可照做的提示**
 *
 * 🔴 **不级联删除**：删掉一个建错的空部位，与删掉整个部位下的所有位，
 *    不该走同一个按钮。调用方要把 400 的 `detail` 原样弹给用户（里面带着「还有 N 条」）。
 */
export function deleteBodyPart(id: number) {
  return request({ url: `/wealth/body/parts/${id}/`, method: 'delete' })
}

/**
 * 初始化默认部位（幂等）—— **只建部位，不预设任何位**
 *
 * ⚠️ `overwrite: true` 会覆盖已有部位的说明与排序，调用前必须先问一句。
 */
export function seedBodyParts(data?: { overwrite?: boolean }) {
  return request({ url: '/wealth/body/parts/seed/', method: 'post', data: data ?? {} })
}

// ── 位 ──

/**
 * 位列表 —— 后端返回**裸数组**
 *
 * `pending: 1` 与顶部那个「还没搞定」的数字**同源**：两者走后端同一个判据，
 * 所以点进去看到的行数一定对得上（不对账的话，就是「念 5 件、看到 3 行」）。
 */
export function getBodyNeeds(params?: {
  part?: number
  find_status?: string
  pending?: 1
  search?: string
}) {
  return request({ url: '/wealth/body/needs/', method: 'get', params })
}

export function createBodyNeed(data: BodyNeedFormData) {
  return request({ url: '/wealth/body/needs/', method: 'post', data })
}

export function updateBodyNeed(id: number, data: Partial<BodyNeedFormData>) {
  return request({ url: `/wealth/body/needs/${id}/`, method: 'patch', data })
}

/**
 * 删除一个位 —— **物理删除**
 *
 * 这就是「不需要这一条了」的出口。也是刻意不给「不想找了」状态的原因：
 * 那个状态会同时装「真的不需要」与「暂时懒得找」两种相反的东西。
 */
export function deleteBodyNeed(id: number) {
  return request({ url: `/wealth/body/needs/${id}/`, method: 'delete' })
}

// ── 汇总与口径 ──

/** 顶部计数 —— 只读、实时算 */
export function getBodySummary() {
  return request({ url: '/wealth/body/summary/', method: 'get' })
}

/** 枚举与口径的单一出口 —— 前端不硬编码任何选项文案或阈值 */
export function getBodyMeta() {
  return request({ url: '/wealth/body/meta/', method: 'get' })
}

// ── 类型再导出：组件按需取用，避免各处重复 import 两个文件 ──

export type {
  BodyMeta,
  BodyNeed,
  BodyNeedFormData,
  BodyPart,
  BodyPartFormData,
  BodySeedResult,
  BodySummary,
}
