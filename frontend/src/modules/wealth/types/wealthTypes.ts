/** 周级别净收入等级 */
export type NetLevel =
  | 'surplus_high' | 'surplus_mid' | 'surplus_low'
  | 'zero'
  | 'deficit_low' | 'deficit_mid' | 'deficit_high'

/** 周历条目 */
export interface WeekCalendarEntry {
  global_week_index: number
  age_year: number
  week_number: number
  week_start_date: string
  week_end_date: string
  is_lived: boolean
  income: number
  expense: number
  net: number
  net_level: NetLevel
}

/** 当前推演状态 */
export interface CurrentScenario {
  id: number
  snapshot_time: string
  current_age: number
  current_week: number
  current_cash: string
  daily_budget: string
  support_weeks: number
  end_age: number | null
  end_week: number | null
}

/** 当前位置（第几岁第几周）—— 后端**读周历表**得出，前端不得自行推算 */
export interface CurrentAgeWeek {
  current_age: number
  current_week: number
  /** 含今天那一行的全局索引（推演起点） */
  global_week_index: number
  /** 窗口（19–60 岁）内已度过周数 —— 与页头 summary.lived_weeks 同源同值 */
  lived_weeks: number
  /** 位置来源：周历表 / 按出生日期估算（周历尚未初始化时的回落） */
  source: 'calendar' | 'birthdate'
  birth_date: string
}

/** 推演输入 */
export interface CoverageInput {
  current_age: number
  current_week: number
  current_cash: number
  daily_budget: number
  daily_interest_rate?: number
}

/** 反算输入：本金 + 目标天数 → 每日可提取额（纯试算，不写库） */
export interface BudgetInput {
  current_cash: number
  /** 天数，由前端按单位（年/月/天）换算后传入 */
  target_days: number
  daily_interest_rate?: number
}

/** 反算结果 */
export interface BudgetResult {
  daily_budget: number
  target_days: number
  current_cash: number
  daily_interest_rate: number
}

/** 推演结果 */
export interface CoverageResult {
  coverage_weeks: number[]
  support_weeks: number
  end_age: number | null
  end_week: number | null
  daily_interest_rate?: number
  /** 计量窗口（19–60 岁）：推演上限，跑满窗口未耗尽即视为覆盖至窗口末端 */
  window_start_age?: number
  window_end_age?: number
  window_weeks?: number
  reached_window_end?: boolean
}

/** 人生总览 */
export interface LifeSummary {
  total_income: number
  total_expense: number
  total_net: number
  surplus_rate: number
  lived_weeks: number
  surplus_weeks: number
  deficit_weeks: number
  /** 计量窗口（19–60 岁）：以上指标均在此窗口内统计 */
  window_start_age?: number
  window_end_age?: number
  window_weeks?: number
}

/** 账单条目 */
export interface BillItem {
  id: number
  transaction_type: string
  category: string
  subcategory: string | null
  amount: number
  date: string
  note: string | null
}

/** 按周账单响应 */
export interface BillsByWeekResponse {
  week_index: number
  week_start: string
  week_end: string
  bills: BillItem[]
}

/** 周历查询参数 */
export interface CalendarQueryParams {
  user_id?: number
  age?: number
  lived_only?: boolean
}

/** 周历数据索引映射 */
export interface WeekDataMap {
  [globalWeekIndex: number]: WeekCalendarEntry
}

/** 覆盖周集合 */
export type CoverageSet = Set<number>

/** 月度日级别颜色等级 */
export type MonthlyColorLevel =
  | 'income_high' | 'income_mid' | 'income_light'
  | 'neutral'
  | 'expense_light' | 'expense_mid' | 'expense_high'

/** 月度日历中的单日 */
export interface MonthlyDay {
  date: string
  day: number
  income: number
  expense: number
  net: number
  summary_text: string
  color_level: MonthlyColorLevel
}

/** 月度日历 */
export interface MonthlyCalendar {
  year: number
  month: number
  days: MonthlyDay[]
}

/** 单笔完整账单 */
export interface FullBillItem {
  id: number
  transaction_type: string
  category: string
  subcategory: string | null
  amount: number
  project: string | null
  account: string | null
  merchant: string | null
  notes: string | null
  date: string
}

