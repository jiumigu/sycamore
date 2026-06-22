export interface HealthRecord {
  hid: number
  steps: number | null
  htype: number | null
  htype_label: string
  cofficient: number | null
  total: number | null
  time: string
  remark: string | null
  years: string | null
  user_id: number | null
}

export interface MilestoneInfo {
  number: number
  start: number
  end: number
  current: number
  remaining: number
  progress_in_milestone: number
}

export interface PredictionInfo {
  target_date: string
  days_remaining: number
  daily_needed: number
}

export interface HealthSummary {
  total_steps: number
  target_steps: number
  progress_percent: number
  completed_milestones: number
  total_milestones: number
  next_milestone_distance: number
  daily_avg: number
  days_active: number
  max_daily: number
  longest_streak: number
  this_month_steps: number
  current_milestone: MilestoneInfo
  prediction: PredictionInfo | null
}

export interface MilestoneItem {
  number: number
  start: number
  end: number
  is_completed: boolean
  is_current: boolean
  completed_date?: string
  days_taken?: number
  current_progress?: number
  progress_percent?: number
}

export interface MilestoneList {
  milestones: MilestoneItem[]
  total_steps: number
}

export interface DailyTrendItem {
  date: string
  total_steps: number
  record_count: number
}

export interface CalendarItem {
  date: string
  total_steps: number
  record_count: number
}

export interface MilestoneTimelineItem {
  number: number
  start: number
  end: number
  completed_date: string
  days_taken: number
  days_since_previous: number | null
}

export interface TypeStatItem {
  htype: number
  label: string
  total_steps: number
  count: number
  percentage: number
}

export interface YearlyComparisonItem {
  year: string
  total_steps: number
  count: number
  avg_daily: number
}

export const HTYPE_OPTIONS = [
  { value: 1, label: '🚶 步数' },
  { value: 2, label: '🪢 跳绳' },
  { value: 3, label: '🏃 跑步' },
  { value: 4, label: '🚴 骑行' },
]

export const HTYPE_LABELS: Record<number, string> = {
  1: '🚶 步数', 2: '🪢 跳绳', 3: '🏃 跑步', 4: '🚴 骑行',
}

export const HTYPE_LABELS_SHORT: Record<number, string> = {
  1: '步数', 2: '跳绳', 3: '跑步', 4: '骑行',
}

export const MILESTONE_SIZE = 2_000_000
export const TARGET_STEPS = 100_000_000
export const TOTAL_MILESTONES = 50

// ─── 体重管理 ───

export interface WeightRecord {
  id: number
  record_date: string
  weight_kg: string
  weight_jin: number
  bmi: number | null
  body_fat: string | null
  measure_time: string | null
  notes: string | null
  user_id: number
  created_at: string
  updated_at: string
}

export interface WeightGoal {
  id: number
  user_id: number
  target_weight_kg: string
  target_weight_jin: number
  start_weight_kg: string
  start_weight_jin: number
  monthly_target_kg: string
  monthly_target_jin: number
  start_date: string
  expected_end_date: string | null
  status: string
  current_month: number
  current_month_start_weight: string | null
  current_month_target: string | null
  is_active: boolean
  completed_at: string | null
}

export interface WeightMilestone {
  id: number
  month_number: number
  start_weight_kg: string
  target_weight_kg: string
  end_weight_kg: string | null
  is_achieved: boolean
  achieved_at: string | null
  goal: number
}

export interface WeightStats {
  current_weight_kg: number | null
  current_weight_jin: number | null
  target_weight_kg: number | null
  target_weight_jin: number | null
  total_lost_kg: number | null
  total_lost_jin: number | null
  remaining_kg: number | null
  remaining_jin: number | null
  overall_progress: number
  monthly_lost_kg: number | null
  monthly_lost_jin: number | null
  monthly_target_jin: number | null
  monthly_target_kg: number | null
  monthly_progress: number
  bmi: number | null
  bmi_status: string | null
  remaining_days: number
}

export interface WeightTrend {
  records: WeightTrendItem[]
  milestones: WeightTrendMilestone[]
  target_weight_kg: number | null
}

export interface WeightTrendItem {
  date: string
  weight_kg: number
  weight_jin: number
  body_fat: number | null
}

export interface WeightTrendMilestone {
  month: number
  target_weight_kg: number
  start_weight_kg: number
  end_weight_kg: number | null
  is_achieved: boolean
}

export interface UserBodyInfo {
  id: number
  user_id: number
  height_cm: string
  height_m: number
  gender: string | null
  age: number | null
}

export const MEASURE_TIME_OPTIONS = [
  { value: 'morning', label: '早晨' },
  { value: 'afternoon', label: '下午' },
  { value: 'evening', label: '晚上' },
]

export const BMI_RANGES = [
  { max: 18.5, label: '偏瘦', color: '#3B82F6', advice: '适当增重' },
  { max: 24, label: '正常', color: '#10B981', advice: '保持' },
  { max: 28, label: '超重', color: '#F59E0B', advice: '注意控制' },
  { max: Infinity, label: '肥胖', color: '#EF4444', advice: '需减重' },
]

// ─── 好朋友跟踪 ───

export interface MenstrualRecord {
  id: number
  user_id: number
  year: number
  month: string
  start_date: string
  offset: number
  cycle_days: number
  notes: string
  created_at: string
}

export interface MenstrualStats {
  total_records: number
  avg_cycle: number
  avg_offset: number
  predicted_next: string | null
  min_cycle: number
  max_cycle: number
}

export interface MenstrualTrendItem {
  date: string
  cycle_days: number
}
