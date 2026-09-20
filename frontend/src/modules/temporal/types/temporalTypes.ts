export type OneDayOType =
  | 'MIGU' | 'HAPPY' | 'SAD' | 'DIGITAL'
  | 'SUMMARY' | 'ONEDAY' | 'IDEA' | 'ACHIEVE'

export interface OneDayPage {
  oid: number
  years: string | null
  oneday: number | null
  page: number | null
  total: number | null
  title: string
  begin_date: string
  otype: OneDayOType
  otype_display: string
  update_date: string
  flag: string | null
  remark: string | null
  user_id: number | null
  created_at: string
  logseq_file: string | null
}

export interface OneDayPageStats {
  total_count: number
  month_count: number
  total_oneday: number
  total_page: number
  total_words: number
  avg_words: number
  type_stats: Array<{
    otype: string
    count: number
    total_oneday: number
    total_page: number
    total_words: number
    avg_words: number
  }>
}

export const OTYPE_OPTIONS = [
  { value: 'MIGU', label: '迷谷知松', type: 'success' as const },
  { value: 'HAPPY', label: '有点开心', type: 'warning' as const },
  { value: 'SAD', label: '有点闹心', type: 'danger' as const },
  { value: 'DIGITAL', label: '数字转型', type: 'info' as const },
  { value: 'SUMMARY', label: '复盘总结', type: '' as const },
  { value: 'ONEDAY', label: '普通一日', type: '' as const },
  { value: 'IDEA', label: '有点想法', type: 'info' as const },
  { value: 'ACHIEVE', label: '有点成就', type: 'success' as const },
]

// ─── 任务时间追踪类型 ───

export interface TemporalTask {
  id: number
  task_name: string
  task_description: string
  start_time: string | null
  end_time: string | null
  duration: string | null
  duration_hours: number | null
  notes: string
  tags: string
  task_type: string
  year: number | null
  mon: string | null
  day: number | null
  week: number | null
  quarter: number | null
  category_level1: string | null
  category_level2: string | null
  category_color: string | null
  import_batch: string | null
  updated_at: string
  category_icon: string
  duration_display: string
  date: string
  // v0.3 解析字段（L1 归因 / L2 活动类型 / 是否未归类）
  activity_type?: string | null
  attribution?: string | null
  is_unclassified?: boolean
}

export interface TaskOverview {
  total_hours: number
  total_records: number
  active_days: number
  production_percentage?: number
  category_breakdown?: Record<string, number>
  // v0.3：L1 归因 / L2 活动类型 聚合 + 完整度
  attribution_breakdown: Record<string, number>
  activity_breakdown: Record<string, number>
  completeness: CompletenessData
}

// ─── 三层分类（自顶向下：L1 归因 / L2 活动类型 / L3 task_name）───

export interface TaskMeta {
  id: number
  task_name: string
  activity_type: string
  default_attribution: string | null
  is_system: boolean
  note: string | null
}

export interface UnclassifiedItem {
  task_name: string
  total_hours: number
  record_count: number
}

// ─── 分类台账（映射编辑器主体：全量 task_name + 真实使用量）───

export type AttributionSource = 'rule' | 'default' | 'fallback'

/** 归因规则的匹配维度（与后端 `RedemptionAttrRule.MATCH_FIELD_CHOICES` 一一对应） */
export type AttrRuleField = 'task_name' | 'activity_type' | 'task_type'

/** 维度中文名：台账提示「这条归因来自哪条规则」时用，口径与赎回期页面保持一致 */
export const RULE_FIELD_LABEL: Record<AttrRuleField, string> = {
  task_name: '任务名',
  activity_type: '活动类型(L2)',
  task_type: '任务类型',
}

/** 只有按任务名的规则能被台账单行撤销；其余维度会波及其他任务名 */
export function ruleIsRowScoped(field: AttrRuleField | null | undefined): boolean {
  return field === 'task_name'
}

export interface MetaLedgerItem {
  task_name: string
  activity_type: string
  /** TaskMeta 上存的默认归因（可能为空） */
  default_attribution: string | null
  /** 实际生效归因：规则 > 默认 > 兜底 */
  effective_attribution: string | null
  attribution_source: AttributionSource | null
  /**
   * 命中的归因规则（仅 source='rule' 时有值，其余恒为 null）
   *
   * ⚠️ `rule_field` 决定「撤销覆盖」能不能撤：只有 `task_name` 维度可撤；
   * `activity_type`(L2) / `task_type` 规则同时覆盖同一维度下的**其他**任务名，
   * 单行撤销会连坐，须到赎回期「归因规则」页停用。
   */
  rule_id: number | null
  rule_field: AttrRuleField | null
  rule_value: string | null
  is_unclassified: boolean
  is_system: boolean
  total_hours: number
  record_count: number
  /** 单次均时（分钟） */
  avg_minutes: number
  last_used: string | null
}

