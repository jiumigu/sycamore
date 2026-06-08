import request from '@/shared/utils/request'

export function getFoodList(params?: Record<string, unknown>) {
  return request({ url: '/food/records/', method: 'get', params })
}

export function getFoodDetail(id: number) {
  return request({ url: `/food/records/${id}/`, method: 'get' })
}

export function createFood(data: Record<string, unknown>) {
  return request({ url: '/food/records/', method: 'post', data })
}

export function updateFood(id: number, data: Record<string, unknown>) {
  return request({ url: `/food/records/${id}/`, method: 'put', data })
}

export function deleteFood(id: number) {
  return request({ url: `/food/records/${id}/`, method: 'delete' })
}

export function getFoodStats() {
  return request({ url: '/food/records/stats/', method: 'get' })
}

export function getFoodLocations() {
  return request({ url: '/food/records/locations/', method: 'get' })
}

export function getFoodMapData() {
  return request({ url: '/food/records/map_data/', method: 'get' })
}

export function getFoodTags() {
  return request({ url: '/food/records/tags/', method: 'get' })
}

export function getFoodTrend(year?: number) {
  return request({ url: '/food/records/trend/', method: 'get', params: year ? { year } : {} })
}

export function getFoodCategories() {
  return request({ url: '/food/records/categories/', method: 'get' })
}

export function uploadFood(formData: FormData) {
  return request({
    url: '/food/upload/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getFoodTasteDistribution() {
  return request({ url: '/food/records/taste_distribution/', method: 'get' })
}