/** 单日明细 */
export interface DailyDetail {
  income_total: number
  expense_total: number
  net: number
  income_list: FullBillItem[]
  expense_list: FullBillItem[]
}

/** 分类汇总 */
export interface CategorySummary {
  category: string
  amount: number
}

/** 月度汇总 */
export interface MonthlySummary {
  total_income: number
  total_expense: number
  balance: number
  avg_daily_expense: number
  max_daily_income: number
  max_daily_expense: number
  expense_top3: CategorySummary[]
  income_top3: CategorySummary[]
}

/** 记账表单数据 */
export interface BillCreateData {
  transaction_type: '收入' | '支出'
  amount: number
  category: string
  subcategory?: string
  project?: string
  account?: string
  merchant?: string
  notes?: string
  date: string
  user_id?: number
}

// ══════════════════════════════════════════
// 月度复盘类型
// ══════════════════════════════════════════

/** 月度复盘汇总 */
export interface MonthlyReview {
  year: number
  month: number
  month_name: string
  income: number
  expense: number
  balance: number
  savings_rate: number
  avg_daily_expense: number
  max_daily_income: number | null
  max_daily_expense: number | null
  max_daily_income_detail: { amount: number; date: string } | null
  max_daily_expense_detail: { amount: number; date: string } | null
  deposit: number | null
  /** 余额来源：`asset_snapshot` 取资产盘点该月净值 / `legacy` 历史手填 / `null` 无数据
   *  🔴 前端**按这个键**决定怎么标注，不按值猜（v3.60.14 收口）。 */
  deposit_source: 'asset_snapshot' | 'legacy' | null
  /** 来源为 `asset_snapshot` 时的盘点日期（`YYYY-MM-DD`） */
  deposit_as_of: string | null
  notes: string
  from_balance_list: boolean
  mom_change: {
    income: number | null
    expense: number | null
    balance: number | null
  }
}

/** 趋势数据项 */
export interface TrendItem {
  yearmon: string
  income: number
  expense: number
  balance: number
  savings_rate: number
  deposit: number | null
}

/** 分类排行项 */
export interface CategoryRankingItem {
  category: string
  amount: number
  percentage: number
}

/** 历史复盘列表项 */
export interface MonthlyListItem {
  yearmon: string
  income: number
  expense: number
  balance: number | null
  /** 存款余额：资产盘点该月净资产优先，无快照时回落历史手填值 */
  deposit: number | null
  /** 见 `MonthlyReview.deposit_source`。列表用它决定要不要标「手填」 */
  deposit_source: 'asset_snapshot' | 'legacy' | null
  deposit_as_of: string | null
  savings_rate: number
  notes: string
}

/** 历史复盘列表 */
export interface MonthlyListData {
  items: MonthlyListItem[]
  total: number
  page: number
  page_size: number
}

/** 同比环比分析 */
export interface CompareData {
  current: {
    yearmon: string
    income: number
    expense: number
    balance: number
    savings_rate: number
  }
  mom: {
    yearmon: string
    income: number
    expense: number
    balance: number
    income_change: number | null
    expense_change: number | null
    balance_change: number | null
  }
  yoy?: {
    yearmon: string
    income: number
    expense: number
    balance: number
    income_change: number | null
    expense_change: number | null
    balance_change: number | null
  }
}

/** 复盘编辑表单数据 */
export interface BalanceInfoFormData {
  yearmon: string
  income: number
  expense: number
  balance?: number | null
  notes?: string
}

// ══════════════════════════════════════════
// 资产盘点类型（资产负债表口径）
// ══════════════════════════════════════════

/** 账户余额 */
export interface AccountBalances {
  zplay: number
  wechat: number
  cash: number
  jianbank: number
  gongbank: number
  zhongbank: number
  nongbank: number
  accumulationfund: number
}

/** 资产汇总
 * total / financial_assets = 活期账户 + 公积金
 * total_assets             = financial_assets + 应收借出
 * net_worth                = total_assets − 负债（与 realnum 同值，realnum 为兼容保留）
 */
