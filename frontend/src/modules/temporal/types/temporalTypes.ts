export type OneDayOType =
  | 'MIGU' | 'HAPPY' | 'SAD' | 'DIGITAL'
  | 'SUMMARY' | 'ONEDAY' | 'IDEA' | 'ACHIEVE'

export interface OneDayPage {
  oid: number
  years: string | null
  oneday: number | null
  page: number | null
  total: number | null
  title: string
  begin_date: string
  otype: OneDayOType
  otype_display: string
  update_date: string
  flag: string | null
  remark: string | null
  user_id: number | null
  created_at: string
  logseq_file: string | null
}

export interface OneDayPageStats {
  total_count: number
  month_count: number
  total_oneday: number
  total_page: number
  total_words: number
  avg_words: number
  type_stats: Array<{
    otype: string
    count: number
    total_oneday: number
    total_page: number
    total_words: number
    avg_words: number
  }>
}

export const OTYPE_OPTIONS = [
  { value: 'MIGU', label: '迷谷知松', type: 'success' as const },
  { value: 'HAPPY', label: '有点开心', type: 'warning' as const },
  { value: 'SAD', label: '有点闹心', type: 'danger' as const },
  { value: 'DIGITAL', label: '数字转型', type: 'info' as const },
  { value: 'SUMMARY', label: '复盘总结', type: '' as const },
  { value: 'ONEDAY', label: '普通一日', type: '' as const },
  { value: 'IDEA', label: '有点想法', type: 'info' as const },
  { value: 'ACHIEVE', label: '有点成就', type: 'success' as const },
]

// ─── 任务时间追踪类型 ───

export interface TemporalTask {
  id: number
  task_name: string
  task_description: string
  start_time: string | null
  end_time: string | null
  duration: string | null
  duration_hours: number | null
  notes: string
  tags: string
  task_type: string
  year: number | null
  mon: string | null
  day: number | null
  week: number | null
  quarter: number | null
  category_level1: string | null
  category_level2: string | null
  category_color: string | null
  import_batch: string | null
  updated_at: string
  category_icon: string
  duration_display: string
  date: string
  // v0.3 解析字段（L1 归因 / L2 活动类型 / 是否未归类）
  activity_type?: string | null
  attribution?: string | null
  is_unclassified?: boolean
}

export interface TaskOverview {
  total_hours: number
  total_records: number
  active_days: number
  production_percentage?: number
  category_breakdown?: Record<string, number>
  // v0.3：L1 归因 / L2 活动类型 聚合 + 完整度
  attribution_breakdown: Record<string, number>
  activity_breakdown: Record<string, number>
  completeness: CompletenessData
}

// ─── 三层分类（自顶向下：L1 归因 / L2 活动类型 / L3 task_name）───

export interface TaskMeta {
  id: number
  task_name: string
  activity_type: string
  default_attribution: string | null
  is_system: boolean
  note: string | null
}

export interface UnclassifiedItem {
  task_name: string
  total_hours: number
  record_count: number
}

// 旭日 3 环：L1 归因 → L2 类型 → L3 task_name
export interface SunburstLeaf {
  name: string
  hours: number
}

export interface SunburstChild {
  name: string
  hours: number
  color?: string | null
  children: SunburstLeaf[]
}

export interface SunburstGroup {
  name: string
  hours: number
  color: string | null
  children: SunburstChild[]
}

export interface SunburstData {
  groups: SunburstGroup[]
}

export interface CompletenessData {
  total_hours: number
  classified_hours: number
  completeness: number
  days_recorded: number
  denominator_hours_per_day: number
}

export interface WeeklyStructureWeek {
  year: number
  week: number
  by_l1: Record<string, number>
  by_l2: Record<string, number>
  by_l3: Record<string, number>
  redemption_4color: Record<string, number>
  completeness: number
}

export interface WeeklyStructure {
  weeks: WeeklyStructureWeek[]
}

export type AttributionType = '投向' | '维持' | '外部' | '流失'
export type ActivityType =
  | '睡眠' | '维护性事务' | '深度工作' | '浅层工作' | '主动休息'
  | '被动消耗' | '社交' | '兴趣记录' | '未归类'

export const ATTRIBUTION_OPTIONS: AttributionType[] = ['投向', '维持', '外部', '流失']
export const ACTIVITY_TYPE_OPTIONS: ActivityType[] = [
  '深度工作', '浅层工作', '主动休息', '被动消耗', '睡眠',
  '维护性事务', '社交', '兴趣记录', '未归类',
]
export const ACTIVITY_TYPE_COLOR_MAP: Record<string, string> = {
  '睡眠': '#64748B', '维护性事务': '#94A3B8', '深度工作': '#6366F1',
  '浅层工作': '#0EA5E9', '主动休息': '#10B981', '被动消耗': '#F87171',
  '社交': '#A855F7', '兴趣记录': '#EC4899', '未归类': '#CBD5E1',
}
export const ATTRIBUTION_COLOR_MAP: Record<string, string> = {
  '投向': '#10B981', '维持': '#6366F1', '外部': '#0EA5E9', '流失': '#F87171',
}

export interface TrendItem {
  period: string
  [category: string]: string | number
}

export interface BalanceCategory {
  name: string
  hours: number
  percentage: number
  color: string
}

export interface BalanceData {
  total_hours: number
  categories: BalanceCategory[]
}

export interface RankingItem {
  task_name: string
  category: string
  color: string
  total_hours: number
  record_count: number
}

export interface DistributionData {
  morning: number
  afternoon: number
  evening: number
  morning_pct: number
  afternoon_pct: number
  evening_pct: number
}

export interface CalendarDay {
  date: string
  hours: number
  count: number
}

export interface ImportResult {
  inserted: number
  updated: number
  skipped: number
  error?: string
}

export const CATEGORY_MAP: Record<string, { color: string; icon: string }> = {
  '工作': { color: '#EF4444', icon: '💼' },
  '学习': { color: '#10B981', icon: '📖' },
  '生活': { color: '#F59E0B', icon: '🏠' },
  '兴趣记录': { color: '#3B82F6', icon: '🎨' },
}
