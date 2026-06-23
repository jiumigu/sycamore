export type GoalPriority = 'p0' | 'p1' | 'p2' | 'p3'

export type GoalStatus = 'planning' | 'in-progress' | 'paused' | 'completed' | 'abandoned' | 'archived'

export type GoalCategory = 'year' | 'quarter' | 'month' | 'long-term'

export type MilestoneStatus = 'pending' | 'in-progress' | 'completed'

export type ReviewType = 'weekly' | 'monthly' | 'milestone'

export interface Milestone {
  id: number
  goal: number
  title: string
  status: MilestoneStatus
  status_display?: string
  completed_note: string | null
  self_review?: string
  description?: string
  order_num: number
  target_date: string | null
  target_value: number | null
  actual_value: number | null
  reward_amount: number | null
  reward_amount_display?: number
  reward_synced: boolean
  reward_issued_at: string | null
  reward_transaction_id: number | null
  created_at: string
  updated_at: string
}

export interface Action {
  id: number
  goal: number
  goal_title: string | null
  milestone: number | null
  milestone_title: string | null
  name: string
  note: string | null
  action_date: string | null
  created_at: string
  updated_at: string
}

export interface GoalReview {
  id: number
  goal: number
  review_type: ReviewType
  review_type_display?: string
  review_date: string
  score: number | null
  what_worked: string
  what_blocked: string
  next_adjustment: string
  content: string
  progress_note: string | null
  created_at: string
}

export interface CheckinStreak {
  current: number
  longest: number
  total: number
}

export interface RewardMilestone {
  id: number
  title: string
  reward_amount: number
  status: string
  order_num: number
}

export interface CheckinMilestone {
  id: number
  title: string
  status: string
  reward_amount: number
  description: string
  completed_note: string
  self_review: string
  target_date: string | null
  order_num: number
}

export interface CheckinStats {
  streak: CheckinStreak
  total_milestones: number
  completed_milestones: number
  progress_percentage: number
  calendar: Record<string, boolean>
  reward_milestones: RewardMilestone[]
  milestones: CheckinMilestone[]
}

export interface Goal {
  id: number
  title: string
  description: string | null
  category: GoalCategory
  category_display?: string
  tags: string[] | null
  action_count?: number
  milestone_count?: number
  is_tracking_mode?: boolean
  priority: GoalPriority
  priority_display?: string
  status: GoalStatus
  status_display?: string
  progress_percentage: number
  start_date: string | null
  deadline: string | null
  year: number | null
  notes: string | null
  reward_value: number
  enable_reward: boolean
  default_reward_amount: number
  total_reward_issued: number
  user_id: number | null
  decision_quality?: number | null
  mental_models_used?: string | null
  inversion_check?: string | null
  first_principles?: string | null
  circle_check?: number | null
  happiness_impact?: number | null
  peace_impact?: number | null
  milestones?: Milestone[]
  actions?: Action[]
  reviews?: GoalReview[]
  created_at: string
  updated_at: string
}

export interface GoalListParams {
  page?: number
  page_size?: number
  year?: number
  category?: string
  status?: string
  priority?: string
  tag?: string
  search?: string
  ordering?: string
}

export interface GoalStats {
  total_goals: number
  completed_goals: number
  in_progress_goals: number
  overdue_goals: number
  avg_progress: number
  by_category: Record<string, number>
  by_priority: Record<string, number>
  by_status: Record<string, number>
  by_year: Record<string, { count: number; avg_progress: number }>
  popular_tags: Array<{ name: string; count: number }>
}

export const CATEGORY_OPTIONS = [
  { value: 'year', label: '年度目标' },
  { value: 'quarter', label: '季度目标' },
  { value: 'month', label: '月度目标' },
  { value: 'long-term', label: '长期目标' },
]

export const PRIORITY_OPTIONS = [
  { value: 'p0', label: 'P0 - 紧急重要', type: 'danger' as const },
  { value: 'p1', label: 'P1 - 重要', type: 'warning' as const },
  { value: 'p2', label: 'P2 - 一般', type: 'info' as const },
  { value: 'p3', label: 'P3 - 低优先级', type: 'default' as const },
]

export const STATUS_OPTIONS = [
  { value: 'planning', label: '计划中', type: 'info' as const },
  { value: 'in-progress', label: '进行中', type: 'primary' as const },
  { value: 'paused', label: '已暂停', type: 'warning' as const },
  { value: 'completed', label: '已完成', type: 'success' as const },
  { value: 'abandoned', label: '已放弃', type: 'info' as const },
  { value: 'archived', label: '已归档', type: 'default' as const },
]

export const COMMON_TAGS = [
  '职业发展', '学习成长', '个人兴趣', '人生项目', '健康生活',
  '财务规划', '人际关系', '技能提升', '习惯养成', '创作产出',
]
