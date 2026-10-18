/** 自我运转 · 前端类型定义
 *
 * 🔴 读之前先知道四件事：
 *
 * 1. **本文件是 `backend/apps/selfrun/constants.py` 的副本** —— 漏改**不会报错**
 *    （要么落 `|| 兜底` 变灰、要么少一个下拉选项）。改枚举时**两边同时改**。
 * 2. **判定阈值（`on_track` / `slipping` 的分界）不在这里** —— 由后端随
 *    `status_explain.thresholds` 下发，前端 **0 个阈值数字**，只上色不判。
 * 3. **配色也不在这里** —— 由后端 `colors` 下发；本文件只留一个**中性兜底灰**，
 *    免得接口挂掉时整页无色。**刻意不做第二份彩色表**（那就是第二份真源）。
 * 4. **`Decimal` 字段到达前端是「字符串」**（DRF 默认 `COERCE_DECIMAL_TO_STRING=True`）
 *    ⇒ 所有数值一律过 `num()` 归一化再用。
 *    ⚠️ 直接比较会静默出错：`'3.00' > '12.00'` 在 JS 里是 **true**（字符串逐位比）。
 */

// ══════════════════════════════════════════════════════════════
// 一、枚举（与后端 constants.py 一一对应）
// ══════════════════════════════════════════════════════════════

export type StageStatus = 'draft' | 'active' | 'paused' | 'closed'
export type PauseReason = 'trip' | 'sick' | 'fallow' | 'other'
export type PeriodType = 'weekly' | 'monthly'
export type PeriodStatus = 'on_track' | 'slipping' | 'slid' | 'no_record' | 'fallow'
/** 🔴 刻意只有两个值：三种「暂停」作用域不同，混进来必成兜底桶 */
export type MetricStatus = 'active' | 'retired'
export type Verdict = 'goal' | 'floor' | 'miss' | 'empty' | 'unknown'
export type SourceKind = 'auto' | 'manual' | 'auto_plus_manual'
export type Agg = 'sum_hours' | 'sum_value' | 'distinct_days' | 'count' | 'boolean' | 'manual_sum'
export type Direction = 'at_least' | 'at_most'
/** 读数的「状态」（与 `verdict` 正交：一个说数据源健不健康，一个说做到没有） */
export type ReadingState = 'ok' | 'stale' | 'unconfigured' | 'empty'
export type MetricAction = 'created' | 'goal_changed' | 'floor_changed' | 'config_changed' | 'retired' | 'revived' | 'plan_changed'
export type ChangeReason = 'template_use' | 'calibrate' | 'mood' | 'other'

/** 按期设定的作用域 —— 🔴 **两种事实**，不是「程度」：
 *  `single` 只这一期（下期回落默认）；`from` 从这一期起一直用，直到出现更晚的 `from`。
 *  同一期两条都在 ⇒ `single` 压过 `from`（特例优先于长期）。 */
export type PlanScope = 'single' | 'from'

/** 这一期的目标**从哪来** —— 🔴 三态必须能分辨。
 *  全都显示成同一个数的话，「我这周的目标怎么变了」永远说不清。 */
export type TargetSource = 'metric' | 'single' | 'from'

// ══════════════════════════════════════════════════════════════
// 二、标签（下发优先，下面是兜底）
// ══════════════════════════════════════════════════════════════

export const VERDICT_LABEL: Record<string, string> = {
  goal: '达目标',
  floor: '达底线',
  miss: '未达底线',
  empty: '本期无数据',
  unknown: '取不到',
}

export const PERIOD_STATUS_LABEL: Record<string, string> = {
  on_track: '本周合格',
  slipping: '本周及格',
  slid: '本周活着',
  no_record: '这周没有记录',
  fallow: '休耕中',
}

export const STAGE_STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  active: '进行中',
  paused: '暂停中',
  closed: '已收尾',
}

export const PAUSE_REASON_LABEL: Record<string, string> = {
  trip: '旅途',
  sick: '生病',
  fallow: '休耕',
  other: '其他',
}

export const SOURCE_KIND_LABEL: Record<string, string> = {
  auto: '自动取数',
  manual: '手工登记',
  auto_plus_manual: '自动 + 手工补记',
}

export const AGG_LABEL: Record<string, string> = {
  sum_hours: '时长求和',
  sum_value: '数值求和',
  distinct_days: '有记录天数',
  count: '计数',
  boolean: '有无',
  manual_sum: '手工求和',
}

