export interface DanceRecord {
  id: number
  study_time: string
  score: number
  teacher_name: string | null
  dance_type: string
  difficulty: string
  weekinfo: string | null
  remark: string | null
  file_path: string | null
  year: number | null
  month: number | null
  quarter: number | null
  duration_minutes: number
  energy_level: number | null
  improvement_note: string | null
  type_icon: string
  weekinfo_label: string | null
}

export interface DanceOverview {
  total_count: number
  total_teachers: number
  total_types: number
  avg_score: number
  max_score: number
  this_month_count: number
  last_month_count: number
  monthly_change: number
  favorite_teacher: string
  favorite_teacher_count: number
  most_type: string
  most_type_count: number
}

export interface MonthlyTrend {
  month: number
  count: number
  avg_score: number
}

export interface TrendData {
  monthly: MonthlyTrend[]
  trend: 'increasing' | 'decreasing' | 'stable'
}

export interface TeacherStat {
  name: string
  count: number
  avg_score: number
  avg_energy: number
}

export interface DanceTypeStat {
  name: string
  count: number
  avg_score: number
}

export interface ScoreTrendItem {
  period: string
  avg_score: number
  count: number
}

export interface CalendarItem {
  date: string
  dance_type: string
  score: number
  teacher: string | null
  difficulty: string
}

export const DANCE_TYPE_OPTIONS = [
  { value: 'jazz', label: 'Jazz', icon: '💃', color: '#F472B6' },
  { value: 'hiphop', label: 'Hiphop', icon: '🕺', color: '#FBBF24' },
  { value: '古典', label: '古典', icon: '🦢', color: '#A78BFA' },
  { value: '身体开发', label: '身体开发', icon: '🧘', color: '#34D399' },
  { value: 'MV', label: 'MV', icon: '🎵', color: '#F87171' },
  { value: '形体软开', label: '形体软开', icon: '🤸', color: '#60A5FA' },
]

export const DIFFICULTY_OPTIONS = [
  { value: '入门', label: '入门', color: '#34D399' },
  { value: '入门小班', label: '入门小班', color: '#60A5FA' },
  { value: '二星', label: '二星', color: '#FBBF24' },
  { value: '进阶', label: '进阶', color: '#F87171' },
]

export const SCORE_LABELS: Record<number, string> = {
  1: '还需努力', 2: '初学', 3: '掌握', 4: '熟练', 5: '良好',
  6: '优秀', 7: '很棒', 8: '杰出', 9: '大师', 10: '完美',
}
