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
export type PeriodStatus = 'great' | 'on_track' | 'slipping' | 'slid' | 'no_record' | 'fallow'
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

/**
 * 周期档位 —— **只放本名，不带「本周 / 本月」**（v3.62.45）。
 *
 * 🔴 原来这里写死「本周合格」，于是「本月状态」页也在说「本周」——
 *    用户读到的第一反应是「走错页了」。前缀现在由 `periodStatusLabel()`
 *    按 `periodType` 拼；页面知道自己开的是哪把尺子。
 */
export const PERIOD_STATUS_LABEL: Record<string, string> = {
  great: '我超棒',
  on_track: '合格',
  slipping: '及格',
  slid: '活着',
  no_record: '这期没有记录',
  fallow: '休耕中',
}

/** 「本周」/「本月」——与后端 `PERIOD_TYPE_PREFIX` 同一份语义 */
export const PERIOD_PREFIX: Record<string, string> = {
  weekly: '本周',
  monthly: '本月',
}

/** 月度三问的题数（后端 `MONTHLY_QUESTION_COUNT`）—— 判定分母恒为它 */
export const MONTHLY_QUESTION_COUNT = 3

/**
 * 拼出完整档位名：`periodStatusLabel('great', 'monthly')` ⇒ `本月我超棒`。
 *
 * `periodType` 省略时只返回本名（阶段汇总页把周与月混在一起统计，不能带前缀）。
 */
