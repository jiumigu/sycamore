/**
 * 物件资产（v3.60.0，P4-A）类型定义
 *
 * ⚠️ 与 `survivalTypes.ts` 刻意分开、**不互相 import**：
 *    一个是「值多少钱」（年 / 元，会折旧会报废），
 *    一个是「还能撑多久」（天，会被用完）。字段名看着像，语义完全不同。
 *
 * 🔴 三个必须记住的类型事实：
 *    ① 金额与净值在响应里是**字符串**（DRF `DecimalField` 默认转字符串），
 *       要算数先 `Number(...)`。别拿字符串比大小 —— '10' < '9' 会得出荒谬结论。
 *    ② `purchase_amount` 与 `current_value` 是**两件事**：
 *       前者可空=「想不起来多少钱」，后者可空=「算不出来」。两者都不等于 0。
 *    ③ 派生列（`age_months` / `remaining_months` / `current_value` / `is_overdue` …）
 *       **一律来自后端**，前端一个都不重算。
 */

// `bands` 的元组形状与财富侧比率模块同源，直接复用，别另立一份
import type { RatioBand } from './wealthTypes'

// ──────────────────────────────────────────────────────────────
// 枚举（真源在后端 constants.py，这里只是为了类型收窄）
// ──────────────────────────────────────────────────────────────

/** 回答「我还要不要它」。三态，别合并成两态 —— 见设计文档 §6.3 */
export type PropertyStatus = 'in_use' | 'idle' | 'scrapped'

/** 回答「它现在好不好使」。**与 status 完全正交，不参与任何数字** */
export type PropertyCondition = 'normal' | 'broken'

// ──────────────────────────────────────────────────────────────
// 类别
// ──────────────────────────────────────────────────────────────

/**
 * 物件类别 —— 只装**用途**（家电 / 家具 / 数码 / 交通 / 家装 / 其他）。
 *
 * ⚠️ 不要把体型（大件 / 小玩意儿）或价值档（高 / 中 / 低）建进来：那是另外两把尺子。
 *    想表达「它很大」「它很贵」，用列表排序（设计文档 §4.3 专条）。
 */
export interface PropertyCategory {
  id: number
  name: string
  icon: string
  /**
   * **只作表单预填，绝不兜底。**
   * 用户没填年限的物件净值一律算不出（null），不会拿这个值顶上。
   */
  default_lifespan_months: number | null
  sort_order: number
  note: string
  /** 其下物件数 —— 它同时也是「为什么这个类别删不掉」的答案 */
  property_count: number
}

export interface PropertyCategoryFormData {
  name: string
  icon?: string
  default_lifespan_months?: number | null
  sort_order?: number
  note?: string
}

export interface PropertySeedResult {
  created: number
  updated: number
  skipped: number
  categories: PropertyCategory[]
}

// ──────────────────────────────────────────────────────────────
// 物件
// ──────────────────────────────────────────────────────────────

/** 算不出的原因 —— 前端点开那个「—」看到的就是它 */
export interface PropertyIssue {
  code: string
  label: string
}

/** 明细行的原始字段（人填的那部分） */
export interface PropertyItemBase {
  id: number
  name: string
  /** 品牌 / 型号 */
  spec: string
  location: string
  category_id: number
  category_name: string
  /** 整件总价；null = 想不起来了（**不是 0**） */
  purchase_amount: string | null
  purchase_date: string | null
  /** 界面按年填、这里存月；null = 没填 → 净值算不出 */
  lifespan_months: number | null
  status: PropertyStatus
  condition: PropertyCondition
  scrapped_date: string | null
  dispose_note: string
  note: string
  tags: string[]
  created_at: string | null
  updated_at: string | null
}

/**
 * 净值为 0 的**来源** —— 后端下发，前端不自己拿 `condition` 判。
 *
 * 🔴 「已折完」与「坏了归 0」是两件事，该采取的行动相反（一个该换新、一个该修或该扔）。
 *    拿 `condition === 'broken'` 在前端推一遍，等于把口径搬出后端一份；
 *    下次改口径时漏掉的就是它，而漏掉是静默的（界面上照旧说得通）。
 */
export type PropertyZeroReason = 'depreciated' | 'broken'

/**
 * 明细行 = 原始字段 + 派生列。
 *
 * 派生列**全部由后端算好**（`services/property_calc.py` 唯一真源）——
 * 这里写 `| null` 不是「可能有」，而是「算不出时就是 null」：
 *     缺金额 / 缺购买日期 / 缺年限 / 购买日在未来 / 报废却没填报废日。
 * 遇到 null 要显示「—」并把 `issues` 里的句子摆出来，**绝不掉成 0**。
 */
