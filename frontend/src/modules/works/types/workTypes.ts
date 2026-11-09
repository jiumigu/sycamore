/** 作品 · 类型定义
 *
 * 🔴 枚举**不在这里定**（这里只是它们的 TypeScript 形状）——
 *    取值由 `GET /api/works/meta/` 下发，前端零副本
 *    （抄一份就会漏改，而且**不报错**：界面上只是少一个下拉项）。
 */
import type { MediaItem } from '@/shared/types/media'

export type WorkKind =
  | 'article' | 'model' | 'template' | 'checklist'
  | 'craft' | 'drawing' | 'embroidery'
  | 'tutorial' | 'other'

/** ⚠️ `private` 不是「草稿」—— 它是「本来就不打算发」，不是「还没做完」。 */
export type WorkStatus = 'private' | 'ready' | 'published'

/**
 * 七个来源。
 *
 * 🔴 取值真源在后端 `CAPTURE_SOURCE_CHOICES`（这里只是形状），
 *    但**类型必须写全** —— 下面的 `SOURCE_SHORT` 是
 *    `Record<CaptureSource, string>`，少一个来源会在 `vue-tsc` 阶段直接报错；
 *    若类型漏了、映射也漏了，收口台上那个来源只会显示成字面量 `undefined`
 *    （不报错，只是看不懂）。
 */
export type CaptureSource =
  | 'milestone' | 'inbox' | 'book' | 'diary' | 'quote' | 'ask' | 'treasure'
export type CaptureStatus = 'pending' | 'used' | 'dropped'

/** 行内「值得留」标记的三态。
 *
 * 🔴 **不是布尔** —— 「没勾」与「勾了」之外还有第三态「已收进作品」：
 *    那时不能在这里取消（会让作品凭空少一个来源），界面要去「作品」页处理。
 *    压成布尔，第三态就只剩「点了报错」这一种表现。
 *
 * ⚠️ 放在这里而不是组件里：`<script setup>` 内**不允许 `export`**，
 *    类型要从 `.vue` 里导出会直接编译不过。
 */
export type KeepState = 'none' | 'pending' | 'used'

export type PeriodType = 'weekly' | 'monthly'

export interface EnumOption {
  value: string
  label: string
}

/** 作品的来源（哪条里程碑 / 哪个收件箱条目 / 哪本书 / 哪条日记）。 */
export interface WorkOrigin {
  id: number
  source_type: CaptureSource
  source_type_display: string
  title: string
}

export interface Work {
  id: number
  name: string
  summary: string
  kind: WorkKind
  kind_display: string
  status: WorkStatus
  status_display: string
  /** 空串 = 「要发但还没定发到哪」，与 `status='private'` 是两件事 */
  channel: string
  note: string
  /** 作品的本体证据（图片 / 视频），type 由后端上传接口判定下发 */
  media: MediaItem[]
  created_at: string
  updated_at: string
  origin: WorkOrigin[]
  /** 由**后端**按 `created_at` 算出来的期标识（前端零计算） */
  period_key: string | null
  /** 这件是不是「本期」成形的（后端判并下发，前端不自己比字符串） */
  in_current_period: boolean
}

export interface WorkCapture {
  id: number
  source_type: CaptureSource
  source_type_display: string
  source_id: number
  title: string
  excerpt: string
  status: CaptureStatus
  status_display: string
  work: number | null
  work_name: string | null
  captured_at: string
  period_key: string | null
  /** 这条是不是「本期」勾的（后端判并下发） */
  in_current_period: boolean
}

export interface WorkMeta {
  kinds: EnumOption[]
  statuses: EnumOption[]
  sources: EnumOption[]
  channels: string[]
}

export interface WorksOverview {
  total: number
  published: number
  ready: number
  pending_captures: number
  total_captures: number
  channels: string[]
}

/** 写操作的回执（写了哪张表、几行）—— 运行时可见，出问题一眼看出哪步没写。 */
export type Written = Record<string, number>

/** 出口状态 → Element Plus 标签色。**不套涨跌红绿** —— 它量的是「走到哪一步」。 */
export const STATUS_TAG: Record<WorkStatus, 'info' | 'warning' | 'success'> = {
  private: 'info',
  ready: 'warning',
  published: 'success',
}

/** 来源 → 图标前的短标签。⚠️ 只用于列表里一眼分辨，不参与任何判断。
 *
 *  ⚠️ 键名必须与后端 `CAPTURE_SOURCE_CHOICES` 对齐 —— 少一个不会报错，
 *     只会让那个来源在收口台上显示成 `undefined`（字面量就是 undefined）。
 */
export const SOURCE_SHORT: Record<CaptureSource, string> = {
  milestone: '里程碑',
  inbox: '收件箱',
  book: '读书',
  diary: '日记',
  quote: '摘录',
  ask: '问答',
  treasure: '档案馆',
}
