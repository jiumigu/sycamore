/** 决策追踪器 — API 层（长期观察型决策：追踪 + 日常记录 + 随时预览 + 到期报告） */

import request from '@/shared/utils/request'

/** 倾向值：默认追踪为 continue/quit/uncertain；自定义倾向选项的追踪直接存选项文字 */
export type Tendency = string
/** 倾向选项（key 即记录存的 tendency 值） */
export interface LeanOption { key: string; label: string }

/** 默认三选项（追踪未自定义时使用） */
export const DEFAULT_LEAN_OPTIONS: LeanOption[] = [
  { key: 'continue', label: '想继续' },
  { key: 'quit', label: '不想继续' },
  { key: 'uncertain', label: '不确定' },
]
/** 默认三选项的展示元信息（图标/颜色） */
export const TENDENCY_META: Record<string, { label: string; icon: string; color: string; tag: 'success' | 'danger' | 'warning' }> = {
  continue: { label: '想继续', icon: '✓', color: '#52c41a', tag: 'success' },
  quit: { label: '不想继续', icon: '✗', color: '#f5222d', tag: 'danger' },
  uncertain: { label: '不确定', icon: '？', color: '#fa8c16', tag: 'warning' },
}
/** 自定义选项循环色板 */
export const CUSTOM_LEAN_COLORS = ['#409eff', '#fa8c16', '#9254de', '#13c2c2', '#f759ab', '#8c8c8c']

/** 取某倾向的展示元信息（自定义选项按出现顺序配色） */
export function leanMeta(t: string, options?: LeanOption[]): { label: string; icon: string; color: string; tag: 'success' | 'danger' | 'warning' | 'primary' | 'info' } {
  const builtin = TENDENCY_META[t]
  if (builtin) return builtin
  const opts = options ?? []
  const idx = Math.max(0, opts.findIndex(o => o.key === t))
  return { label: t, icon: '', color: CUSTOM_LEAN_COLORS[idx % CUSTOM_LEAN_COLORS.length], tag: 'primary' }
}
/** 情绪强度 1–5（旧版「低/中/高」已分别映射为 2/3/4） */
export type Intensity = 1 | 2 | 3 | 4 | 5

/** 强度选项：数值越大越强烈 */
export const INTENSITY_OPTIONS: Array<{ value: Intensity; label: string; color: string }> = [
  { value: 1, label: '很弱', color: '#8c8c8c' },
  { value: 2, label: '弱', color: '#8c8c8c' },
  { value: 3, label: '中', color: '#d46b08' },
  { value: 4, label: '强', color: '#cf1322' },
  { value: 5, label: '很强', color: '#a8071a' },
]

export function intensityLabel(i: number): string {
  return INTENSITY_OPTIONS.find(o => o.value === i)?.label ?? String(i)
}

export function intensityColor(i: number): string {
  return INTENSITY_OPTIONS.find(o => o.value === i)?.color ?? '#8c8c8c'
}

export interface DecisionTracker {
  id: number
  topic: string
  background: string
  start_date: string
  end_date: string
  status: '观察中' | '已到期' | '已决策' | '已归档'
  final_decision: string
  decision_date: string | null
  review_note: string
  /** 自定义倾向选项（文字数组，2–6 项）；null/空 = 用默认三项 */
  lean_options: string[] | null
  created_at?: string
  updated_at?: string
  record_count?: number
  /** 距结束天数（负数=已过期），后端计算 */
  days_left?: number
}

export interface DecisionRecord {
  id: number
  tracker: number
  record_date: string
  tendency: Tendency
  reason: string
  intensity: Intensity
  created_at?: string
}

export interface DecisionReport {
  tracker: {
    id: number
    topic: string
    background: string
    start_date: string
    end_date: string
    status: string
  }
  /** 该追踪的倾向选项（决定统计列/图表系列） */
  options: LeanOption[]
  total_records: number
  record_days: number
  tendency_stats: Array<{ tendency: Tendency; label: string; count: number; percent: number }>
  /** 每月各倾向条数（键为 tendency 值，见 options） */
  monthly_trend: Array<{ month: string } & Record<string, number>>
  reasons: Record<Tendency, Array<{ record_date: string; intensity: Intensity; intensity_label: string; reason: string }>>
}

