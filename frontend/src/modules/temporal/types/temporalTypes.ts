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
  /**
   * 记录来源（v3.64.33）：由 `import_batch` 在后端分类得出，**前端不写中文映射**。
   * `unlabeled` = 早期记录没留来源；`other` = 有批次号但代码没认出来 —— 两者别混。
   */
  source_kind?: TaskSourceKind
  source_label?: string
}

export type TaskSourceKind =
  | 'manual' | 'timer' | 'csv' | 'worklog' | 'overtime_recon' | 'unlabeled' | 'other'

/** 来源类型汇总（`/temporal/tasks/sources/`） */
export interface SourceKindSummary {
  kind: TaskSourceKind
  label: string
  /** 这个来源是什么、从哪写进来的（后端下发，前端不编） */
  hint: string
  count: number
  batches: number
}

/** 单个导入批次 */
export interface SourceBatchItem {
  /** 批次号；`未标注` 的那一项为 null */
  batch: string | null
  kind: TaskSourceKind
  label: string
  count: number
  /** 这一批涉及多少个不同任务名 */
  name_kinds: number
  first_start: string | null
  last_start: string | null
  /** 这批记录**最后一次被改动**的时刻（不是导入时刻 —— 编辑也会刷新它） */
  last_touch: string | null
}

export interface SourceOverview {
  total_records: number
  total_batches: number
  items: SourceBatchItem[]
  kinds: SourceKindSummary[]
  unlabeled_count: number
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

/**
 * 归因来源只有两档（v3.64.16）：
 * - `default`：映射表那一列（`temporal_task_meta.default_attribution`）明确写着的值
 * - `fallback`：没设 → 兜底「成长」
 *
 * 🔴 曾有第三档 `rule`（赎回期外挂规则）。它是 `default` 的影子副本，却只覆盖少数
 *    任务名，导致赎回期的六类小时静默漏数 —— 整条退役，不要再加回来。
 */
export type AttributionSource = 'default' | 'fallback'

export interface MetaLedgerItem {
  task_name: string
  activity_type: string
  /** TaskMeta 上存的默认归因（可能为空） */
  default_attribution: string | null
  /** 实际生效归因：映射表那列 > 兜底 */
  effective_attribution: string | null
  attribution_source: AttributionSource | null
  /**
   * 是否「没配 L1 归因、靠兜底」。
   *
   * 🔴 与 `attribution_source === 'fallback'` 同源，但**单独给一个布尔**是为了
   *    让下拉框能直接用它判「该显示空还是显示值」：从前下拉绑的是
   *    `effective_attribution`，兜底值被当成已填的选中项 ⇒ 用户点「去归好」
   *    进来只看到「成长」，以为早配好了，而库里是 NULL。
   */
  is_attr_unset: boolean
  is_unclassified: boolean
  is_system: boolean
  /**
   * 是否计入「成长计时」（每周状态里的成长小时数）。
   *
   * 🔴 这是**唯一依据**（v3.64.11）：此前是隐式的「L2 = 深度工作」，
   *    界面上看不见，想拉一个新分类进来只能把它塞进「深度工作」桶；
   *    而且挪走某项任务会顺手改掉成长口径。现在改 L2 不再影响这里。
   */
  counts_growth: boolean
  /**
   * 「今天的三条线」里的角色（v3.64.12）；空串 = 不参与护栏。
   *
   * 🔴 与 `counts_growth` 同理：角色写在标记上、**不看任务名**。
   *    否则改个名，护栏会静默变成「未记录」，且看不出是改名导致的。
   *    阈值不在前端 —— 后端 `DAILY_GUARD_LINES` 是唯一一份。
   */
  daily_role: DailyRole
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
  /** 计入成长计时的任务名个数 / 累计时长（改开关时能立刻看到动了多少量） */
  growth_count: number
  growth_hours: number
  /** 标了「护栏角色」的任务名个数（只数睡眠 / 午睡；「流失」按归因，不占这一格） */
  role_count: number
  /**
   * 没配 L1 归因（按兜底「成长」计入）的任务名个数 / 累计时长。
   *
   * 🔴 与 `unclassified`（L2 没配）分开：一个是「它属于哪类活动」没答，
   *    一个是「它对你意味着什么」没答。合并成一个「未配」会让人以为填一次就都好了。
   */
  unset_attr_count: number
  unset_attr_hours: number
  by_attribution: Record<string, number>
}

export interface MetaLedgerData {
  summary: MetaLedgerSummary
  returned: number
  items: MetaLedgerItem[]
}

/** 一行台账的四列属性 —— 改名/合并时用来比「谁覆盖谁」 */
export interface TaskMetaAttrs {
  activity_type: string
  default_attribution: string | null
  counts_growth: boolean
  daily_role: DailyRole
}

/**
 * 改名 / 合并的结果（`dry_run=1` 时同一结构，只是没写库）。
 *
 * 🔴 `merged` 由**后端**判定（新名是否已存在），前端不许自己拿台账行去猜：
 *    列表一旦被筛选过就可能猜错，用户点确定前看到「改名」、做完却是「合并」。
 */
export interface TaskRenameResult {
  task_name: string
  new_name: string
  /** `true` = 新名已存在，这次是「并过去」；`false` = 纯改名 */
  merged: boolean
  moved_records: number
  moved_hours: number
  dry_run: boolean
  /** 合并时生效的那套属性（目标那行）；纯改名时为 null */
  kept: TaskMetaAttrs | null
  /** 合并时被覆盖掉的那套属性；纯改名时为 null */
  dropped: TaskMetaAttrs | null
  /** 会被覆盖掉的字段中文名（后端算好，前端只打印） */
  changed_attrs: string[]
}

/** 台账「来源」列：口径与后端 resolve_attribution_detail 一致 */
export const ATTR_SOURCE_MAP: Record<AttributionSource, { label: string; color: string; tip: string }> = {
  // ⚠️ 标签叫「任务默认」而不是「类型默认」：这个值来自**该任务名**自己的那一行，
  //    不是 L2 类型预设。旧标签让人以为「改 L2 就能改归因」，实际改 L2 不碰归因。
  default: { label: '任务默认', color: '#94A3B8', tip: '取自该任务名在映射表里设的 L1 归因' },
  // ⚠️ 「兜底」用琥珀色而不是浅灰：浅灰（#CBD5E1）在表格里几乎看不见，
  //    用户因此认为「已经配好了」。兜底不是一个中性的信息，它是一条待办。
  fallback: { label: '兜底', color: '#F59E0B', tip: '未设默认归因，兜底为「成长」；改 L2 类型不会顺手改归因' },
}

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

export type AttributionType = '成长' | '体验' | '关系' | '维持' | '谋生' | '流失'
export type ActivityType =
  | '睡眠' | '维护性事务' | '深度工作' | '浅层工作' | '主动休息'
  | '被动消耗' | '社交' | '兴趣记录' | '主动经历' | '未归类'

// ⚠️ 顺序必须与后端 `temporal/constants.py` 的 `ATTRIBUTION_ORDER` 逐字一致 ——
//    它同时是「主导归因」两两并列时的取值序（靠前者胜），不只是显示顺序。
//    演进史：v3.58.11 插「关系」、v3.60.36 插「体验」，两次都只能**纯增量插在「成长」之后**。
export const ATTRIBUTION_OPTIONS: AttributionType[] = ['成长', '体验', '关系', '维持', '谋生', '流失']
export const ACTIVITY_TYPE_OPTIONS: ActivityType[] = [
  '深度工作', '浅层工作', '主动休息', '被动消耗', '睡眠',
  '维护性事务', '社交', '兴趣记录', '主动经历', '未归类',
]
// ⚠️ 与后端 `ACTIVITY_TYPE_COLORS` 大体一致，但「社交」这里是 #C084FC、后端是 #A855F7 ——
//    既有偏差（不是本轮引入）。改色会动到已经看惯的界面，留待单独确认，本轮不动。
export const ACTIVITY_TYPE_COLOR_MAP: Record<string, string> = {
  '睡眠': '#64748B', '维护性事务': '#94A3B8', '深度工作': '#6366F1',
  '浅层工作': '#0EA5E9', '主动休息': '#10B981', '被动消耗': '#F87171',
  '社交': '#C084FC', '兴趣记录': '#EC4899', '主动经历': '#F59E0B',
  '未归类': '#CBD5E1',
}
// 🔴 单一真源：界面任何地方要「归因 → 颜色」，都必须从这里取。
//    曾有一份内联副本住在 `TimeStatsView.vue`（每加一个词就漏一处、静默落灰色兜底），
//    v3.60.36 已收口回来 —— 不要再写第三份。
export const ATTRIBUTION_COLOR_MAP: Record<string, string> = {
  '成长': '#10B981', '体验': '#F59E0B', '关系': '#A855F7',
  '维持': '#6366F1', '谋生': '#0EA5E9', '流失': '#F87171',
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
  /** 用户在预演清单里自己勾掉的行数（与「库已有故跳过」分开报，v3.64.32） */
  skipped_by_user?: number
  /** 本次新建的「未归类」任务名数量 */
  unclassified?: number
  error?: string
}

/**
 * 两条时段「怎么重叠的」—— `contained/edge/likely_dup` 是后端定的四类，前端只查表。
 *
 * 🔴 别在前端按 `overlap_minutes` 重新分档：分档还看长度比与包含关系，
 *    口径在 `services.classify_overlap`（单一真源）。
 */
export type ConflictRelation = 'contained' | 'edge' | 'review' | 'likely_dup'

export interface ImportConflict {
  id: number
  task_name: string
  start_time: string
  end_time: string
  overlap_minutes: number
  relation: ConflictRelation
}

/** 预演里「需要人看一眼」的一行（`contained/edge/clean` 不进这个数组） */
export interface ImportPreviewRow {
  /** CSV 物理行号（表头是第 1 行）—— 导入时原样回传，别自己重算 */
  row_no: number
  task_name: string
  start_time: string
  /** 只有时分；为空表示源数据没给结束时刻（时长另算） */
  end_time: string
  hours: number
  verdict: ConflictRelation
  /** 与它相交的记录总数（`conflicts` 最多带 2 条） */
  conflict_total: number
  conflicts: ImportConflict[]
}

/**
 * 导入预演结果（只读）。
 *
 * 两个维度正交，别混：
 * - **出路** `already_exists`：库里已有同一条 ⇒ 落库时跳过或更新（预演不判哪个）
 * - **关系** 四类：与库里**其它**记录的时段关系
 *
 * 不变量：`total = inner_duplicate + already_exists + clean + Σ四类`
 */
export interface ImportPreview {
  total_parsed: number
  parse_errors: Record<string, number>
  /** 同一份 CSV 内部重复的行数（落库时丢弃，不计入 summary 的桶） */
  inner_duplicate: number
  summary: {
    total: number
    already_exists: number
    clean: number
    contained: number
    edge: number
    review: number
    likely_dup: number
    /** `review + likely_dup`：需要人看的行数 */
    needs_review: number
  }
  rows: ImportPreviewRow[]
  error?: string
}

/** 最近常用任务名的一项（手工新增弹窗的快捷候选） */
export interface FrequentTaskName {
  task_name: string
  /** 窗口内的记录次数 —— 「频繁」的实际口径 */
  record_count: number
  total_hours: number
}

/**
 * 最近 N 个月最频繁的任务名。
 *
 * 🔴 窗口（几个自然月）与排序口径全在后端
 *    （`TemporalStatsService.get_frequent_names`），前端不复制判据、
 *    也不自己算「最近 3 个月」—— 否则两把尺子，改一处漏一处还不报错。
 */
export interface FrequentNamesData {
  months: number
  limit: number
  window_start: string
  items: FrequentTaskName[]
}

/** 与待新增/编辑时段相交的一条已有记录 */
export interface OverlapConflict {
  id: number
  task_name: string
  /** 已是本地时间 `YYYY-MM-DD HH:MM`（后端格式化，前端不再二次转） */
  start_time: string
  end_time: string
  /** 交集分钟数 —— 提示里给人看的量 */
  overlap_minutes: number
  /** 同名 ⇒ 极可能重复新增；异名 ⇒ 合法并行（大段里套细分） */
  same_name: boolean
}

/**
 * 时段重叠查询结果（`tasks/check_overlap`）。
 *
 * 🔴 「重叠」在本库里是**合法形态**（「牛马工作 08:00-18:00」之内再细分「代码编程」），
 *    所以后端只回答「撞了哪些」，**不阻断保存** —— 由用户看完这份清单自己决定。
 *    别在前端把它改成一票否决，也别自己再算一遍重叠（口径在 `services.find_overlaps`）。
 */
export interface OverlapCheckData {
  has_overlap: boolean
  conflicts: OverlapConflict[]
  same_name_count: number
}

export const CATEGORY_MAP: Record<string, { color: string; icon: string }> = {
  '工作': { color: '#EF4444', icon: '💼' },
  '学习': { color: '#10B981', icon: '📖' },
  '生活': { color: '#F59E0B', icon: '🏠' },
  '兴趣记录': { color: '#3B82F6', icon: '🎨' },
}

// ─── 日常护栏：「今天的三条线」（v3.64.13）──────────────────────────────
// 🔴 这里只是后端 `constants.DAILY_ROLE_CHOICES` 的**副本**（值域要一致）；
//    **阈值一个都不在这里** —— 8 小时 / 1.5 小时 / 4 小时只在后端常量里。
// ⚠️ 「流失」那条线**没有角色**，按 L1 归因统计，所以它不在这个值域里。

export type DailyRole = '' | 'sleep_night' | 'nap'

export const DAILY_ROLE_OPTIONS: { value: DailyRole; label: string }[] = [
  { value: '', label: '不参与' },
  { value: 'sleep_night', label: '夜间睡眠' },
  { value: 'nap', label: '午睡' },
]

/** 三档状态：没有 `unknown` / `pending` 之类的兜底桶（项目铁律） */
export type DailyGuardStatus = 'ok' | 'off' | 'unrecorded'

export interface DailyGuardLine {
  key: 'sleep' | 'nap' | 'lost'
  label: string
  /** `at_least` = 下限（睡够），`at_most` = 上限（别超） */
  direction: 'at_least' | 'at_most'
  /** 这条线「配好了没有」。false ⇒ 未记录是「还没配」（配置问题），不是「今天没做」 */
  configured: boolean
  threshold_hours: number
  /** 「≥ 8 小时」/「≤ 1.5 小时」—— 后端给，前端不拼 */
  threshold_text: string
  /** 没记录时是 `null`，**不是 0**（`null` 与 `0` 是两件事） */
  value_hours: number | null
  value_text: string
  status: DailyGuardStatus
  /** 「达标」/「未达」/「越线」/「未记录」—— 后端给，前端不写中文表 */
  status_text: string
  /** 「差 0.6 小时」/「超 2 小时」；达标与未记录时为空串 */
  gap_text: string
  /** 未记录时是原因句（「今天没有午睡记录」），否则是阈值说明 */
  detail_text: string
  record_count: number
}

export interface DailyGuardData {
  date: string
  lines: DailyGuardLine[]
  /** 三条线里已落地的条数（睡眠/午睡看角色、流失看归因）；0 = 一条都还没配 */
  configured_lines: number
}