export const DIRECTION_LABEL: Record<string, string> = {
  at_least: '至少（≥）',
  at_most: '至多（≤）',
}

export const PERIOD_TYPE_LABEL: Record<string, string> = {
  weekly: '每周',
  monthly: '每月',
}

export const STATE_LABEL: Record<string, string> = {
  ok: '正常',
  stale: '数据源过期',
  unconfigured: '未配置目标',
  empty: '本期无数据',
}

export const METRIC_ACTION_LABEL: Record<string, string> = {
  created: '创建',
  goal_changed: '目标变更',
  floor_changed: '底线变更',
  config_changed: '口径变更',
  retired: '退役',
  revived: '恢复',
  plan_changed: '按期设定',
}

export const PLAN_SCOPE_LABEL: Record<string, string> = {
  single: '只这一期',
  from: '从这一期起（一直用，直到再改）',
}

export const TARGET_SOURCE_LABEL: Record<string, string> = {
  metric: '阶段默认',
  single: '本期设定',
  from: '按期设定',
}

/** 「这一期是谁定的」上色：`metric` = 默认值**不挂标签**（挂满标签反而看不见特例） */
export const TARGET_SOURCE_TAG: Record<string, '' | 'info' | 'warning' | 'success'> = {
  metric: '',
  single: 'warning',
  from: 'success',
}

export const CHANGE_REASON_LABEL: Record<string, string> = {
  template_use: '套用模板',
  calibrate: '校准：之前的预期不现实',
  mood: '状态：最近状态不好，想先松一点',
  other: '其他',
}

/** 月度三问（`answer_sheet` 的键）—— 与后端 `compute_monthly_status` 同序 */
export const MONTHLY_QUESTIONS = [
  {
    key: 'q1_income',
    label: '这个月有人为你的东西付过钱吗？',
    hint: '哪怕 1 块钱 —— 问的是「验证」，不是「收入」',
  },
  {
    key: 'q2_output',
    label: '这个月你产出的东西发出去过吗？',
    hint: '发出去了就算，不管有没有人看',
  },
  {
    key: 'q3_runway',
    label: '这个月结束时，你比月初更清楚自己能撑多久吗？',
    hint: '答案可以是「更清楚了，撑不了多久」—— 那也答「是」',
  },
] as const

/** 🔴 **中性兜底灰**（只在后端 `colors` 缺失时用）。刻意不做第二份彩色表。 */
export const FALLBACK_COLOR = '#CBD5E1'

// ══════════════════════════════════════════════════════════════
// 三、实体（与后端序列化器对齐）
// ══════════════════════════════════════════════════════════════

export interface SelfRunStage {
  id: number
  name: string
  start_date: string
  end_date: string | null
  status: StageStatus
  status_display: string
  pause_reason: PauseReason | null
  pause_reason_display: string
  paused_since: string | null
  resume_at: string | null
  last_seen_at: string | null
  summary: string
  summary_snapshot: StageSummary | null
  summary_at: string | null
  note: string
  created_at: string
  updated_at: string
  /** 现算不落库：生效中的 KPI 条数 */
  metric_count: number
  /** 现算不落库：已进行天数 */
  elapsed_days: number
}