export interface AssetSummary {
  flow_total: number
  total: number
  financial_assets: number
  total_assets: number
  net_worth: number
  borrow: number
  lend: number
  realnum: number
}

/**
 * 月支出的三点估算 —— 应急金月数的分母（v3.58.24）
 *
 *   E = (O + 4M + P) ÷ 6，O=最小月、M=中位数、P=最大月
 *   窗口 = 锚定月**之前**的 12 个完整月（不含盘点当月）
 *
 * ⚠️ value 为 null 表示**样本不足**，不是 0。
 *    0 是结论（月支出为零 ⇒ 应急金无穷），null 是「算不出来」。
 */
export interface ExpenseEstimate {
  value: number | null
  optimistic: number | null
  likely: number | null
  pessimistic: number | null
  /** 算术平均 —— 只作对照展示，不参与估算 */
  mean: number | null
  median: number | null
  months_with_records: number
  months_required: number
  window_months: number
  anchor_yearmon: string | null
  ym_keys: number[]
  detail: { ym_key: number; year: number; month: number; amount: number }[]
  reason: string | null
}

/** 资产健康指标
 * 应急金以「月数」判定；月支出估算不出时 emergency_* 派生字段为 null
 * debt_ratio_legacy 为修正前的分母口径，仅供对照，不用于展示
 */
export interface HealthMetrics {
  emergency_fund: number
  emergency_fund_months: number | null
  emergency_months_target: number
  /** 应急金月数的判定级别 —— 后端按 RATIO_BANDS 给出，前端不再自己算 target/2 */
  emergency_months_level: RatioLevel
  emergency_months_level_label: string | null
  /** 目标完成度（0–100），后端算好 —— 前端不做除法 */
  emergency_months_pct: number | null
  emergency_target_amount: number | null
  emergency_gap: number | null
  /** 分母的完整三点估算（O / M / P / E 与样本量）—— 气泡里要给得起细节 */
  expense_estimate: ExpenseEstimate
  monthly_expense_window: number
  expense_basis_yearmon: string | null
  liquidity_ratio: number
  /** 活期占比的判定级别 —— 与比率面板共用 constants.RATIO_BANDS 一张表 */
  liquidity_ratio_level: RatioLevel
  liquidity_ratio_level_label: string | null
  debt_ratio: number
  debt_ratio_level: RatioLevel
  debt_ratio_level_label: string | null
  debt_ratio_legacy: number
  provident_fund_ratio: number
  provident_fund_ratio_level: RatioLevel
  provident_fund_ratio_level_label: string | null
}

/** 资产全景 */
export interface CashFlowOverview {
  snapshot_date: string | null
  yearmon: string | null
  accounts: AccountBalances
  summary: AssetSummary
  health_metrics: HealthMetrics
}

/** 资产趋势项 */
export interface AssetTrendItem {
  yearmon: string
  flow_total: number
  total: number
  financial_assets: number
  total_assets: number
  net_worth: number
  accumulationfund: number
  zplay: number
  wechat: number
  jianbank: number
  gongbank: number
  zhongbank: number
  nongbank: number
  borrow: number
  lend: number
}

/** 盘点历史项 */
export interface SnapshotListItem {
  baid: number
  yearmon: string | null
  btime: string | null
  flow_total: number
  total: number
  financial_assets: number
  total_assets: number
  net_worth: number
  zplay: number
  wechat: number
  cash: number
  jianbank: number
  gongbank: number
  zhongbank: number
  nongbank: number
  accumulationfund: number
  realnum: number
  borrow: number
  lend: number
  remarks: string
}

/** 盘点历史列表 */
export interface SnapshotListData {
  items: SnapshotListItem[]
  total: number
  page: number
  page_size: number
}

/** 盘点快照表单 */
export interface SnapshotFormData {
  yearmon: string
  btime?: string
  zplay?: number
  wechat?: number
  cash?: number
  jianbank?: number
  gongbank?: number
  zhongbank?: number
  nongbank?: number
  accumulationfund?: number
  lend?: number
  borrow?: number
  remarks?: string
}

// ══════════════════════════════════════════
// 定期存款类型
// ══════════════════════════════════════════

