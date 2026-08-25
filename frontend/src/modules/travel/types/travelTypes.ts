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

export interface HeatmapItem {
  province: string
  count: number
  intensity: number
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
