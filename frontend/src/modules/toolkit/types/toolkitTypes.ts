export interface ToolDefinition {
  tool_key: string
  name: string
  description: string
  icon: string
  category: string
  input_schema: ToolSchema
  output_type: string
  is_async: boolean
  timeout_seconds: number
}

export interface ToolSchema {
  type: string
  properties: Record<string, SchemaProperty>
  required?: string[]
  oneOf?: Record<string, string[]>[]
}

export interface SchemaProperty {
  type: string
  description?: string
  default?: unknown
  minimum?: number
  maximum?: number
  enum?: string[]
  items?: { type: string }
}

export interface CategoryInfo {
  key: string
  label: string
  count: number
}

export interface ToolResult {
  success: boolean
  output_file?: string
  output_text?: string
  filename?: string
  preview?: string
  stats?: Record<string, unknown>
}

export interface ExecutionRecord {
  id: number
  tool_id: number
  tool_name: string
  tool_icon: string
  task_id: string
  status: ExecutionStatus
  progress: number
  error_message: string
  output_file: string | null
  execution_time_ms: number | null
  created_at: string
  completed_at: string | null
}

export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'

export const CATEGORY_LABELS: Record<string, string> = {
  image: '图片处理',
  text: '文本处理',
  file: '文件转换',
  convert: '格式转换',
  other: '其他',
}

export const STATUS_CONFIG: Record<ExecutionStatus, { label: string; type: string; color: string }> = {
  pending: { label: '等待中', type: 'info', color: '#9CA3AF' },
  running: { label: '执行中', type: 'warning', color: '#F59E0B' },
  success: { label: '成功', type: 'success', color: '#10B981' },
  failed: { label: '失败', type: 'danger', color: '#EF4444' },
  cancelled: { label: '已取消', type: 'info', color: '#6B7280' },
}

export interface CityCoordinate {
  id: number
  name: string
  full_name: string
  province: string
  lng: number
  lat: number
  city_type: string
  pinyin: string
}

export interface TravelRoutePreset {
  id: number
  name: string
  origin: string
  destinations: string[]
  description: string
  created_at: string
  updated_at: string
}

export interface HourlyWageRecord {
  id: number
  user_id: number
  name: string
  monthly_salary: string
  rest_type: string
  work_start: string
  work_end: string
  lunch_break: number
  commute_minutes: number
  calc_mode: string
  freelance_time_mode: string
  freelance_days: number | null
  freelance_hours_per_day: number | null
  weekly_hours: number[]
  freelance_weeks: number
  work_days_per_month: string
  work_hours_per_day: string
  total_hours_per_month: string
  hourly_wage: string
  notes: string
  created_at: string
}

export interface FreeSpendingRecord {
  id: number
  user_id: number
  liquid_assets: string
  annual_income: string
  debt: string
  work_years: number
  free_amount: string
  notes: string
  created_at: string
}
