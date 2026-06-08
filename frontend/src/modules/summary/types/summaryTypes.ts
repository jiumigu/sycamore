/** 综合进度看板 — 类型定义 */

export interface ModulePoint {
  module: string
  label: string
  color: string
  points: number
  raw_value: number
  unit: string
}

export interface YearlyOverview {
  year: string
  total_points: number
  yearly_target: number
  monthly_target: number
  progress_percent: number
  remaining_points: number
  modules: ModulePoint[]
}

export interface MonthlyDetail {
  year: string
  month: number
  total_points: number
  month_target: number
  target_percent: number
  modules: ModulePoint[]
}

export interface TrendPoint {
  month: number
  total_points: number
  month_target: number
  wealth: number
  health: number
  times: number
  words: number
  sugar: number
  travel: number
  book: number
}

export interface RadarIndicator {
  name: string
  max: number
  color: string
}

export interface RadarData {
  year: number
  indicators: RadarIndicator[]
  values: number[]
}

export interface ModuleDetail {
  module: string
  label: string
  color: string
  raw_value: number
  points: number
  unit: string
  record_count: number
  records: Record<string, unknown>[]
}

// ── 季度决策工作台 ──────────────────────────────────────

export interface QuarterlyModuleEntry {
  module: string
  label: string
  color: string
  points: number
  raw_value: number
  unit: string
  prev_quarter_points: number
  qoq_change: number
  last_year_points: number
  yoy_change: number
}

export interface QuarterlyReport {
  year: number
  quarter: number
  label: string
  total_points: number
  quarter_target: number
  target_percent: number
  prev_quarter_total: number
  qoq_change: number
  last_year_total: number
  yoy_change: number
  modules: QuarterlyModuleEntry[]
}

export interface QuestionItem {
  question_key: string
  question_category: string
  question_text: string
  related_module: string
}

export interface AnswerItem {
  id?: number
  question_key: string
  question_text: string
  question_category: string
  answer_text: string
  related_module: string
  action_taken: boolean
  updated_at?: string
}

export interface InsightItem {
  type: 'success' | 'warning' | 'danger' | 'info'
  icon: string
  message: string
}

/** 常量 */
export const MODULE_LABELS: Record<string, string> = {
  wealth: '财富',
  health: '健康',
  times: '时间投入',
  words: '文字记录',
  sugar: '小确幸',
  travel: '旅行',
  book: '阅读',
}

export const MODULE_COLORS: Record<string, string> = {
  wealth: '#F59E0B',
  health: '#10B981',
  times: '#6366F1',
  words: '#EC4899',
  sugar: '#F97316',
  travel: '#06B6D4',
  book: '#3B82F6',
}

export const YEARLY_TARGET = 400
export const MONTHLY_TARGET = +(YEARLY_TARGET / 12).toFixed(2)
export const QUARTER_OPTIONS = [
  { value: 1, label: 'Q1 (1-3月)' },
  { value: 2, label: 'Q2 (4-6月)' },
  { value: 3, label: 'Q3 (7-9月)' },
  { value: 4, label: 'Q4 (10-12月)' },
]