/** 定期存款记录 */
export interface RegularItem {
  id: number
  begin_date: string
  end_date: string
  value: number
  flag: number
  flag_label: string
  interest: number | null
  remark: string | null
  bankinfo: string | null
  rate: number | null
  term_days: number
  calculated_interest: number
}

/** 定期存款统计 */
export interface RegularStats {
  total_value: number
  total_interest: number
  ongoing_value: number
  matured_value: number
  withdrawn_value: number
  ongoing_count: number
  matured_count: number
  withdrawn_count: number
  expiring_soon_count: number
  expired_count: number
}

/** 定期存款表单数据 */
export interface RegularFormData {
  begin_date: string
  end_date: string
  value: number
  rate?: number | null
  bankinfo?: string
  remark?: string
  interest?: number | null
}

/** 到期处理表单 */
export interface MatureProcessData {
  action: 'withdraw' | 'renew' | 'renew_all'
  new_rate?: number | null
  new_end_date?: string | null
}

/** 到期提醒项 */
export interface ExpiringItem {
  id: number
  bankinfo: string | null
  value: number
  end_date: string
  days_left: number
  status: 'expired' | 'due_soon_7' | 'due_soon_30' | 'normal'
}

/** 到期状态配置 */
export const EXPIRING_STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  expired: { label: '已过期', color: '#EF4444', bg: '#FEE2E2' },
  due_soon_7: { label: '7天内到期', color: '#F59E0B', bg: '#FEF3C7' },
  due_soon_30: { label: '30天内到期', color: '#3B82F6', bg: '#DBEAFE' },
  normal: { label: '正常', color: '#10B981', bg: '#D1FAE5' },
}

/** 存款状态选项 */
export const FLAG_OPTIONS = [
  { value: -1, label: '全部状态' },
  { value: 0, label: '未到期' },
  { value: 1, label: '已到期' },
  { value: 2, label: '已取出' },
] as const

// ══════════════════════════════════════════
// 三年赎回期 · 账单赎回归属标记
// ══════════════════════════════════════════

/** 赎回归属四档（上线版，跑 2 个月复盘后可能拆「过渡」）
 *  ⚠️ 与时间侧的 L1 归因（成长/谋生/维持/流失）**不是同一把尺子**：
 *  这边问「这笔钱服务哪个阶段/对象」，时间侧问「这段时间的价值归向」。切勿互换。 */
export const PERIOD_TAGS = ['为自己', '过渡', '为别人', '不计入'] as const
export type PeriodTag = (typeof PERIOD_TAGS)[number]

/** 赎回归属标签/配色（涨红跌绿之外的独立语义色） */
export const PERIOD_TAG_META: Record<string, { label: string; color: string; bg: string }> = {
  为自己: { label: '为自己', color: '#7C3AED', bg: '#F3E8FF' },
  过渡: { label: '过渡', color: '#2563EB', bg: '#DBEAFE' },
  为别人: { label: '为别人', color: '#D97706', bg: '#FEF3C7' },
  不计入: { label: '不计入', color: '#6B7280', bg: '#F3F4F6' },
  unmarked: { label: '未标记', color: '#9CA3AF', bg: '#F3F4F6' },
}

/** 赎回归属筛选下拉选项 */
export const PERIOD_TAG_FILTER_OPTIONS = [
  { label: '未标记', value: 'unmarked' },
  ...PERIOD_TAGS.map((t) => ({ label: t, value: t })),
]

/** 赎回归属小结项 */
export interface PeriodTagStat {
  period_tag: string
  count: number
  total: number
}

// ══════════════════════════════════════════
// 负债明细 / 应收账龄（P1-A，v3.58.20）
//
// 账龄桶的**边界与标签一律由后端下发**（constants.RECEIVABLE_AGING_BUCKETS），
// 前端只按返回顺序渲染，不在此重定义天数阈值 —— 两处各写一份必然漂移。
// 这里只留「未填借出日」这一个字面量，用于在分布条上做特殊着色的判断。
// ══════════════════════════════════════════

/** 与后端 AGING_UNKNOWN_BUCKET 逐字一致 */
export const AGING_UNKNOWN_BUCKET = '未填借出日'

