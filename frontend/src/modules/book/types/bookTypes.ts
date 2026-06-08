export interface Book {
  bid: number
  years: string | null
  btitle: string
  author: string | null
  original_title: string | null
  btype: string | null
  btype_display?: string
  status: string | null
  status_display?: string
  recommend: number
  recommend_display?: string
  reading_depth: number
  reading_depth_display?: string
  readDate: string | null
  created_at: string | null
  updated_at: string
  tags: string | null
  abandon_reason: string | null
  closedop: string | null
  openop: string | null
  action_item?: string
  user_id?: number | null
}

export interface BookListParams {
  page?: number
  page_size?: number
  years?: string
  btype?: string
  status?: string
  recommend?: number
  recommend_min?: number
  recommend_max?: number
  reading_depth?: number
  search?: string
  ordering?: string
  tag?: string
}

export interface BookStats {
  total_count: number
  completed_count: number
  reading_count: number
  abandoned_count: number
  planned_count: number
  month_count: number
  year_count: number
  avg_recommend: number
  status_stats: Array<{ status: string; count: number }>
  type_stats: Array<{ btype: string; count: number; avg_recommend: number }>
  year_stats: Array<{ years: string; count: number }>
  recommend_stats: Array<{ recommend: number; count: number }>
  depth_stats: Array<{ reading_depth: number; count: number }>
}

export const BTYPE_OPTIONS = [
  '基础学科', '哲学智慧', '心理健康', '财富创造', '幸福科学',
  '认知提升类', '技能工具类', '文学滋养类', '休闲放松类', '个人成长类', '能量消耗类',
]

export const STATUS_OPTIONS = [
  '计划阅读', '在读', '精读', '通读', '消遣', '弃读', '已完成', '待重读',
]

export const READING_DEPTH_OPTIONS = [
  { value: 1, label: '速读浏览' },
  { value: 2, label: '重点阅读' },
  { value: 3, label: '精读细品' },
  { value: 4, label: '反复研读' },
  { value: 5, label: '践行内化' },
]

export const RECOMMEND_TEXTS = ['不推荐', '一般', '推荐', '宝藏', '人生必读']
