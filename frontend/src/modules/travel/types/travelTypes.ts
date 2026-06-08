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
