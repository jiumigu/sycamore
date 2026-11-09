export interface SugarRecord {
  s_id: number
  years: number | null
  month: number | null
  title: string
  level_of_happiness: number
  time: string
  category: string | null
  category_display?: string | null
  tags: string | null
  joy_type: string
  notes: string | null
  reward_amount: number
  reward_synced: boolean
  reward_label?: string
  /** 档位配色，由后端随记录下发（前端不按分数自己算 —— 那是第二份档位边界） */
  reward_color?: string
  created_at: string
  updated_at: string
}

export interface SugarListParams {
  year?: number
  month?: number
  category?: string
  joy_type?: string
  min_happiness?: number
  search?: string
  ordering?: string
}

export interface SugarCategoryStats {
  category: string
  count: number
  total_reward: number
}

export const CATEGORY_OPTIONS = [
  { value: 'food', label: '美食', icon: '🍜' },
  { value: 'travel', label: '旅行', icon: '✈️' },
  { value: 'learn', label: '学习', icon: '📚' },
  { value: 'social', label: '社交', icon: '💬' },
  { value: 'leisure', label: '休闲', icon: '🎮' },
  { value: 'work', label: '工作', icon: '💼' },
  { value: 'health', label: '健康', icon: '🏃' },
  { value: 'other', label: '其他', icon: '💭' },
]

// ─── 快乐程度档位（唯一下发口：GET /sugar/records/happiness_bands/） ───
//
// 🔴 这里**只有类型与查表函数，没有档位边界数字**。
// 边界与词表在 `apps/sugar/constants.py`（后端唯一真源），随接口下发。
// 曾经前端抄过四份（本文件一个 REWARD_LABELS、卡片里一份配色一份表情、弹窗里一份词表），
// 结果同一分数在弹窗说「非常开心」、在列表说「很高兴」—— 所以全部删掉，改成查表。

export interface SugarHappinessBand {
  /** 这一档的上界（含） */
  max_level: number
  label: string
  color: string
}

export interface SugarHappinessBands {
  min: number
  max: number
  bands: SugarHappinessBand[]
}

/** 取该分数所在的档位；**没取到表就返回 null**（不猜、不回落硬编码档位）。 */
export function happinessBandOf(
  meta: SugarHappinessBands | null,
  level: number | null | undefined,
): SugarHappinessBand | null {
  if (!meta || level === null || level === undefined) return null
  const value = Number(level)
  if (Number.isNaN(value)) return null
  // 与服务端 `resolve_happiness_band` 同一套判据：第一个 `max_level >= 分数` 的档
  return meta.bands.find(b => value <= b.max_level) ?? null
}

/** 档位词；取不到表时返回空串 —— 宁可只说分数，也不要编一个词出来 */
export function happinessLabelOf(
  meta: SugarHappinessBands | null,
  level: number | null | undefined,
): string {
  return happinessBandOf(meta, level)?.label ?? ''
}

// ─── 能量清单 ───

export interface EnergyTemplate {
  id: number
  content: string
  default_energy: number
  category: string
  category_label: string
  icon: string
  estimated_seconds: number
  estimated_minutes: number
  is_system: boolean
  is_active: boolean
  sort_order: number
}

export interface EnergyLog {
  id: number
  template: number | null
  template_icon: string
  content: string
  energy_gained: number
  is_custom: boolean
  completed_at: string
  reward_processed: boolean
  created_at: string
}

export interface EnergyStats {
  today: { total_energy: number; completed_count: number }
  week: { total_energy: number; completed_count: number }
  month: { total_energy: number; completed_count: number }
  streak: { current: number; longest: number }
}

export interface EnergyTrendPoint {
  date: string
  total_energy: number
}

// ─── 小确幸模板 ───

export interface SugarTemplate {
  id: number
  user_id: number
  category: string
  category_display: string
  name: string
  icon: string
  points: number
  duration: string
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export const SUGAR_TEMPLATE_CATEGORIES: Record<string, { label: string; icon: string }> = {
  daily: { label: '日常', icon: '🌱' },
  creative: { label: '创意', icon: '✨' },
  social: { label: '社交', icon: '💬' },
  relax: { label: '放松', icon: '🧘' },
}

export const ENERGY_CATEGORY_CONFIG: Record<string, { label: string; icon: string }> = {
  daily: { label: '日常', icon: '🌱' },
  creative: { label: '创意', icon: '✨' },
  social: { label: '社交', icon: '💬' },
  relax: { label: '放松', icon: '🧘' },
}

// ─── 快乐类型 ───

export interface JoyTypeStat {
  joy_type: string
  count: number
  percentage: number
  total_happiness: number
  avg_happiness: number
}

export interface JoyTypeStats {
  joy_types: JoyTypeStat[]
  total: number
}

export const JOY_TYPE_OPTIONS = [
  { value: '感官型', label: '感官型 — 五感满足', icon: '🌿' },
  { value: '秩序型', label: '秩序型 — 掌控感', icon: '📋' },
  { value: '联结型', label: '联结型 — 关系满足', icon: '💬' },
  { value: '意外型', label: '意外型 — 惊喜感', icon: '🎁' },
  { value: '独处型', label: '独处型 — 内在空间', icon: '🧘' },
]

/**
 * 筛选下拉的选项 —— 由 `GET /sugar/records/joy_types/` 下发，前端零副本。
 *
 * 🔴 这里**不是** `JOY_TYPE_OPTIONS`：后者是录入表单的五个标准型；
 *    筛选还得覆盖库里那些不在词表内的旧值（社交/其他/创造）与「未标注」，
 *    否则那几条记录永远筛不出来。谁在筛选下拉里直接 v-for 上面那个常量，
 *    就等于把「漏数」写死在页面里。
 */
export interface JoyTypeOption {
  /** 筛选用值：标准/旧词是类型名，未标注是后端下发的哨兵（**不是空串**） */
  value: string
  label: string
  /** 按当前 年/月/分类 统计的条数；不随 `joy_type` 自身的选择变化 */
  count: number
  kind: 'standard' | 'legacy' | 'unlabeled'
}

export interface JoyTypeOptions {
  /** 「未标注」对应的请求值 —— 用它跟 `undefined`（= 没筛选）区分开 */
  unlabeled_value: string
  options: JoyTypeOption[]
}

export const JOY_TYPE_COLORS: Record<string, string> = {
  '感官型': '#10B981',
  '秩序型': '#3B82F6',
  '联结型': '#EF4444',
  '意外型': '#F59E0B',
  '独处型': '#8B5CF6',
}
