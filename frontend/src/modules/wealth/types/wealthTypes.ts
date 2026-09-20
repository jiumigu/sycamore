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
  deposit_balance: number | null
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
  deposit: number | null
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
  deposit?: number | null
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

/** 资产健康指标
 * 应急金以「月数」判定；月均支出无数据时 emergency_* 派生字段为 null
 * debt_ratio_legacy 为修正前的分母口径，仅供对照，不用于展示
 */
export interface HealthMetrics {
  emergency_fund: number
  emergency_fund_months: number | null
  emergency_months_target: number
  emergency_target_amount: number | null
  emergency_gap: number | null
  monthly_expense_avg: number
  liquidity_ratio: number
  debt_ratio: number
  debt_ratio_legacy: number
  provident_fund_ratio: number
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

/** 对账项 */
export interface ReconcileItem {
  yearmon: string
  book_balance: number
  actual_total: number
  difference: number
  status: 'matched' | 'mismatched'
}

/** 对账结果 */
export interface ReconcileData {
  items: ReconcileItem[]
  summary: {
    matched: number
    mismatched: number
  }
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
