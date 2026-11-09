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
    /**
     * `support_until` 为 `null` 时的原因码，目前只有 `no_self_expense`。
     *
     * 🔴 前端只查表出人话，**不要**自己拿 `support_until === null` 猜语义 ——
     *    这个空前被写死成「永不耗尽」，而真实含义是「还没有速度可外推」。
     */
    support_zero_reason: string | null
  }
  tier: PeriodTagStat[]
  time: {
    hours: Record<string, number>
    /** 已记录小时（分六类后求和 = 全部记录时长） */
    covered_hours: number
    /** 其中没设默认归因、按兜底「成长」计入的小时 */
    fallback_hours: number
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

/** 归因类别配色 —— 📌 v3.64.19 起**搬到 `shared/config/attributionMeta.ts`**。
 *
 * 为什么搬：阶段账本（selfrun）要印同一套配色，而本模块第 4 轮整体下线。
 * 留在这里的话会出现两张表；更糟的是删模块时这张表跟着被删，
 * 而账本那边还在 import —— 那时才发现的，就是一片灰。
 * 这里只做 re-export，保持既有引用不用改（模块下线时随文件一起消失）。
 */
export { ATTRIBUTION_META } from '@/shared/config/attributionMeta'
