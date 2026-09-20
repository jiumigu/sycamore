/** 三年赎回期 · 前端类型定义 */

export interface RedemptionConfig {
  id: number
  start_date: string
  end_date: string
  pool_principal: number
  tracking_status: 'active' | 'paused'
  paused_since: string | null
  resume_at: string | null
  baseline_toward_ratio: number | null
  baseline_set_week: number | null
  created_at: string
  updated_at: string
  derived?: {
    elapsed_days: number
    remaining_days: number
    phase: string
  }
}

export interface PoolInject {
  id: number
  inject_date: string
  amount: number
  source: string
  note: string | null
  created_at: string
}

/** 匹配维度（须与后端 `RedemptionAttrRule.MATCH_FIELD_CHOICES` 对齐）。
 *
 * ⚠️ 三点语义：① `activity_type` 是 L2 活动类型，不在 ATracker 外部表，后端按 task_name
 * 反查 `temporal_task_meta` 得到，**曾因前端漏列而选不到、后端又走 getattr 静默跳过**；
 * ② `task_type` 在当前数据里恒等于 `task_name`（外部表写入约定），保留是为兼容历史规则；
 * ③ 已移除 `category_level2` —— v0.3 起停写，全库非空行数为 0。
 */
export type AttrField = 'task_name' | 'activity_type' | 'task_type'
export type Attribution = '成长' | '关系' | '维持' | '谋生' | '流失'

export interface AttrRule {
  id: number
  match_field: AttrField
  match_value: string
  attribution: Attribution
  priority: number
  is_active: boolean
  note: string | null
  created_at: string
  updated_at: string
}

export interface PeriodTagStat {
  period_tag: string
  count: number
  total: number
}

export interface RedemptionStats {
  window: {
    start: string
    end: string
    total_days: number
    elapsed_days: number
    remaining_days: number
  }
  tracking_status: string
  pool: {
    principal: number
    injected: number
    self_expense: number
    self_income: number
    balance: number
    avg_daily: number
    support_until: string | null
  }
  tier: PeriodTagStat[]
  time: {
    hours: Record<string, number>
    covered_hours: number
    theoretical_hours: number
    coverage_rate: number
    coverage_warn: boolean
    toward_ratio: number
    days_elapsed: number
  } | null
  unit_cost: number | null
}

export interface SyncResult {
  mode: string
  cash: number
  daily_budget: number
  support_weeks: number | null
  end_age: number | null
  end_week: number | null
}

/** 归因类别配色 */
export const ATTRIBUTION_META: Record<string, { color: string; bg: string }> = {
  成长: { color: '#7C3AED', bg: '#F3E8FF' },
  关系: { color: '#0D9488', bg: '#CCFBF1' },
  维持: { color: '#2563EB', bg: '#DBEAFE' },
  谋生: { color: '#D97706', bg: '#FEF3C7' },
  流失: { color: '#DC2626', bg: '#FEE2E2' },
}
