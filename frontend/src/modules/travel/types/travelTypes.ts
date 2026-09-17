export interface TravelRecord {
  tid: number
  parentnode: string | null
  tname: string | null
  district: string | null
  tyear: number | null
  tcost: number | null
  ttime: string | null
  tremark: string | null
  duration_days: number | null
  rating: number | null
  companions: string | null
  latitude: number | null
  longitude: number | null
}

/** 地级市热力项（name 为地级市名，如「温州市」「大理州」「喀什地区」） */
export interface HeatmapItem {
  name: string
  count: number
  /** 热力档位：偶尔 / 多次 / 频繁 / 深度游 */
  level: string
  /** 计数来源明细：县级市/区县的到访会并入所属地级市（如福鼎市 → 宁德市） */
  sources?: Array<{ city: string; count: number }>
}

export interface BubbleItem {
  city: string
  province: string
  latitude: number
  longitude: number
  value: number | null
  size: number
  rating: number | null
  years: number[]
  count: number
}

export interface MapData {
  heatmap: HeatmapItem[]
  /** 地级市到访次数最大值（用于图例提示） */
  heat_max: number
  bubbles: BubbleItem[]
  total: {
    cities: number
    provinces: number
    total_cost: number
  }
}

export interface YearlyTrend {
  year: number
  count: number
  cost: number
}

export interface ProvinceDist {
  province: string
  count: number
}

export interface TravelStats {
  overview: {
    province_count: number
    city_count: number
    total_cost: number
    avg_rating: number | null
    total_days: number
    record_count: number
  }
  yearly_trend: YearlyTrend[]
  province_distribution: ProvinceDist[]
  years: number[]
}

export interface TravelFormData {
  parentnode: string
  tname: string
  district: string
  tyear: number
  ttime: string
  tcost: number | null
  duration_days: number | null
  rating: number | null
  companions: string
  tremark: string
}

export type TravelPlanItemType = 'food' | 'scenic' | 'transport' | 'hotel'

export const TRAVEL_PLAN_ITEM_TYPES: { label: string; value: TravelPlanItemType }[] = [
  { label: '🍽️ 美食', value: 'food' },
  { label: '📍 景点', value: 'scenic' },
  { label: '🚗 交通', value: 'transport' },
  { label: '🏠 住宿', value: 'hotel' },
]

export interface TravelPlanItem {
  id: number
  item_type: TravelPlanItemType
  name: string
  estimate_cost: number
  is_completed: boolean
  completed_at: string | null
  notes: string
  sort_order: number
  wish: number | null
}

export interface TravelPlan {
  id: number
  name: string
  destination: string
  start_date: string | null
  status: string
  total_estimate: number
  notes: string
  created_at: string
  updated_at: string
  items: TravelPlanItem[]
}

export interface TravelPlanItemInput {
  item_type: TravelPlanItemType
  name: string
  estimate_cost: number
}

export interface TravelPlanInput {
  name: string
  destination: string
  start_date: string | null
  status?: string
  notes?: string
  items: TravelPlanItemInput[]
}

export interface TravelPlanStats {
  total_plans: number
  total_estimate: number
  completed_plans: number
}

// ===== 旅行心愿单 =====
export type WishStatus = '想去' | '已列入计划' | '已打卡'

export interface TravelWish {
  id: number
  name: string
  category: string
  province: string
  city: string
  district: string
  lng: number | null
  lat: number | null
  status: WishStatus
  visited_at: string | null
  visit_rating: number | null
  visit_notes: string
  worth_revisit: boolean
  visit_plan: number | null
  visit_record_id: number | null
  notes: string
  created_at: string
  updated_at: string
}

export interface WishStats {
  total: number
  located: number
  by_status: Record<string, number>
  by_category: Record<string, number>
}

export interface TravelPlanOption {
  id: number
  name: string
  destination: string
  status: string
  start_date: string | null
}

// ===== 行程日志（打卡聚合视图） =====
export interface TripLogItem {
  id: number
  name: string
  category: string
  is_food: boolean
  rating: number | null
  notes: string
  worth_revisit: boolean
  consolidated: boolean
  plan_id: number | null
  lng: number | null
  lat: number | null
}

export interface TripLogRecord {
  tid: number
  tcost: number | null
  rating: number | null
  companions: string
  duration_days: number | null
  tremark: string
}

export interface TripLogDay {
  date: string
  city: string
  province: string
  district: string
  items: TripLogItem[]
  item_count: number
  summary: string
  avg_rating: number | null
  worth_count: number
  consolidated: boolean
  record: TripLogRecord | null
  plans: { id: number; name: string }[]
}

export interface TripLog {
  days: TripLogDay[]
  total_days: number
  total_items: number
  pending_days: number
}

export interface ConsolidatePayload {
  date: string
  city?: string
  tcost?: number | null
  rating?: number | null
  duration_days?: number | null
  companions?: string
  tremark?: string
}

// ===== 路线 → 计划 =====
export interface RouteWishOption {
  id: number
  name: string
  category: string
  is_food: boolean
}

export interface RouteStation {
  city: string
  wish_count: number
  wishes: RouteWishOption[]
}

export interface PlanFromRouteInput {
  name?: string
  origin?: string
  destinations: string[]
  start_date?: string | null
  wish_ids?: number[]
}