export interface MetaLedgerSummary {
  total: number
  classified: number
  unclassified: number
  total_hours: number
  unclassified_hours: number
  by_attribution: Record<string, number>
}

export interface MetaLedgerData {
  summary: MetaLedgerSummary
  returned: number
  items: MetaLedgerItem[]
}

/** 台账「来源」列：口径与后端 resolve_attribution_detail 一致 */
export const ATTR_SOURCE_MAP: Record<AttributionSource, { label: string; color: string; tip: string }> = {
  rule: { label: '赎回期规则', color: '#6366F1', tip: '由三年赎回期归因规则覆盖（优先级最高）。按任务名的规则可在本页撤销；按活动类型(L2)/任务类型的规则会覆盖同一维度下多个任务名，需到赎回期页停用' },
  default: { label: '类型默认', color: '#94A3B8', tip: '取自该任务名的默认归因' },
  fallback: { label: '兜底', color: '#CBD5E1', tip: '未设默认归因，兜底为「成长」；改 L2 类型不会顺手改归因' },
}

/** 台账 L1 下拉的「清除覆盖」哨兵值（不落库，仅前端语义） */
export const ATTR_CLEAR = '__clear__'

// 旭日 3 环：L1 归因 → L2 类型 → L3 task_name
export interface SunburstLeaf {
  name: string
  hours: number
}

export interface SunburstChild {
  name: string
  hours: number
  color?: string | null
  children: SunburstLeaf[]
}

export interface SunburstGroup {
  name: string
  hours: number
  color: string | null
  children: SunburstChild[]
}

export interface SunburstData {
  groups: SunburstGroup[]
}

export interface CompletenessData {
  total_hours: number
  classified_hours: number
  completeness: number
  days_recorded: number
  denominator_hours_per_day: number
  /** 总时间（小时）= 基数 × 有记录天数，展示「已记录 h / 总时间 h」用 */
  denominator_hours: number
}

export interface WeeklyStructureWeek {
  year: number
  week: number
  by_l1: Record<string, number>
  by_l2: Record<string, number>
  by_l3: Record<string, number>
  completeness: number
}

export interface WeeklyStructure {
  weeks: WeeklyStructureWeek[]
}

export type AttributionType = '成长' | '关系' | '维持' | '谋生' | '流失'
export type ActivityType =
  | '睡眠' | '维护性事务' | '深度工作' | '浅层工作' | '主动休息'
  | '被动消耗' | '社交' | '兴趣记录' | '未归类'

export const ATTRIBUTION_OPTIONS: AttributionType[] = ['成长', '关系', '维持', '谋生', '流失']
export const ACTIVITY_TYPE_OPTIONS: ActivityType[] = [
  '深度工作', '浅层工作', '主动休息', '被动消耗', '睡眠',
  '维护性事务', '社交', '兴趣记录', '未归类',
]
export const ACTIVITY_TYPE_COLOR_MAP: Record<string, string> = {
  '睡眠': '#64748B', '维护性事务': '#94A3B8', '深度工作': '#6366F1',
  '浅层工作': '#0EA5E9', '主动休息': '#10B981', '被动消耗': '#F87171',
  '社交': '#C084FC', '兴趣记录': '#EC4899', '未归类': '#CBD5E1',
}
export const ATTRIBUTION_COLOR_MAP: Record<string, string> = {
  '成长': '#10B981', '关系': '#A855F7', '维持': '#6366F1',
  '谋生': '#0EA5E9', '流失': '#F87171',
}

export interface TrendItem {
  period: string
  [category: string]: string | number
}

export interface BalanceCategory {
  name: string
  hours: number
  percentage: number
  color: string
}

export interface BalanceData {
  total_hours: number
  categories: BalanceCategory[]
}

export interface RankingItem {
  task_name: string
  category: string
  color: string
  total_hours: number
  record_count: number
}

export interface DistributionData {
  morning: number
  afternoon: number
  evening: number
  morning_pct: number
  afternoon_pct: number
  evening_pct: number
}

export interface CalendarDay {
  date: string
  hours: number
  count: number
}

export interface ImportResult {
  inserted: number
  updated: number
  skipped: number
  /** CSV 内「任务名 + 开始时刻」完全重复、已去重的行数（v3.58.5） */
  deduplicated?: number
  /** CSV 解析出的有效原始记录条数（去重前） */
  total_parsed?: number
  /** 本次新建的「未归类」任务名数量 */
  unclassified?: number
  error?: string
}

export const CATEGORY_MAP: Record<string, { color: string; icon: string }> = {
  '工作': { color: '#EF4444', icon: '💼' },
  '学习': { color: '#10B981', icon: '📖' },
  '生活': { color: '#F59E0B', icon: '🏠' },
  '兴趣记录': { color: '#3B82F6', icon: '🎨' },
}