export interface PropertyDerived {
  /** 购买日到基准日的整月数 */
  age_months: number | null
  /** 计划月数 − 已用月数；**可为负**（负多少就是超期多少，是事实不是错误） */
  remaining_months: number | null
  monthly_depreciation: string | null
  /**
   * 当前净值。三个可能：
   *   `null` → 算不出（缺数据）；
   *   `'0.00'` → 是一个**结论**，来源见 `zero_reason`；
   *   其余 → 直线折旧的结果。
   * **三者不能混为一谈**。
   */
  current_value: string | null
  /** 净值为 0 时的来源；净值不为 0（或算不出）时为 null */
  zero_reason: PropertyZeroReason | null
  /** 算到哪一天：在用/闲置 = 今天；已报废 = 报废那天（价值在那里定格） */
  ref_date: string | null
  is_overdue: boolean
  overdue_months: number
  issues: PropertyIssue[]
}

export type PropertyItem = PropertyItemBase & PropertyDerived

/** 新增 / 编辑的入参 —— 派生列一律不送（后端自己算） */
export interface PropertyItemFormData {
  category_id: number
  name: string
  spec?: string
  location?: string
  purchase_amount?: number | null
  purchase_date?: string | null
  lifespan_months?: number | null
  status?: PropertyStatus
  condition?: PropertyCondition
  scrapped_date?: string | null
  dispose_note?: string
  note?: string
  tags?: string[]
}

// ──────────────────────────────────────────────────────────────
// 汇总
// ──────────────────────────────────────────────────────────────

/**
 * 一个合计块的**四个数，缺一不可**。
 *
 * 只给 `total` 的话，界面没法把「少算了」摆出来 ——
 * 总额看着小一点、件数却是全的，两个数都对不上，还没人会去查。
 */
export interface PropertyTotalBlock {
  total: string
  counted: number
  /** 没填金额（连原值都没有）件数 */
  unpriced_count: number
  /** 填了金额却算不出净值（缺日期 / 缺年限 / 日期在未来）件数 */
  unvalued_count: number
}

/**
 * 净值块 = 合计块 + `broken_count`。
 *
 * 🔴 为什么要有这个数：勾一下「损坏」会让在用净值合计掉一截，
 *    而「计入件数」纹丝不动 —— 总数变小、件数还是全的，
 *    两个数对不上还没人会去查。这个数就是那句解释。
 * ⚠️ 它**只属于净值块**：原值合计与状况无关（买的时候花了多少钱，
 *    不会因为后来坏了就变），给那边也挂一个恒为 0 的字段只会添乱。
 */
export interface PropertyNetValueBlock extends PropertyTotalBlock {
  /** 因状况=损坏而按 0 计的件数（它们**仍计入 counted**，只是金额为 0） */
  broken_count: number
}

export interface PropertySummary {
  /** 在用 + 闲置 —— 闲置也算「还在我手上」 */
  in_use_count: number
  scrapped_count: number
  /** 原值合计：**含已报废**（那是历史总投入） */
  total_amount: PropertyTotalBlock
  /** 在用净值合计：**不含已报废**（它的价值在报废那天就定格了） */
  in_use_net_value: PropertyNetValueBlock
}

// ──────────────────────────────────────────────────────────────
// 口径元信息
// ──────────────────────────────────────────────────────────────

export interface PropertyOption {
  value: string
  label: string
}

/**
 * 口径气泡 —— 结构必须与 `RatioMeta` 一致，因为共用同一个气泡组件。
 * `bands` **恒为空数组**：本模块不设绝对判定线（见设计文档 §5.5）。
 */
export interface PropertyMetricMeta {
  key: string
  label: string
  unit: string
  /** 恒为 'neutral' —— 净值高不代表好，超期也不代表坏 */
  direction: string
  formula: string
  /** 口径说明，逐行渲染；**纯文本**，不含 Markdown 标记 */
  note: string[]
  bands: RatioBand[]
}

export interface PropertyMeta {
  statuses: PropertyOption[]
  conditions: PropertyOption[]
  metric_meta: PropertyMetricMeta[]
  /** 原因码 → 给人看的一句话（唯一真源在后端 constants） */
  issue_labels: Record<string, string>
  /** 页面里固定那一句说明 —— 放后端是为了它只有一个来源 */
  not_in_net_worth_note: string
  subtitle: string
}
