export interface FoodRecord {
  id: number
  name: string
  dish_name: string | null
  category: string | null
  category_display: string | null
  province: string
  city: string
  location: string | null
  latitude: number | null
  longitude: number | null
  taste_level: string
  taste_level_display: string
  eat_date: string
  eat_time: string | null
  eat_time_display: string | null
  companions: string | null
  occasion: string | null
  occasion_display: string | null
  images: string[] | null
  cover_image: string | null
  image_url: string | null
  rating: number | null
  price: string | number | null
  notes: string | null
  tags: string | null
  want_visit_again: boolean
  created_at: string
  updated_at: string
}

export interface FoodRecordList {
  id: number
  name: string
  dish_name: string | null
  category: string | null
  category_display: string | null
  city: string
  location: string | null
  taste_level: string
  taste_level_display: string
  eat_date: string
  cover_image: string | null
  image_url: string | null
  rating: number | null
  price: string | number | null
  notes: string | null
  want_visit_again: boolean
}

export interface FoodStats {
  total_records: number
  total_cities: number
  favorite_category: string | null
  favorite_category_count: number
  avg_rating: number
  want_visit_again_count: number
  this_month_count: number
}

export interface FoodLocation {
  province: string
  city: string
  count: number
}

export interface FoodMapData {
  province: string
  count: number
  cities: { city: string; count: number }[]
}

export interface TagCount {
  name: string
  count: number
}

export interface FoodFormData {
  name: string
  dish_name?: string
  category?: string
  province?: string
  city?: string
  location?: string
  latitude?: number
  longitude?: number
  taste_level: string
  eat_date: string
  images?: string[]
  cover_image?: string
  rating?: number
  price?: number
  notes?: string
  tags?: string
  want_visit_again?: boolean
}

export const CATEGORY_OPTIONS = [
  { value: 'chinese', label: '中餐', icon: '🍜' },
  { value: 'western', label: '西餐', icon: '🍕' },
  { value: 'japanese', label: '日料', icon: '🍣' },
  { value: 'dessert', label: '甜品', icon: '🍰' },
  { value: 'snack', label: '小吃', icon: '🥟' },
  { value: 'drink', label: '饮品', icon: '🧋' },
  { value: 'other', label: '其他', icon: '🍽️' },
]

export const TASTE_LEVELS: Record<string, { label: string; icon: string; color: string }> = {
  good: { label: '好吃', icon: '😋', color: '#10B981' },
  very_good: { label: '特别好吃', icon: '😍', color: '#3B82F6' },
  want_again: { label: '还想吃', icon: '🤤', color: '#F59E0B' },
  must_eat_again: { label: '一定要再吃', icon: '🔥', color: '#EF4444' },
}

export const EAT_TIME_OPTIONS = [
  { value: 'breakfast', label: '早餐', icon: '🌅' },
  { value: 'lunch', label: '午餐', icon: '☀️' },
  { value: 'dinner', label: '晚餐', icon: '🌙' },
  { value: 'snack', label: '小吃', icon: '🍪' },
]

export const OCCASION_OPTIONS = [
  { value: 'date', label: '约会', icon: '💑' },
  { value: 'gathering', label: '聚餐', icon: '👥' },
  { value: 'solo', label: '独享', icon: '🧘' },
  { value: 'travel', label: '旅游', icon: '✈️' },
  { value: 'work', label: '工作餐', icon: '💼' },
]
