export interface OutputRecord {
  id: number
  title: string
  category: string
  category_display: string
  expected_result: string
  actual_result: string
  quality: string
  quality_display: string
  difficulty: number
  difficulty_display: string
  fail_reason: string
  fail_type: string
  fail_type_display: string
  lesson_learned: string
  occurred_at: string | null
  created_at: string
  updated_at: string
}

export interface CategoryStat {
  label: string
  total: number
  good: number
  yield_rate: number
}

/** 失败类型分布一项（只统计「没达到预期」的记录） */
export interface FailTypeStat {
  value: string
  label: string
  count: number
}

export interface MonthlyTrend {
  month: string
  total: number
  yield_rate: number
}

export interface OutputStats {
  /** 统计窗口键：30d / 90d / year / all（口径由后端翻译，前端只传 key） */
  window: OutputWindow
  total_records: number
  good_count: number
  defective_count: number
  waste_count: number
  /** 没达到预期 = 不良品 + 废品；它才是「该复盘的那几件」 */
  redo_count: number
  yield_rate: number
  defect_rate: number
  waste_rate: number
  /** 样本门槛：低于它就只报件数、不报比例 */
  min_sample: number
  sample_enough: boolean
  by_category: Record<string, CategoryStat>
  by_fail_type: FailTypeStat[]
  top_fail_type: FailTypeStat | null
  fail_type_missing: number
  /** 全库里未填发生日期的条数（进不了任何按日期过滤的口径，界面要如实说明） */
  undated_count: number
  monthly_trend: MonthlyTrend[]
}

export type OutputWindow = '30d' | '90d' | 'year' | 'all'

/**
 * 窗口选项。
 * ⚠️ 这里只放「按钮文字 + key」；key 对应的日期边界**只在后端**有一份
 *    （`OutputRecordViewSet.WINDOW_DAYS`），前端不自己算边界。
 */
export const WINDOW_OPTIONS: Array<{ value: OutputWindow; label: string }> = [
  { value: '30d', label: '近 30 天' },
  { value: '90d', label: '近 90 天' },
  { value: 'year', label: '今年' },
  { value: 'all', label: '全部' },
]

export const CATEGORY_OPTIONS = [
  { value: 'work', label: '工作' },
  { value: 'writing', label: '写作' },
  { value: 'social', label: '社交' },
  { value: 'study', label: '学习' },
  { value: 'health', label: '健康' },
  { value: 'life', label: '生活' },
  { value: 'other', label: '其他' },
] as const

export const QUALITY_OPTIONS = [
  { value: 'good', label: '良品', color: '#10B981' },
  { value: 'defective', label: '不良品', color: '#F59E0B' },
  { value: 'waste', label: '废品', color: '#EF4444' },
] as const

export const FAIL_TYPE_OPTIONS = [
  { value: 'cognitive', label: '认知盲区' },
  { value: 'ability', label: '能力不足' },
  { value: 'external', label: '外部因素' },
  { value: 'luck', label: '运气' },
  { value: 'careless', label: '粗心' },
  { value: 'other', label: '其他' },
] as const