/** 单条决策的倾向预览——占比 + 强度加权分数 + 连续断记天数 */
export interface TrackerPreviewItem {
  tracker_id: number
  topic: string
  status: string
  total_records: number
  record_days: number
  last_record_date: string | null
  /** 距最后一次记录（无记录则以观察开始日计）的天数 */
  stale_days: number
  needs_reminder: boolean
  /** 该追踪的倾向选项 */
  options: LeanOption[]
  lean_tendency: Tendency | null
  lean_label: string
  /** 主导倾向的条数占比 */
  lean_percent: number
  weighted_total: number
  /** 强度加权倾向分：默认三选项 = (quit−continue)/两者加权和×100（正=偏离开）；自定义选项 = 主导−次主导优势分（恒 ≥ 0） */
  weighted_score: number
  /** 加权口径下主导倾向（默认= quit）的占比 */
  weighted_lean_percent: number
  high_count: number
  conclusion: string
  tendency_stats: Array<{
    tendency: Tendency
    label: string
    count: number
    percent: number
    weighted: number
    weighted_percent: number
    avg_intensity: number
    high_count: number
    high_ratio: number
  }>
}

export interface DecisionPreview {
  generated_at: string
  stale_threshold_days: number
  tracker_count: number
  total_records: number
  has_reminder: boolean
  reminder_text: string
  stale_trackers: Array<{ tracker_id: number; topic: string; stale_days: number; last_record_date: string | null }>
  items: TrackerPreviewItem[]
}

/** 列表（分页） */
export function getDecisionTrackers(params?: { status?: string; page?: number }) {
  return request<{ count: number; results: DecisionTracker[] }>({
    url: '/toolkit/decision-trackers/', method: 'get', params,
  })
}

export function createDecisionTracker(data: Partial<DecisionTracker>) {
  return request<DecisionTracker>({ url: '/toolkit/decision-trackers/', method: 'post', data })
}

export function updateDecisionTracker(id: number, data: Partial<DecisionTracker>) {
  return request<DecisionTracker>({ url: `/toolkit/decision-trackers/${id}/`, method: 'patch', data })
}

export function deleteDecisionTracker(id: number) {
  return request({ url: `/toolkit/decision-trackers/${id}/`, method: 'delete' })
}

/** 某追踪的全部日常记录 */
export function getTrackerRecords(trackerId: number) {
  return request<DecisionRecord[]>({ url: `/toolkit/decision-trackers/${trackerId}/records/`, method: 'get' })
}

/** 新增一条日常记录 */
export function createDecisionRecord(data: Partial<DecisionRecord>) {
  return request<DecisionRecord>({ url: '/toolkit/decision-records/', method: 'post', data })
}

/** 删除一条日常记录（记错了可删） */
export function deleteDecisionRecord(id: number) {
  return request({ url: `/toolkit/decision-records/${id}/`, method: 'delete' })
}

/** 到期汇总报告 */
export function getDecisionReport(trackerId: number) {
  return request<DecisionReport>({ url: `/toolkit/decision-trackers/${trackerId}/report/`, method: 'get' })
}

/** 随时可看的倾向汇总（占比 + 强度加权 + 断记提醒），不必等到期 */
export function getDecisionPreview(params?: { tracker?: number; status?: string }) {
  return request<DecisionPreview>({ url: '/toolkit/decision-trackers/preview/', method: 'get', params })
}

/** 做出决定 */
export function decideTracker(id: number, data: { final_decision: string; decision_date?: string }) {
  return request<DecisionTracker>({ url: `/toolkit/decision-trackers/${id}/decide/`, method: 'post', data })
}

/** 归档（可带事后回看） */
export function archiveTracker(id: number, data?: { review_note?: string }) {
  return request<DecisionTracker>({ url: `/toolkit/decision-trackers/${id}/archive/`, method: 'post', data })
}
