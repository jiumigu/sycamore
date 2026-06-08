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
}

/** 推演结果 */
export interface CoverageResult {
  coverage_weeks: number[]
  support_weeks: number
  end_age: number | null
  end_week: number | null
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

/** 日历视图切换 */
export type CalendarViewMode = 'heatmap' | 'monthly'

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
// 现金盘点类型
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

/** 资产汇总 */
export interface AssetSummary {
  flow_total: number
  total: number
  borrow: number
  lend: number
  realnum: number
}

/** 资产健康指标 */
export interface HealthMetrics {
  emergency_fund: number
  liquidity_ratio: number
  debt_ratio: number
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
