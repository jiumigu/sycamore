/** 综合进度看板 — 类型定义 */

/**
 * 覆盖率 + 强度（v3.62.43）
 *
 * 🔴 两个分母刻意不同：
 *   覆盖率 = 有记录的期数 ÷ **该有的期数**  → 回答「有没有断」
 *   强度   = 总量 ÷ **有记录的期数**        → 回答「记的时候做了多少」
 * `pct` / `intensity` 可以是 null（算不出来）—— **null 不是 0%**，显示 `—`。
 */
export interface Coverage {
  period_kind: 'day' | 'month'
  /** 「天」/「月」—— 与 covered/periods 成对使用，别单独渲染数字 */
  period_word: string
  /** 该维度的覆盖率叫法：记录覆盖 / 记账覆盖 / 出行覆盖 / 阅读覆盖 */
  label: string
  covered: number
  periods: number
  pct: number | null
  intensity: number | null
  intensity_label: string
  /** 如「步/天」「元/月」，自带分母，前端不再拼 */
  intensity_unit: string
  recent_covered: number | null
  recent_periods: number | null
  recent_pct: number | null
}

export interface ModulePoint {
  module: string
  label: string
  color: string
  /** 内部评分单位，界面不再展示 —— 只用于 achievement_pct */
  points: number
  /** 原始量（未按单位归一）。null = 该区间取不到，≠ 0 */
  raw_value: number | null
  /** 已按 unit 的量级前缀归一的展示值（448067 步 → 44.81）。前端直接拼 unit，不再折算 */
  display_value: number | null
  unit: string
  /** 取不到 / 按 0 计 的原因码，前端只查表 */
  zero_reason?: string | null
  coverage: Coverage
  /** 雷达该轴满格刻度（点），来自七维封顶配置 */
  axis_max: number | null
  /** 目标换算回物理量（财富：元）—— 「净额 / 目标」用这个做分母 */
  achievement_target: number | null
  /** 🔴 可为负：净流出年份就是负达成率，不能被 floor 成 0% */
  achievement_pct: number | null
}

/** 最短板：覆盖率最低的那根轴（由后端判定，前端不自己比大小） */
export interface Weakest {
  module: string
  label: string
  color: string
  coverage_pct: number
  covered: number
  periods: number
  period_word: string
  recent_pct: number | null
  recent_covered: number | null
  recent_periods: number | null
}

export interface OverviewWindow {
  elapsed_days: number
  elapsed_months: number
  is_current_year?: boolean
}

/** 年度总览 —— 🔴 没有 total_points / yearly_target（v3.62.43 拆除总分） */
export interface YearlyOverview {
  year: string
  as_of: string
  window: OverviewWindow
  modules: ModulePoint[]
  weakest: Weakest | null
}

export interface MonthlyDetail {
  year: string
  month: number
  window: OverviewWindow
  modules: ModulePoint[]
  weakest: Weakest | null
}

/** 月度覆盖率；未来月份各维度为 null（不是 0） */
export interface TrendMonth {
  month: number
  is_future: boolean
  /** 覆盖率：None = 该月还没结 / 还没到 */
  coverage: Record<string, number | null>
  /** 分子：有记录的期数（提示框显示「42/292 天」用，前端不反推） */
  covered: Record<string, number>
  /** 分母：该有的期数 */
  periods: Record<string, number>
  /** 强度：与 coverage 同 null 规则（覆盖率算不出来时强度也为 null） */
  intensity: Record<string, number | null>
}

/** 趋势里每个维度的元信息（颜色、单位都在后端定，前端不拼） */
export interface TrendModuleMeta {
  module: string
  label: string
  color: string
  period_word: string
  intensity_label: string
  intensity_unit: string
}

/**
 * 月度「覆盖率 + 强度」两套值（v3.62.44）
 *
 * 只画覆盖率时，「记了 2 天走了 3 万步」与「记了 2 天走了 3 千步」是同一个颜色 ——
 * 强度在月度尺度上完全不可见，而「记了但记得很差」恰恰最该被看见。
 */
export interface TrendData {
  year: number
  /** 图例口径说明，由后端下发（前端不自己编） */
  unit_note: string
  modules: TrendModuleMeta[]
  months: TrendMonth[]
  /** 每维度年内最高月强度：柱高按行归一（量纲不同，无法共用一个刻度） */
  intensity_max: Record<string, number>
}

/** 雷达单轴：一套数据、两种镜片（覆盖率 / 净额对目标达成率） */
export interface RadarAxis {
  module: string
  name: string
  color: string
  coverage: number | null
  /** 🔴 可以是负数：净流出年份的达成率就是负的，不能被抬成 0% */
  achievement: number | null
  axis_max: number | null
  /** 目标换算回物理量（财富：元） */
  achievement_target: number | null
  achievement_negative: boolean
  /** 仅财富：当年净额（元） */
  net_amount: number | null
  covered: number
  periods: number
  period_word: string
  coverage_label: string
  intensity: number | null
  intensity_label: string
  intensity_unit: string
  total_display: number | null
  total_unit: string
  zero_reason?: string | null
}

export type RadarBasis = 'coverage' | 'achievement'

export interface RadarData {
  year: number
  basis_default: RadarBasis
  axes: RadarAxis[]
}

export interface ModuleDetail {
  module: string
  label: string
  color: string
  raw_value: number | null
  display_value: number | null
  points: number
  unit: string
  zero_reason?: string | null
  record_count: number
  records: Record<string, unknown>[]
}

// ── 季度决策工作台 ──────────────────────────────────────

export interface QuarterlyModuleEntry {
  module: string
  label: string
  color: string
  points: number
  raw_value: number | null
  display_value: number | null
  unit: string
  zero_reason?: string | null
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

/**
 * 总分的年度目标 / 月目标已随总分一起退役（v3.62.43）。
 * 七个不同量纲相加没有意义，且七轴封顶之和 315 < 400 ⇒ 那百分比不可达。
 * 若将来又要一个「合计」，先回答：1 本书凭什么是 1 次旅行。
 */
export const QUARTER_OPTIONS = [
  { value: 1, label: 'Q1 (1-3月)' },
  { value: 2, label: 'Q2 (4-6月)' },
  { value: 3, label: 'Q3 (7-9月)' },
  { value: 4, label: 'Q4 (10-12月)' },
]