export function periodStatusLabel(status: string, periodType?: string | null): string {
  const core = PERIOD_STATUS_LABEL[status]
  if (!core) return status || '—'
  const prefix = periodType ? PERIOD_PREFIX[periodType] ?? '' : ''
  return prefix + core
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
  /** 上级阶段 id（顶级阶段为 `null`）。⚠️ **两层封顶**：有 `parent` 的一定是叶子 */
  parent: number | null
  /** 上级阶段名（由后端拼，前端不拿 id 去列表里反查 —— 列表可能没拉全） */
  parent_name: string | null
  /** 现算不落库：挂了多少个小阶段 */
  children_count: number
  /**
   * 长阶段 = **顶级 + 一条 KPI 都没有**（后端判，前端不自己推）。
   *
   * 🔴 长阶段只汇总（钱 / 时间 / 作品），**不产生周月判定** ——
   *    `SelfRunPeriod` 只挂在叶子阶段上，长阶段给它配 KPI 后端直接 400。
   * ⚠️ 判据是「有没有 KPI」而不是「有没有孩子」：长阶段可以先建、后挂小阶段，
   *    那段空窗期它同样是长阶段。
   */
  is_long_stage: boolean
  /** 账本配置（目前只有 `pool_principal` 本金）。**不是**派生值，是输入 */
  ledger_config: { pool_principal?: number } & Record<string, unknown>
  /** 现算不落库：生效中的 KPI 条数 */
  metric_count: number
  /** 现算不落库：今天在阶段里是第几天；0 = 还没开始 */
  elapsed_days: number
  /** 现算不落库：天数的显示词（「第 12 天」/「共 61 天」/「还有 1 天开始」）。
   *  🔴 三种态的词只由后端定一份，模板直接印，别在页里各写一遍三元表达式。
   *  ⚠️ 它**不含起止日期** —— 区间在 `range_label`，两处都写会看着像两个值。 */
  days_label: string
  /** 现算不落库：阶段区间（「2026-11-01 ~ 2026-12-31（61 天）」/
   *  「2026-11-01 起（不设终点，手动收尾）」）。
   *  🔴 起止日期只此一份：页头、仪表盘卡、阶段总结都印它，谁都不许自己拼 str。 */
  range_label: string
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
  /**
   * 档位全名（含「本周 / 本月」前缀），**后端拼好下发**。
   * 🔴 月度还没答三问时是「待答三问」（`value` 为空串）——
   *    这个词也放后端，前端自己写一遍就等于中文表又多一份。
   */
  label_text?: string
  /**
   * 判定依据：`kpi` = 周达标条数比；`questions` = 月度三问（唯一）；
   * `pending` = 月度三问还没答 ⇒ **未判定**（`value` 为空），
   * 此时 `ok/counted` 只是 KPI 参考，不参与判定。
   * 🔴 v3.64.6 起月度只有三问这一把尺子：不许再拿 KPI 档位顶上去
   *    （否则同一期会先「我超棒 4/4」后「合格 2/3」，读起来像归档给降了档）。
   */
  basis?: 'kpi' | 'questions' | 'pending'
  /** 整句判定说明（后端拼好：「判定线：…」或「三问答是 2/3 ⇒ 本月合格」） */
  basis_text?: string
  /** 月度：答「是」的个数 */
  yes?: number
  /** 月度：已答个数（「否」也算答过） */
  answered?: number
  /** 月度三问一个都没答 ⇒ true（此时 `value` 为空串） */
  awaiting_answers?: boolean
  /** 分子：达目标或达底线的条数（月度未判定时仅作参考） */
  ok: number
  /** 分母：**剔掉 unknown 与 skipped 之后**的条数 */
  counted: number
  total: number
  skipped: number
  unknown: number
  empty: number
  /** 🔴 阈值由后端下发，前端只上色不判 */
  thresholds: Record<string, number>
  /** 档位本名（后端只有一份；前端 `PERIOD_STATUS_LABEL` 只是兜底） */
  labels?: Record<string, string>
  /** 本期前缀：`本周` / `本月` */
  prefix?: string
  monthly_question_count?: number
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
  /** `works_count` 的 `work_kind` 候选（后端 `works.constants.WORK_KIND_CHOICES` 直发） */
  work_kind_options: SelfRunEnumOption[]
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
  /**
   * 最好的一期。`period_label` = 「2026-W42（10-12 ~ 10-18）」。
   * 🔴 **显示只用 `period_label`**：单独一个 `2026-W42` 读不出是几号到几号，
   *    ISO 周号跨年时心算必错。`period_key` 留给比对/取数，不要印。
   */
  best: { value: number; period_key: string; period_label: string } | null
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
// 七、阶段账本（`GET /stages/<pk>/ledger/`）
// ══════════════════════════════════════════════════════════════

/** 账本区间。**半开区间在数据层**；这里给的是「第几天 / 共几天 / 还剩几天」、
 *  以及 `range_label`（区间的人话，后端拼）—— 前端一个日期都别自己减。 */
export interface LedgerRange {
  start: string
  end: string
  total_days: number
  elapsed_days: number
  remaining_days: number
}

/** 时间块：与阶段总结、周 KPI「成长小时数」**同源**（都读映射表 L1 那列） */
export interface LedgerTime {
  /** 六类小时。键集由后端 `ATTRIBUTION_CHOICES_LIST` 派生 —— 加词自动多一格 */
  hours: Record<string, number>
  /** 已记录小时 = **六类之和**（红线：两者必须相等，不等就是漏数）。**不含睡眠** */
  covered_hours: number
  /** 被剔除的睡眠小时（夜间 + 午睡）。只是报出来，不进六类、不进分子。
   *  🔴 `covered_hours + excluded_sleep_hours` == 区间内全部记录时长 */
  excluded_sleep_hours: number
  /** 其中「没设默认归因、按兜底计入」的小时。**不排除在六类之外**，只单列 */
  fallback_hours: number
  /** 天数 × 每天可支配小时（**已扣生存时间、不含睡眠**） */
  theoretical_hours: number
  /** 分母的「每天几小时」—— 页面文案用它，**不许写死 12 / 14**（改口径只动后端常量） */
  theoretical_daily_hours: number
  /** 分子分母都不含睡眠。可支配按每天 14h 估、醒着 16h ⇒ 记录极全时仍可能略 > 1。
   *  别夹到 100%（照实显示，进度条自己封顶） */
  coverage_rate: number
  coverage_warn: boolean
  /** 成长小时 ÷ 已记录小时（分母不含睡眠） */
  toward_ratio: number
}

export interface LedgerPool {
  principal: number
  injected: number
  self_expense: number
  self_income: number
  balance: number
  /** 滚动 30 天日均净消耗。⚠️ 分母固定 30 —— 阶段刚开几天时偏低 */
  avg_daily: number
  /** 按当前速度能撑到哪天；`null` 时**必看** `support_zero_reason` */
  support_until: string | null
  /** 🔴 查表用，**不许**自己判 `support_until === null` 想当然（0 不是 ∞） */
  support_zero_reason: string | null
}

/** 赎回归属一档（`period_tag` 四档 + `unmarked`） */
export interface LedgerTier {
  period_tag: string
  /** 🔴 真实**笔数**（后端 `Count`）。旧的 `Sum('id')` 会把 2 笔显示成 14 笔 */
  count: number
  /** 发生额（支出与收入直接相加），**不是**净额 */
  total: number
}

export interface LedgerMoney {
  pool: LedgerPool
  tier: LedgerTier[]
  /** 允许日均 = 剩余余额 ÷ 剩余天数；与 `pool.avg_daily` **同量纲**（每天多少钱），
   *  可直接比大小。`null` 时看 `daily_allowance_zero_reason`。 */
  daily_allowance: number | null
  /** `no_principal` = 没设本金；`no_day_left` = 阶段已到最后一天 */
  daily_allowance_zero_reason: string | null
  /** 预算占用 = 日均 ÷ 允许日均；`null` 时看 `daily_use_rate_zero_reason` */
  daily_use_rate: number | null
  /** `no_allowance` = 允许值缺失或 ≤0；`net_inflow` = 日均是负的（钱在变多），比值无意义 */
  daily_use_rate_zero_reason: string | null
  /** 日均窗口的实际覆盖天数（阶段刚开时远小于 30） */
  avg_daily_sample_days: number
  /** 该窗口内的**真实**日均 —— 样本不足时它远大于被稀释的 `pool.avg_daily` */
  avg_daily_sample_net_per_day: number
  /** `avg_daily_sample_days < 30` ⇒ 均值偏低、「撑到哪天」偏乐观，必须在页面上说出来 */
  avg_daily_sample_thin: boolean
}

/** 子阶段行。**达标率是那个小阶段的**，不是长阶段的判定结果 ——
 *  长阶段只汇总、不判定（它没有 `SelfRunPeriod`）。 */
export interface LedgerChild {
  id: number
  name: string
  range_label: string
  status_display: string
  /** 命中次数（达目标或达底线） */
  hit: number
  /** 有判定的次数 */
  judged: number
  /** `hit / judged`；`null` = 还没有任何一期被判定过（**不是 0%**） */
  reach_rate: number | null
}

/** 账本「作品」格里的一件 —— 就是这一格里那个数字的**依据**。
 *
 * 🔴 `created_at` 是**成形那一刻**（合成时的本地时间），不是那件事发生的日期；
 *    弹窗里要显示到分钟，用户才能自己看出它落在阶段区间的哪一刻。
 */
export interface LedgerWorkItem {
  id: number
  name: string
  /** 类型显示词（后端 `get_kind_display()`） */
  kind: string
  /** 出口状态显示词（后端 `get_status_display()`） */
  status: string
  summary: string
  /** 空串 = 「要发但还没定发到哪」，与「只给自己」不是一回事 */
  channel: string
  created_at: string
}

export interface StageLedger {
  stage_id: number
  range: LedgerRange
  time: LedgerTime
  money: LedgerMoney
  /**
   * `count` 与 `items` **出自同一次取数**，所以 `items.length` 只会因为
   * `truncated` 而小于 `count` —— 绝不会出现「写着 2 件、列出 3 条」。
   */
  works: {
    count: number
    items: LedgerWorkItem[]
    /** 明细最多列几条（后端下发，前端不写死第二套上限） */
    limit: number
    /** 超出上限 ⇒ 弹窗必须说「还有 N 件」，不能让人以为就这些 */
    truncated: boolean
  }
  children: LedgerChild[]
}

/**
 * `support_zero_reason` 的显示词 —— **只查表，不猜语义**。
 *
 * 后端把原因码给出来，前端只负责翻译；以后多一种「算不出来」的原因时，
 * 这里漏加只会显示 `—`，而不会像 `|| '永不耗尽'` 那样**静默说反话**。
 */
export const SUPPORT_ZERO_LABEL: Record<string, string> = {
  no_self_expense: '算不出来',
  // 🔴 净流入不是「算不出来」，是一个结论：钱在变多，没有耗尽日
  net_inflow: '钱在变多',
}

/** 每个原因码配一句人话（解释为什么算不出来，并指出去哪补） */
export const SUPPORT_ZERO_HINT: Record<string, string> = {
  no_self_expense: '这段路还没有一条「为自己」的账，没有每天的消耗速度可外推 —— 撑多久算不出来。',
  net_inflow: '近 30 天是净流入：进来的比花的多，池子在涨，不存在「撑到哪天」。',
}

/** `daily_use_rate_zero_reason` 的显示词 —— 两种「没有比值」也要分开说 */
export const USE_RATE_ZERO_LABEL: Record<string, string> = {
  no_allowance: '—',
  net_inflow: '净流入',
}

/** `daily_allowance_zero_reason` 的显示词 —— 两种「空」，别都说成算不出来 */
export const ALLOWANCE_ZERO_LABEL: Record<string, string> = {
  no_principal: '未设本金',
  no_day_left: '已到最后一天',
}

// ══════════════════════════════════════════════════════════════
// 八、归一化小工具
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

/** 复盘补充：本期到期里程碑 + 本期时间流失（后端现算，不落库） */
export interface PeriodGoalItem {
  id: number
  title: string
  goal: string
  target_date: string | null
  status: string
}

/** 一期内「具体做过的事」的一条（L3 任务名 + 时长 + 归因） */
export interface WhatHappenedItem {
  task_name: string
  hours: number
  /** 六词归因；空串 = 没解析出来（不是「未归类」，那种情况后端会给 `未归类`） */
  attribution: string
}

export interface WhatHappenedDay {
  date: string
  /** `10/26` —— 后端给，前端不拼（同一份日期格式只留一处） */
  md: string
  /** `周一` —— 周历表只在后端一份 */
  weekday: string
  total_hours: number
  items: WhatHappenedItem[]
  /** 没列出来的还有几件 —— 让「3 件」看起来是节选，不像「这周只做了 3 件」 */
  more: number
}

/** 时段轴的一块：某人某天从第几分钟到第几分钟做了什么事。
 *
 * 🔴 只有**分钟**，没有时间串 —— 拿到 `'09:00'` 就会有人 `new Date()`，
 *    而 `USE_TZ` 下那会差 8 小时，且结果看起来完全合法（块还是在个合理位置）。
 */
export interface WhatHappenedBlock {
  /** 本地日期 `2026-10-26` —— 只用来找列，不当时间解析 */
  date: string
  /** 当天第几分钟（0–1440） */
  from: number
  to: number
  minutes: number
  task_name: string
  /** 六词归因；空串 = 没解析出来（配色查 `ATTRIBUTION_COLOR_MAP`） */
  attribution: string
  /** `null` = 完整；`head`/`tail` = 被午夜切出来的前/后段；`mid` = 中间整天 */
  split: 'head' | 'tail' | 'mid' | null
}

/** 时间轴的一列 = 一天。没记录的天也在，否则「周三空着」看不出来 */
export interface WhatHappenedColumn {
  date: string
  /** `10/26` */
  md: string
  /** `周一` */
  weekday: string
}

export interface WhatHappened {
  days: WhatHappenedDay[]
  /** 有记录的天数（≠ 周期天数） */
  day_count: number
  /** 各归因的小时合计，按价值序（后端给顺序，前端不排） */
  attr_totals: { label: string; hours: number }[]
  /** 周期内**每一天** —— 时间轴的列 */
  columns: WhatHappenedColumn[]
  /** 原始区间：一条记录一块，跨天切成多块（与 `days` 不合并的口径不同） */
  blocks: WhatHappenedBlock[]
  /** 块覆盖的分钟范围；`null` = 本期一块都没有 */
  span: { from: number; to: number } | null
  /** 因上限被丢掉的块数（0 = 没丢）。非 0 必须显式告诉用户 */
  truncated: number
}

/** 成果卡的一行：三栏共用「有名字 + 哪一天 + 从哪来」这套骨架。
 *
 * 🔴 日期只有后端给的 `date` / `md` / `weekday` 三件套 —— 拿到时间串就有人
 *    `new Date()`，`USE_TZ` 下会差 8 小时且结果看着完全合法。
 */
export interface OutcomeRow {
  id: number
  /** 成品 = 作品名；里程碑 = 里程碑标题；办完的事 = 小确幸标题或收件箱内容 */
  title: string
  /** 只成品有：作品类型显示词（文章 / 绘画作品 …） */
  kind?: string
  /** 只成品有：出口状态显示词（只给自己 / 已发 …） */
  status?: string
  /** 只里程碑有：属于哪个目标 */
  goal?: string
  date: string
  md: string
  weekday: string
  /** 只「办完的事」有：这一条从哪来（`both` = 两处都记过，只出一行） */
  source?: 'sugar' | 'inbox' | 'both'
  /** 只「办完的事」有：小确幸档位词/色，后端从 `SUGAR_HAPPINESS_BANDS` 给 */
  happiness_label?: string | null
  happiness_color?: string | null
}

/** 一栏：`count` 是全量、`items` 可能被截断（截断时 `truncated=true`） */
export interface OutcomeColumn {
  count: number
  items: OutcomeRow[]
  limit: number
  truncated: boolean
}

/** 「这一期干成了什么」—— **三栏各报各的数，没有跨源总数**。
 *
 * 同一件事可能既是作品又在小确幸里记过（10-18 那篇文章两处都有），
 * 合并成一个数就是重复计数，而且没法回头去重。
 */
export interface PeriodOutcomes {
  /** 出了成品（作品库，按「成形于」） */
  works: OutcomeColumn
  /** 完成了里程碑（与复盘「缺口」卡同源，不另查一次） */
  milestones: OutcomeColumn
  /** 办完的事 = 小确幸（只 `秩序型`）+ 收件箱 `done`，按标题归一去重 */
  finished: OutcomeColumn & {
    /** 本期**没标快乐类型**的小确幸条数 —— 不是「没完成」，是「没分类」 */
    untyped_count: number
  }
  /** 三栏全 0 ⇒ 整卡不渲染（不是渲染三行 0） */
  empty: boolean
}

export interface PeriodExtras {
  period_type: PeriodType
  /** 这一周我做了什么 —— 按天分组的具体任务（勾回忆用） */
  what_happened: WhatHappened
  goals: {
    /** 本期到期（target_date 落在本期）的里程碑数 */
    due: number
    /** 其中已完成的 */
    done: number
    /** 该交没交的（`due - done`）——「本期新增逾期」，这才是本周的账 */
    missed: number
    /** 本期之前到期、至今仍未完成的（历史积压）—— 跨周恒定，只做背景说明 */
    overdue: number
    items: PeriodGoalItem[]
  }
  time_loss: {
    loss_hours: number
    total_hours: number
    /** 流失占全部记录小时的比例；`null` = 本期没有任何时间记录（≠ 0%） */
    ratio: number | null
    per_day: number
    days: number
    top: { task_name: string; hours: number }[]
  }
  /** 这一期干成了什么 —— 投入之外的**产出**视角（三栏，不给跨源总数） */
  outcomes: PeriodOutcomes
}