export const LIABILITY_CATEGORIES = ['信用卡', '消费贷', '房贷', '车贷', '亲友借款', '其他'] as const
export const REPAYMENT_METHODS = ['等额本息', '等额本金', '先息后本', '随借随还', '一次性还本'] as const
export const LIABILITY_STATUSES = ['在还', '已结清'] as const
export const RECEIVABLE_STATUSES = ['在借', '已收回', '呆账'] as const

/** 负债明细项（含派生：已还本金 / 年利息成本 / 还款优先级） */
export interface LiabilityItem {
  id: number
  name: string
  category: string
  principal: number
  outstanding: number
  annual_rate: number
  start_date: string | null
  due_date: string | null
  repayment_method: string
  monthly_payment: number
  status: string
  remark: string
  repaid_amount: number
  repaid_ratio: number
  annual_interest_cost: number
  remaining_months: number | null
  days_to_due: number | null
  /** 雪崩法序位（利率降序），已结清为 null */
  priority_by_rate: number | null
  /** 雪球法序位（余额升序），已结清为 null */
  priority_by_balance: number | null
  created_at: string | null
  updated_at: string | null
}

/** 负债分类分布项 */
export interface LiabilityCategoryStat {
  category: string
  count: number
  outstanding: number
  monthly_payment: number
  share: number
}

/** 负债汇总（含与最新快照 borrow 的对账差） */
export interface LiabilitySummary {
  as_of: string
  count: number
  active_count: number
  settled_count: number
  total_principal: number
  total_outstanding: number
  total_monthly_payment: number
  weighted_avg_rate: number
  highest_rate_item: { name: string; annual_rate: number } | null
  annual_interest_cost: number
  by_category: LiabilityCategoryStat[]
  prepay_focus: { by_rate: string | null; by_balance: string | null }
  snapshot_borrow: number | null
  /** 台账剩余本金 − 快照 borrow，正数表示台账多于快照 */
  borrow_diff: number | null
}

/** 负债新增/编辑表单 */
export interface LiabilityFormData {
  id?: number
  name: string
  category?: string
  principal?: number
  outstanding?: number
  annual_rate?: number
  start_date?: string | null
  due_date?: string | null
  repayment_method?: string
  monthly_payment?: number
  status?: string
  remark?: string
}

/** 应收借出明细项（含派生：未收回余额 / 账龄 / 逾期） */
export interface ReceivableItem {
  id: number
  counterparty: string
  principal: number
  received: number
  outstanding: number
  recovery_ratio: number
  lend_date: string | null
  due_date: string | null
  annual_rate: number
  status: string
  remark: string
  aging_days: number | null
  aging_bucket: string
  is_long_aging: boolean
  is_overdue: boolean
  overdue_days: number
  annual_interest_income: number
  created_at: string | null
  updated_at: string | null
}

/** 账龄分布桶 */
export interface AgingBucket {
  bucket: string
  count: number
  amount: number
  share: number
}

/** 应收汇总（含与最新快照 lend 的对账差） */
export interface ReceivableSummary {
  as_of: string
  count: number
  active_count: number
  bad_debt_count: number
  total_lent: number
  total_received: number
  total_outstanding: number
  active_outstanding: number
  bad_debt_amount: number
  recovery_ratio: number
  overdue_count: number
  overdue_amount: number
  max_overdue_days: number
  long_aging_count: number
  interest_income_annual: number
  interest_free_amount: number
  interest_free_ratio: number
  aging: AgingBucket[]
  snapshot_lend: number | null
  /** 未收回余额合计 − 快照 lend，正数表示台账多于快照 */
  lend_diff: number | null
}

/** 应收借出新增/编辑表单 */
export interface ReceivableFormData {
  id?: number
  counterparty: string
  principal?: number
  received?: number
  lend_date?: string | null
  due_date?: string | null
  annual_rate?: number
  status?: string
  remark?: string
}

// ══════════════════════════════════════════
// 资产科目主数据 / 资产快照（P1-B，v3.58.21）
//
// 两个正交维度，不要混用：
//   category  —— 财务规划上的资产类别，回答「这是什么资产」；
//   is_liquid —— 应急金可用性，回答「能不能马上用」。
//   公积金是「category=流动性 但 is_liquid=false」的典型，不是数据错误。
// ══════════════════════════════════════════

