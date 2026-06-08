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
  year_stats: Array<{
    years: string
    count: number
    total_oneday: number
    total_page: number
    total_words: number
    avg_words: number
  }>
  month_stats: Array<{
    month: string
    count: number
    total_oneday: number
    total_page: number
    total_words: number
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
}

export interface TaskOverview {
  total_hours: number
  total_records: number
  active_days: number
  production_percentage: number
  category_breakdown: Record<string, number>
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
  '生产与创造': { color: '#10B981', icon: '💡' },
  '维护与秩序': { color: '#9CA3AF', icon: '🔧' },
  '滋养与成长': { color: '#F59E0B', icon: '🌱' },
  '连接与记录': { color: '#3B82F6', icon: '📝' },
}
