export interface DamsFileResource {
  id: number
  name: string
  path: string
  storage_location: string
  file_category: string
  file_category_label: string
  file_size_mb: number
  access_count: number
  last_accessed_at: string | null
  folder_depth: number
  parent_folder: string
  is_duplicate: boolean
  is_organized: boolean
  user_id: number
  created_at: string
  updated_at: string
}

export interface DamsFileResourceList {
  id: number
  name: string
  path: string
  file_category: string
  file_category_label: string
  file_size_mb: number
  access_count: number
  last_accessed_at: string | null
  is_duplicate: boolean
  is_organized: boolean
}

export interface DamsAccessLog {
  id: number
  file: number
  file_name: string
  accessed_at: string
  user_id: number
  created_at: string
}

export interface AttentionZone {
  label: string
  color: string
  count: number
  file_ids: number[]
}

export interface AttentionMapData {
  red: AttentionZone
  blue: AttentionZone
  green: AttentionZone
  gray: AttentionZone
  total: number
}

export const FILE_CATEGORY_OPTIONS = [
  { value: 'document', label: '文档' },
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' },
  { value: 'audio', label: '音频' },
  { value: 'archive', label: '压缩包' },
  { value: 'code', label: '代码' },
  { value: 'executable', label: '可执行文件' },
  { value: 'other', label: '其他' },
]

export const ATTENTION_ZONE_CONFIG: Record<string, { label: string; color: string }> = {
  red: { label: '高频混乱 — 需整理', color: '#EF4444' },
  blue: { label: '低频有序 — 可归档', color: '#3B82F6' },
  green: { label: '正常有序 — 健康态', color: '#10B981' },
  gray: { label: '未访问/未分类', color: '#9CA3AF' },
}