export const ASSET_CATEGORIES = ['流动性', '投资性', '应收', '自用'] as const
export const ASSET_ACCOUNT_KINDS = [
  '第三方支付', '现金', '储蓄卡', '公积金',
  '证券账户', '基金', '保险', '房产', '车辆', '其他',
] as const
/** 新建科目时「不计入资产负债表」的建议默认类别 —— 后端可改，前端只作默认勾选 */
export const ASSET_DEFAULT_EXCLUDE_CATEGORIES: readonly string[] = ['自用']

/** 资产科目（主数据） */
export interface AssetAccountItem {
  id: number
  /** 映射码 = 旧表列名，用于旧快照回填时对应；手工新增的科目为空 */
  code: string | null
  name: string
  category: string
  account_kind: string
  institution: string
  is_liquid: boolean
  include_in_balance_sheet: boolean
  sort: number
  is_active: boolean
  note: string
  /** 被多少期快照引用 —— >0 时科目不可删除，只能停用 */
  used_snapshot_count: number
  created_at: string | null
  updated_at: string | null
}

export interface AssetCategoryStat {
  category: string
  count: number
  counted: number
  liquid: number
}

/** 科目结构汇总（主数据无金额，只统计结构） */
export interface AssetAccountSummary {
  total: number
  active_count: number
  inactive_count: number
  liquid_count: number
  counted_count: number
  excluded_count: number
  used_count: number
  by_category: AssetCategoryStat[]
}

export interface AssetAccountFormData {
  id?: number
  code?: string | null
  name: string
  category?: string
  account_kind?: string
  institution?: string
  is_liquid?: boolean
  include_in_balance_sheet?: boolean
  sort?: number
  is_active?: boolean
  note?: string
}

export interface SeedResult {
  created: number
  kept: number
  updated: number
  total: number
  overwrite: boolean
}

/** 快照明细行（读，已带科目属性快照） */
export interface AssetSnapshotItemRow {
  account_id: number
  code: string | null
  name: string
  category: string
  account_kind: string
  is_liquid: boolean
  include_in_balance_sheet: boolean
  amount: number
}

/** 资产快照：头 + 汇总恒等式 + 可选明细行
 *
 * 恒等式（后端锁死，前端不做除法也不重算）：
 *   total_assets        = financial_assets + self_use_total
 *   net_worth           = total_assets − borrow
 *   available_net_worth = financial_assets − borrow（剔除自用，「能变成钱的净值」）
 */
export interface AssetSnapshotRow {
  id: number
  yearmon: string
  snapshot_date: string | null
  /** 快照头的借出汇总，只作对账参考，不参与合计 */
  lend: number
  remarks: string
  /** 应收类科目合计 − lend；非 0 表示台账与快照没对上（只提示，不自动改） */
  receivable_gap: number
  liquid_total: number
  /** 恒 4 个键，缺失的类别补 0 */
  category_totals: Record<string, number>
  financial_assets: number
  self_use_total: number
  total_assets: number
  borrow: number
  net_worth: number
  available_net_worth: number
  /** 不计入资产负债表的科目合计（如默认的自用资产），单独提示不静默吞掉 */
  excluded_total: number
  counted_count: number
  item_count: number
  created_at: string | null
  updated_at: string | null
  /** 仅详情接口返回；列表刻意不带明细 */
  items?: AssetSnapshotItemRow[]
}

export interface AssetSnapshotWriteItem {
  account_id: number
  amount: number
}

export interface AssetSnapshotFormData {
  yearmon: string
  snapshot_date?: string | null
  borrow?: number
  lend?: number
  remarks?: string
  items: AssetSnapshotWriteItem[]
}


/* ══════════════════════════════════════════════════════════════
 * 账单项分类规则 / 归类结果（P1-C）
 *
 * 一张规则表服务三个维度：收入性质 / 支出刚性 / 现金流类别。
 * 常量与后端 apps/wealth/constants.py 一一对应 —— 改后端务必同步改这里，
 * 否则会出现「下拉里选得到、后端 400」或反之。
 * ══════════════════════════════════════════════════════════════ */