export interface SelfRunMetric {
  id: number
  stage: number
  template_key: string
  name: string
  period_type: PeriodType
  unit: string
  direction: Direction
  /** ⚠️ `Decimal` ⇒ 到达前端是**字符串**（或 null）。一律过 `num()` */
  goal_value: string | number | null
  floor_value: string | number | null
  goal_why: string
  floor_why: string
  agg: Agg
  source_kind: SourceKind
  source_config: { kind?: string; where?: Record<string, unknown> }
  status: MetricStatus
  status_display: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface SelfRunMetricLog {
  id: number
  metric: number
  metric_name: string
  action: MetricAction
  action_display: string
  field_name: string | null
  from_value: unknown
  to_value: unknown
  reason: ChangeReason | null
  reason_display: string
  reason_note: string
  at: string
}

/**
 * 溯源行里的**一项结构化事实**（如「净资产 ¥300,876.46」）。
 *
 * 🔴 金额只下发**数字**，绝不在后端拼成 `¥300,876.46` 字符串 ——
 *    拼好的串会绕过 `formatAmount` 的隐私掩码（`privacy.ts` 唯一实现），
 *    隐私模式下这一行就会裸露。所以 `kind` 决定前端用哪个格式化函数。
 */
export interface BreakdownFact {
  label: string
  value: number
  /** amount = 金额（走 formatSignedAmount，带符号与掩码）；count = 计数 */
  kind?: 'amount' | 'count'
}

/** 溯源行的附带信息。键名是**约定**，后端必须照此下发，否则前端读不到。 */
export interface BreakdownExtra {
  /** 自由备注（前端唯一认的备注键 —— 不是 `notes` / `remarks`） */
  note?: string
  /** 副标题（部分 reader 用） */
  title?: string
  /** 结构化事实（v3.62.34 起：资产盘点等「一次 = 一个对象」的场景用） */
  facts?: BreakdownFact[]
  [k: string]: unknown
}

/** 溯源的一行（后端 `breakdown` 里的一项） */
export interface BreakdownItem {
  label: string
  value: number
  count: number
  /** L2（活动类型 / 账单子分类 / 所属年月）—— 有的 reader 给，有的给 null */
  l2: string | null
  extra?: BreakdownExtra
}

/** 告警（越界值 / 两把尺子打架 / 算不出来） */
export interface ReadingWarning {
  code: string
  count?: number
  hint: string
  [k: string]: unknown
}

export interface ReadingFreshness {
  kind: string | null
  at: string | null
  days?: number
  limit?: number
  hint?: string
}

/** 一条 KPI 在某个区间上的完整读数 —— **T2 展示与 T3 冻结用的是同一个结构** */
export interface Reading {
  metric_id: number
  name: string
  unit: string
  direction: Direction
  period_type: PeriodType
  agg: Agg
  source_kind: SourceKind
  /** 🔴 **这一期生效的**目标（可能来自阶段默认、本期特例或按期设定） */
  goal_value: number | null
  floor_value: number | null
  goal_why: string
  floor_why: string
  /** 这一期的目标**从哪来** —— 三态必须能分辨，否则「目标怎么变了」说不清 */
  target_source: TargetSource
  target_source_label: string
  plan_id: number | null
  plan_scope: PlanScope | null
  plan_note: string
  /** 🔴 三个数都要在：只存 final 的话，三个月后没法回答「这 1 天是自动取的还是你补的」 */
  auto_value: number | null
  manual_value: number | null
  final_value: number | null
  verdict: Verdict
  state: ReadingState
  /** 本周你明确说了「这条先不算」 */
  skipped: boolean
  breakdown: BreakdownItem[]
  breakdown_total: number
  warnings: ReadingWarning[]
  freshness: ReadingFreshness
}

export interface PeriodStatusExplain {
  value: PeriodStatus | ''
  /** 分子：达目标或达底线的条数 */
  ok: number
  /** 分母：**剔掉 unknown 与 skipped 之后**的条数 */
  counted: number
  total: number
  skipped: number
  unknown: number
  empty: number
  /** 🔴 阈值由后端下发，前端只上色不判 */
  thresholds: Record<string, number>
}

export interface Heartbeat {
  last_seen_at: string | null
  days: number | null
  message: string | null
}

export interface SelfRunPeriod {
  id: number
  stage: number
  stage_name: string
  period_type: PeriodType
  period_key: string
  period_start: string
  period_end: string
  is_partial: boolean
  status: PeriodStatus | ''
  status_display: string
  readings: Reading[] | null
  config_fingerprint: string
  skipped_metric_ids: number[]
  answer_sheet: AnswerSheet | null
  review_text: string
  review_edits: { text: string; at: string; days_after_close: number }[]
  closed_at: string | null
  is_backfilled: boolean
  backfilled_at: string | null
  reopened_at: string | null
  reopen_count: number
  reopen_reason: string
  created_at: string
  updated_at: string
}

export interface MonthlyAnswer {
  /** 🔴 `null` = 还没答，`false` = 答了否 —— 两者必须分开（又一处 `null ≠ 0`） */
  answer: boolean | null
  note?: string
}
export type AnswerSheet = Record<string, MonthlyAnswer>

export interface SelfRunCheckin {
  id: number
  metric: number
  metric_name: string
  unit: string
  checkin_date: string
  /** 负数 = 冲销 */
  value: string | number
  note: string
  created_at: string
}

// ══════════════════════════════════════════════════════════════
// 四、T1 模板与试算
// ══════════════════════════════════════════════════════════════

/** 模板库里的一条（**已落库**，可增删改）。
 *
 * 🔴 「模板是**拷贝**不是引用」：阶段生效时把模板值**抄进** `SelfRunMetric`，
 *    此后改模板或删模板**都不影响已建阶段**（`template_key` 只是字符标记不是 FK）。
 */
export interface KpiTemplate {
  id: number
  key: string
  name: string
  period_type: PeriodType
  unit: string
  direction: Direction
  goal_value: number | null
  floor_value: number | null
  agg: Agg
  source_kind: SourceKind
  source_config: { kind?: string; where?: Record<string, unknown> }
  goal_why: string
  floor_why: string
  sort_order: number
  /** 后端补的：取数器 key 与它指向的源模块（用于「你要去哪补数据」） */
  reader_kind: string | null
  reader_hint: string
  /** 后端补的：被几条 KPI 引用过（**删模板不影响它们**，但要让你看见影响面） */
  used_count: number
}

/** 模板接口随列表一起下发的枚举（前端**不抄第三份**取数器清单）。 */
export interface SelfRunEnumOption {
  value: string
  label: string
}

export interface ReaderOption {
  value: string
  /** 这个取数器指向哪个模块（用于「你要去哪补数据」） */
  hint: string
  /** 还要在界面里补哪个 `where` 字段（`null` = 该取数器自带固定口径） */
  where_key: string | null
}

export interface TemplateEnum {
  agg: SelfRunEnumOption[]
  source_kind: SelfRunEnumOption[]
  direction: SelfRunEnumOption[]
  period_type: SelfRunEnumOption[]
  plan_scope: SelfRunEnumOption[]
  readers: ReaderOption[]
  module_value_keys: string[]
  /** `temporal_*` 的 `l2` 候选（取自库里的 `activity_type`，不是常量表） */
  l2_options: string[]
}

/** 某一条 KPI 在**某一期**的目标（`selfrun_metric_plan` 一行）。 */
export interface SelfRunMetricPlan {
  id: number
  metric: number
  metric_name: string
  period_key: string
  scope: PlanScope
  scope_display: string
  goal_value: number | null
  floor_value: number | null
  goal_why: string
  floor_why: string
  note: string
  created_at: string
  updated_at: string
}

/** 「哪几期可以修订」的一项（周期标识**只由后端算**）。 */
export interface PeriodOption {
  key: string
  /** 半开区间左端。⚠️ `end` 是**不含**的右端，别当「最后一天」显示。 */
  start: string
  end: string
  offset: number
  label: string
}

/** 修订界面一行：某条 KPI 在某一期的**生效目标**。 */
export interface TargetRow {
  metric_id: number
  name: string
  unit: string
  direction: Direction
  /** 阶段默认的双档（用来对比「这一期被改成什么了」） */
  base_goal: number | null
  base_floor: number | null
  /** 🔴 **这一期生效的**双档 */
  goal_value: number | null
  floor_value: number | null
  target_source: TargetSource
  target_source_label: string
  goal_why: string
  floor_why: string
  plan_id: number | null
  plan_scope: PlanScope | null
  plan_note: string
  /** 这条 KPI 一共改过几期（>0 ⇒ 别拿阶段默认值去读往期） */
  plan_count: number
}

export interface TargetsPayload {
  stage: SelfRunStage
  period_type: PeriodType
  period_key: string
  period_start: string
  period_end: string
  current_key: string
  is_current: boolean
  is_past: boolean
  rows: TargetRow[]
}

export interface TargetsResponse {
  stage: SelfRunStage | null
  targets: TargetsPayload | null
  hint?: string
  written: Written
}

export interface PreviewRow {
  key: string
  start: string
  end: string
  value: number | null
  state: ReadingState
  verdict: Verdict
}

export interface PreviewResult {
  period_type: PeriodType
  rows: PreviewRow[]
  stats: { count: number; min: number; max: number; median: number; mean: number } | Record<string, never>
  floor_options: { floor: number; hit: number; total: number }[]
  reader_kind: string | null
  warnings: ReadingWarning[]
}

// ══════════════════════════════════════════════════════════════
// 五、T4 阶段总结
// ══════════════════════════════════════════════════════════════

export interface StageMetricStat {
  metric_id: number
  name: string
  unit: string
  period_type: PeriodType
  /** ⚠️ 这里是**阶段默认**的双档；按期改过的期，真实目标在各自 `readings` 里（已冻结） */
  goal_value: number | null
  floor_value: number | null
  /** 这条 KPI 改过几期、改了哪几期（>0 ⇒ 别拿默认值去读往期） */
  plan_count: number
  plan_periods: string[]
  avg: number | null
  hit: number
  total: number
  best: { value: number; period_key: string } | null
}

export interface StageSummary {
  stage_id: number
  name: string
  start_date: string
  end_date: string | null
  total_weeks: number
  /** 剔掉残缺周之后的周数 */
  counted_weeks: number
  partial_weeks: number
  total_months: number
  metrics: StageMetricStat[]
  weekly_breakdown: {
    period_type: PeriodType
    on_track: number
    slipping: number
    slid: number
    fallow: number
  }
  monthly_statuses: { period_key: string; status: PeriodStatus | ''; yes_count: number | null }[]
  /** 指纹分组 —— 同组才可直接比（T4 的「尺子断点」） */
  fingerprints: { fingerprint: string; periods: string[] }[]
}

// ══════════════════════════════════════════════════════════════
// 六、接口返回外壳（`written` 让「数据流转」在运行时也可见）
// ══════════════════════════════════════════════════════════════

export type Written = Record<string, number>

export interface CurrentPeriodResponse {
  stage: SelfRunStage | null
  period: SelfRunPeriod | null
  /** `true` = 现算（进行中）；`false` = 读冻结快照（已归档） */
  live: boolean
  /**
   * 当期标识（`2026-W42` / `2026-10`）—— 🔴 **与有没有阶段无关**，后端两个分支都给。
   *
   * 用它来回答「现在说的是哪一周」：前端**不许**按 `Date` 自己算 ISO 周
   * （跨年边界会静默差一周）。`period_end` 是**半开区间的右端**（不含），
   * 别当成「最后一天」直接显示。
   */
  period_key: string
  period_start: string
  period_end: string
  hint?: string
  status_explain?: PeriodStatusExplain
  heartbeat?: Heartbeat
  colors?: { verdict: Record<string, string>; period: Record<string, string> }
  written: Written
}

export interface OverviewCard {
  status: PeriodStatus | ''
  status_label: string
  ok: number
  counted: number
  goal_count: number
  period_key: string | null
  heartbeat: Heartbeat
}

export interface OverviewResponse {
  stage: SelfRunStage | null
  card: OverviewCard | null
  written: Written
}

// ══════════════════════════════════════════════════════════════
// 七、归一化小工具
// ══════════════════════════════════════════════════════════════

/**
 * `Decimal 字符串 | number | null` → `number | null`。
 *
 * 🔴 **`null` 必须原样保留** —— 它是「根本没有这个数」（显示「—」），
 *    与 `0`（「确实是 0」，显示「0h」）是两件事。
 * 🔴 **不要用 `Number(v) || null`**：`0` 会被 `||` 换成 `null`。
 */
export function num(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** 数值展示：`null` ⇒ 「—」，**绝不显示 0**（`null ≠ 0`）。 */
export function fmt(v: string | number | null | undefined, unit = ''): string {
  const n = num(v)
  if (n === null) return '—'
  const s = Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, '')
  return unit ? `${s}${unit}` : s
}

/** 一条读数的档位文案：「≥ 12h（目标）/ ≥ 5h（底线）」 */
export function tierText(r: Reading): string {
  const op = r.direction === 'at_least' ? '≥' : '≤'
  const g = num(r.goal_value)
  const f = num(r.floor_value)
  const parts: string[] = []
  if (g !== null) parts.push(`${op} ${fmt(g, r.unit)}（目标）`)
  if (f !== null) parts.push(`${op} ${fmt(f, r.unit)}（底线）`)
  return parts.length ? parts.join(' · ') : '未设线（只展示不判定）'
}

/**
 * 「这一期的目标是从哪来的」。
 *
 * 🔴 `metric`（阶段默认）**返回空串** —— 默认值也挂标签的话，满屏标签反而让
 *    真正的特例看不见（这条铁律的另一半：`null ≠ 0`，这里则是「默认 ≠ 特例」）。
 */
export function targetSourceText(r: { target_source?: TargetSource }): string {
  const s = r.target_source
  if (!s || s === 'metric') return ''
  return TARGET_SOURCE_LABEL[s] ?? s
}
