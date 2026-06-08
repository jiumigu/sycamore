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

export interface DifficultyStat {
  total: number
  good: number
  yield_rate: number
}

export interface MonthlyTrend {
  month: string
  total: number
  yield_rate: number
}

export interface OutputStats {
  total_records: number
  good_count: number
  defective_count: number
  waste_count: number
  yield_rate: number
  defect_rate: number
  waste_rate: number
  by_category: Record<string, CategoryStat>
  by_difficulty: Record<string, DifficultyStat>
  monthly_trend: MonthlyTrend[]
}

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