/** 可匹配的账单项字段（顺序即下拉顺序；具体度 商户 > 子分类 > 分类） */
export const CLASSIFY_RULE_FIELDS = [
  { value: 'category', label: '分类' },
  { value: 'subcategory', label: '子分类' },
  { value: 'merchant', label: '商户' },
] as const

/** 收入性质：主动 = 出卖时间换来；被动 = 资产产生；一次性 = 不可复现 */
export const INCOME_TYPES = ['主动', '被动', '一次性'] as const
/** 支出刚性：固定 = 不花就出事；可变 = 不花也能活 */
export const EXPENSE_NATURES = ['固定', '可变'] as const
/** 现金流五类归集 */
export const CASHFLOW_CLASSES = [
  '收入流入', '必需支出', '品质支出', '投资支出', '债务偿还',
] as const
/** 五类按收支方向分组：收入行只认收入侧的类，支出行只认支出侧的类 */
export const CASHFLOW_INCOME_CLASSES: readonly string[] = ['收入流入']
export const CASHFLOW_EXPENSE_CLASSES: readonly string[] = [
  '必需支出', '品质支出', '投资支出', '债务偿还',
]

/** 分类规则 */
export interface ClassifyRuleItem {
  id: number
  rule_field: string
  match_value: string
  income_type: string | null
  expense_nature: string | null
  cashflow_class: string | null
  priority: number
  is_active: boolean
  note: string
  updated_at: string
}

export interface ClassifyRuleFormData {
  id?: number
  rule_field: string
  match_value: string
  income_type?: string | null
  expense_nature?: string | null
  cashflow_class?: string | null
  /** 留空则由后端按匹配字段的具体度取默认值 */
  priority?: number | null
  is_active?: boolean
  note?: string
}

export interface ClassifyRuleSummary {
  total: number
  active: number
  inactive: number
  by_field: Record<string, number>
  by_dimension: Record<string, number>
  default_priority: Record<string, number>
  field_specificity: Record<string, number>
}

export interface SeedClassifyResult {
  created: number
  updated: number
  skipped: number
  total: number
  overwrite: boolean
}

/** 影响预览的样本行：同一条账单的标签「改前 / 改后」对照 */
export interface ClassifyPreviewSample {
  date: string
  category: string
  subcategory: string
  merchant: string
  transaction_type: string
  amount: number
  before: Record<string, string | null> | null
  after: Record<string, string | null> | null
}

/**
 * 候选规则影响预览
 *
 * ⚠️ `matched_count`（命中多少）与 `changed_count`（真正改动多少）是两件事：
 *    低优先级的候选规则可能命中一大片却一条都改不动。看影响面要看后者。
 */
export interface ClassifyPreview {
  rule_field: string
  match_value: string
  priority: number
  matched_count: number
  matched_amount: number
  changed_count: number
  changed_amount: number
  by_transaction_type: Record<string, number>
  samples: ClassifyPreviewSample[]
  period_label: string
}

export interface ClassifyIncomeBlock {
  total: number
  count: number
  by_type: Record<string, number>
  unclassified: number
}

export interface ClassifyExpenseBlock {
  total: number
  count: number
  by_nature: Record<string, number>
  unclassified: number
}

/** 三个维度各自的覆盖率 —— 分母各不相同（收入/支出/收支合计），不要互相比较 */
export interface ClassifyCoverage {
  income_type: number
  expense_nature: number
  cashflow_class: number
}

/** 被排除的收支类型（转入 / 转出 / 余额变更）—— 显式列出，不静默丢弃 */
export interface ClassifyExcluded {
  transaction_type: string
  count: number
  amount: number
}

export interface ClassifySummary {
  yearmon: string | null
  period_label: string
  bill_count: number
  bill_amount: number
  income: ClassifyIncomeBlock
  expense: ClassifyExpenseBlock
  cashflow: Record<string, number>
  coverage: ClassifyCoverage
  excluded: ClassifyExcluded[]
}

/** 未归类候选（按 分类/子分类 聚合）—— 回答「下一条规则建在哪儿」 */
export interface UnclassifiedGroup {
  category: string
  subcategory: string
  count: number
  amount: number
  transaction_types: string[]
  missing_dimensions: string[]
  suggested_field: string
  suggested_value: string
  merchant_samples: string[]
}

export interface UnclassifiedCandidates {
  yearmon: string | null
  period_label: string
  total_count: number
  total_amount: number
  items: UnclassifiedGroup[]
}

/* ══════════════════════════════════════════════════════════════
 * 财务规划比率（P2-A）
 *
 * 🔴 后端是判定线的唯一真源：`RATIO_BANDS`（apps/wealth/constants.py）
 *    连同**区间本身**一起下发，前端只负责上色与画刻度 ——
 *    这里不允许出现任何阈值数字（如 `>= 6`、`< 30`）。
 *    改动阈值只需改后端常量，前端零改动。
 * ══════════════════════════════════════════════════════════════ */

/** 判定级别 —— good / warn / danger / normal，与后端 _ratio.level 一致 */
export type RatioLevel = 'good' | 'warn' | 'danger' | 'normal' | null

/** 一条判定区间：[下界, 上界|null, level, 中文标签] */
export type RatioBand = [number, number | null, Exclude<RatioLevel, null>, string]

/** 比率的分子 / 分母 —— 回答「这个数怎么来的」 */
export interface RatioLeg {
  label: string
  value: number | null
}

export interface RatioItem {
  key: string
  label: string
  unit: string
  /** higher_better / lower_better / neutral（neutral 表示只看方向不设区间） */
  direction: string
  formula: string
  value: number | null
  /** 判定区间，后端下发；为 null 表示该指标「看趋势不看绝对值」 */
  bands: RatioBand[] | null
  target: number | null
  level: RatioLevel
  level_label: string | null
  numerator: RatioLeg | null
  denominator: RatioLeg | null
  /** false 时 value 必为 null，原因见 reason；**不要把它当成 0** */
  available: boolean
  reason: string | null
  /** 定性提示，**不含金额**（金额要走 formatAmount 脱敏） */
  hint: string
  extra: Record<string, unknown>
}

/** 比率用到的资产位置 —— carried 表示取自更早一期（本月尚未盘点） */
export interface RatioAssetPosition {
  available: boolean
  yearmon: string | null
  snapshot_date: string | null
  source: string | null
  liquid: number | null
  receivable: number | null
  financial_assets: number | null
  self_use_total: number | null
  total_assets: number | null
  borrow: number | null
  net_worth: number | null
  carried: boolean
  reason: string | null
}

export interface LiabilityState {
  total: number
  active: number
  /** empty（完全没录）/ none_active（录了但都不在还）/ ok */
  state: string
}

export interface RatioWindow {
  months: number
  label: string
}

export interface RatioGap {
  key: string
  label: string
  reason: string | null
  hint: string
}

export interface RatioOverview {
  anchor_yearmon: string
  asset_source: string | null
  asset_source_label: string
  asset_position: RatioAssetPosition
  liability_state: LiabilityState
  windows: { expense: RatioWindow; income: RatioWindow; passive: RatioWindow }
  ratios: RatioItem[]
  gaps: RatioGap[]
}

export interface RatioTrendPoint {
  ym: string
  value: number | null
  level: RatioLevel
  level_label: string | null
  available: boolean
}

export interface RatioTrend {
  months: string[]
  asset_source: string | null
  series: Record<string, RatioTrendPoint[]>
  excluded: { key: string; label: string; reason: string }[]
}

/**
 * 比率口径元信息 —— 气泡提示的**唯一文案源**。
 *
 * 🔴 note 是后端 `constants.RATIO_BANDS[key]['note']` 的原样下发，
 *    前端只负责逐行渲染。在这里补一句「其实是……」就等于口径有了两份。
 */
export interface RatioMeta {
  key: string
  label: string
  unit: string
  /** higher_better / lower_better / neutral */
  direction: string
  formula: string
  /** 口径说明，逐行渲染；**纯文本**，不含 Markdown 标记 */
  note: string[]
  bands: RatioBand[] | null
  target: number | null
}
