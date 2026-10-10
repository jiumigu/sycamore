/**
 * 生存资源盘点（v3.59.0，P3-A 一期）类型定义
 *
 * 🔴 三条口径在类型上就钉死，避免写代码时手滑：
 *
 * 一、`days` / `expected` / `spread` 一律 `number | null`。
 *    `null` 是「算不出来」（没配单位、配方缺件、单位不可比），
 *    而 0 是「真的撑 0 天」的结论 —— 两者不是一回事。
 *    任何 `?? 0` 都会把「没数据」翻转成最坏结论，别写。
 *
 * 二、PERT 的语义：**乐观 = 消耗慢 = 撑得久**。
 *    所以恒有 `optimistic ≥ likely ≥ pessimistic`。
 *    界面上的「最乐观」永远指「省着用能撑多久」，不是「情况最好的日子」。
 *
 * 三、配餐的跨配方口径固定是 `min`（每个配方每天都要吃到），
 *    所以卡片显示的是 `aggregate_mode_effective` 而不是用户填的
 *    `aggregate_mode` —— 显示后者会出现「界面写求和、算法取最小」的谎报。
 */

import type { RatioMeta } from './wealthTypes'

export type SurvivalScenarioKey = 'optimistic' | 'likely' | 'pessimistic'

/** 三档天数 */
export interface SurvivalScenarioTriple {
  optimistic: number | null
  likely: number | null
  pessimistic: number | null
}

/** 三档 + 期望值 + 离散度（在各自那一层算，不做「先算期望再平均」） */
export interface SurvivalScored {
  days: SurvivalScenarioTriple
  expected: number | null
  spread: number | null
}

export interface SurvivalOption {
  value: string
  label: string
}

export interface SurvivalUnit {
  id: number
  category_id: number
  name: string
  base_unit: string
  /** 1 个本单位 = N 个基准单位 */
  to_base_rate: number
  is_serving_unit: boolean
  note: string
  sort_order: number
}

export interface SurvivalCategory {
  id: number
  name: string
  consume_mode: string
  consume_mode_label: string
  aggregate_mode: string
  aggregate_mode_label: string
  /** 实际生效的口径：配餐类固定 'min'，显示这个 */
  aggregate_mode_effective: string
  icon: string
  description: string
  sort_order: number
  item_count: number
  recipe_count: number
  units?: SurvivalUnit[]
}

export interface SurvivalItem {
  id: number
  category_id: number
  category_name: string
  name: string
  quantity: number
  unit_id: number | null
  unit_name: string
  satiety: string
  satiety_label: string
  grade: string
  grade_label: string
  status: string
  status_label: string
  priority: string
  priority_label: string
  /** 一件（一份）还能撑多少天；配餐类不填，由配方决定 */
  days_per_unit: number | null
  // ── 按次计量（v3.59.3）：四个「原话」字段 ──
  // 合起来读作「一份能用 10 次，每 3 天用 1 次」。
  // ⚠️ 前端**不做任何换算** —— 间隔天数与折算后的可用天数都由后端给，
  //    自己再乘一遍就成了第二份口径，改后端时必然漏改。
  /** 一份能用多少次（一包卫生巾 10 片就填 10） */
  uses_per_unit: number | null
  /** 每几个周期（「每 3 天」里的 3） */
  use_cycle_num: number | null
  /** 周期单位：day / week / month */
  use_cycle_unit: string
  use_cycle_unit_label: string
  /** 每周期用几次（「每 3 天用 1 次」里的 1） */
  use_times: number | null
  /** 计量口径：'cycle' 按次 / 'day' 按天 / null 两条都没填 */
  life_mode: string | null
  /**
   * 折算后的「一份可用天数」。
   *
   * ⚠️ 界面显示「一份可用」必须用这个，**不是 `days_per_unit`** ——
   *    按次计量的物品 `days_per_unit` 是空的，直接读会显示成「未填」。
   */
  days_per_unit_effective: number | null
  /** 建议盘点间隔（天）；留空 = 不定周期 */
  stocktake_cycle_days: number | null
  /** 补货提醒阈值，与数量同一单位 */
  restock_threshold: number | null
  /** 数字类专用：一册需要读多少小时 */
  hours_per_unit: number | null
  expire_date: string | null
  purchase_date: string | null
  purchase_cost: number | null
  notes: string
  tags: string[]
  recipe_line_count: number
}

export interface SurvivalRecipeLine {
  id: number
  item_id: number
  item_name: string
  item_quantity: number
  item_unit_id: number | null
  item_unit_name: string
  satiety: string
  role: string
  role_label: string
  quantity_per_serving: number
  unit_id: number | null
  unit_name: string
  note: string
}

/** 配方里的**组合行**（v3.59.13）
 *
 * ⚠️ 与 `SurvivalRecipeLine` **刻意不同形**：组合行没有自己的「每餐用量」，
 *    用量在组合成员上。硬凑成同一个形状，前端就只能靠「有没有 item_id」猜。
 */
export interface SurvivalRecipeComboLine {
  id: number
  combo_id: number
  combo_name: string
  role: string
  role_label: string
  member_count: number
  note: string
}

export interface SurvivalRecipe {
  id: number
  category_id: number
  category_name: string
  name: string
  meals_per_day: number
  note: string
  sort_order: number
  line_count: number
  combo_line_count?: number
  lines?: SurvivalRecipeLine[]
  combo_lines?: SurvivalRecipeComboLine[]
}

/** 配置问题：不是错误，是「这里还会算不准」的说明 */
export interface SurvivalIssue {
  category?: string | null
  recipe?: string | null
  code: string
  message: string
  item?: string | null
  items?: string[]
  detail?: string | null
}

/** 组合成员的计算底稿 —— 与配方行同形（同一段后端算法算出来的） */
export interface SurvivalComboMemberDetail {
  item_id: number
  item_name: string
  quantity_per_serving: number | null
  unit_name: string
  stock: number | null
  stock_unit_name: string
  expire_date: string | null
  expire_cap_days: number | null
  servings: number | null
  issues: SurvivalIssue[]
}

/** 配方行的计算底稿 —— 「这个数是怎么来的」要摊得开 */
export interface SurvivalLineDetail {
  /** 聚合用的稳定键（`item-3` / `combo-1`）—— 两类行来自两张表，id 会撞号 */
  line_key?: string
  /** 前端的**分派依据**：'item' 是普通食材行、'combo' 是组合行 */
  line_kind?: 'item' | 'combo'
  line_id: number
  /** 组合行没有「单一物品」，故为 null —— **不是**数据缺失 */
  item_id: number | null
  item_name: string
  role: string
  quantity_per_serving: number | null
  unit_name: string
  stock: number | null
  stock_unit_name: string
  satiety: string
  grade: string
  expire_date: string | null
  expire_cap_days: number | null
  servings: number | null
  /** 组合行专用：组内**最先耗尽的那件**（不是组合名）—— 缺口要点到具体物品 */
  bottleneck_item?: string | null
  /** 组合行专用：逐件明细（与配方行同形，可复用同一套渲染） */
  members?: SurvivalComboMemberDetail[]
  issues: SurvivalIssue[]
}

export interface SurvivalRecipeResult extends SurvivalScored {
  recipe_id: number
  recipe_name: string
  meals_per_day: number | null
  /** 主食位求和（可替代） */
  staple_servings: number | null
  /** 必配位取最小（木桶只在这里成立） */
  required_servings: number | null
  /**
   * 配了几行必配位（不论该行算不算得出）。
   *
   * ⚠️ 必须与 `required_servings` **一起判**：`required_servings === null` 有两种来由 ——
   *    · `required_line_count === 0` → 一行都没配 ⇒ **无约束，不影响结论**
   *    · `required_line_count > 0`   → 配了但都算不出来 ⇒ 真的算不出来（`issues` 会点名）
   *    显示成同一句话会让「没配」看起来像「配置出错」。
   */
  required_line_count: number
  /** min(主食位, 必配位) */
  meals: number | null
  bottleneck_role: string | null
  bottleneck_item: string | null
  expiry_cap_days: number | null
  capped_by_expiry: boolean
  trustworthy: boolean
  per_day_reference: number | null
  lines: SurvivalLineDetail[]
}

export interface SurvivalItemLife extends SurvivalScored {
  item_id: number
  name: string
  quantity: number | null
  unit_name: string
  days_per_unit: number | null
  uses_per_unit: number | null
  use_cycle_num: number | null
  use_cycle_unit: string
  use_times: number | null
  /** 计量口径：'cycle' / 'day' / null（两条都没填） */
  life_mode: string | null
  /** 折算后的一份可用天数 —— 显示「一份可用」用这个 */
  days_per_unit_effective: number | null
  /** 后端算好的使用间隔（天），用来把「每 3 天用 1 次」这句话说全 */
  interval_days: number | null
  hours_per_unit: number | null
  satiety: string
  grade: string
  status: string
  stocktake_cycle_days: number | null
  restock_threshold: number | null
  expire_date: string | null
  expire_cap_days: number | null
  hours_total: number | null
  issues: SurvivalIssue[]
}

/**
 * 保存前试算的结果（v3.59.11）
 *
 * 🔴 字段与 `SurvivalItemLife` 同源（后端那边是继承来的），只差 `item_id`：
 *    试算还没有 id。刻意**不另起一份字段清单** —— 清单复制成两份之后，
 *    加字段时漏改一份是不会有任何报错的，而后果是「试算说 150 天、
 *    保存后写着 123.7 年」这种两边看着都正常的错。
 */
export interface SurvivalItemPreview extends Omit<SurvivalItemLife, 'item_id'> {
  item_id: number | null
}

export interface SurvivalCategoryResult extends SurvivalScored {
  category_id: number
  name: string
  icon: string
  consume_mode: string
  aggregate_mode: string
  aggregate_mode_effective: string
  usable_item_count: number
  item_count: number
  /** 零食单独统计：它顶不了一顿饭，不混进主食时长 */
  snack_days: number | null
  /** 数字类：还能读多少小时 */
  hours_total: number | null
  trustworthy: boolean
  items: SurvivalItemLife[]
  recipes: SurvivalRecipeResult[]
  issues: SurvivalIssue[]
}

export interface SurvivalCash {
  months: number | null
  days: number | null
  /** 口径说明：复用应急金月数的三点估算 */
  basis: string
}

export interface SurvivalCoverage {
  pct: number | null
  remaining_days: number | null
  reason?: string | null
  window_start?: string
  window_end?: string
}

// ── 必需品基准清单与缺口对账（v3.59.7） ──

/** 底线必需 = 缺了影响健康/卫生/体面；改善型 = 只是「有更好」 */
export type SurvivalEssentialScope = 'core' | 'optional'

/**
 * 缺口档位 —— **五档各有各的处置**，不要合并任意两档
 *
 *   missing   没关联物品        → 去录入，或确认自己根本用不着（那就删掉这项）
 *   unknown   物品在但算不出    → 去补用量口径；东西已过期也是这一档
 *   critical  不足 30 天        → 该补货了
 *   tight     30 ~ 90 天        → 记着，可以开始留意
 *   adequate  90 天以上         → 不用管
 *
 * ⚠️ missing 与 unknown 长得都像「没有数字」，但一个要去录入、一个要去改配置。
 *    一律渲染成「算不出来」，会把「还没录」说成「配置出错」，
 *    令人去改一个本来没坏的东西。
 */
export type SurvivalEssentialLevel = 'missing' | 'unknown' | 'critical' | 'tight' | 'adequate'

/**
 * 基准项里**逐件**的对账明细（v3.59.12）
 *
 * 一条基准项可以挂多件物品：睡衣分夏 / 秋 / 冬、卫生巾分日用 / 夜用、
 * 鞋分室内 / 室外。组内多件**并列取最小**（冬天没睡衣，夏季那件囤十件也不解决），
 * 后端算好放在这里，前端只展示、**不重排也不重算**。
 *
 * ⚠️ 顺序由后端定：正常用量下最短的在前、算不出的排最后。
 */
export interface SurvivalEssentialItem extends SurvivalScored {
  item_id: number
  item_name: string
  item_quantity: number | null
  item_unit_name: string
  item_status: string
  expire_date: string | null
  level: SurvivalEssentialLevel
  issues: SurvivalIssue[]
}

/** 基准项 + 逐项对账结果（列表端点返回的就是它） */
export interface SurvivalEssential extends SurvivalScored {
  essential_id: number
  name: string
  category_id: number | null
  category_name: string
  scope: SurvivalEssentialScope
  /** 建议单位，仅录入提示，不参与计算 */
  unit_name: string
  /** 录入提示：帮用户回忆消耗节奏的一句话 */
  hint: string
  note: string
  sort_order: number
  /**
   * 逐件明细（v3.59.12）。「对应物品」多选的回显与「可支撑」的悬浮说明都用它。
   * ⚠️ 顺序由后端定（最短的在前、算不出的最后）。
   */
  items: SurvivalEssentialItem[]
  /**
   * ⚠️ 以下 `item_*` 一律指**代表件** —— 正常用量下最短的那一件，
   *    不再是「唯一那件」。逐件请看上面 `items`。
   *    （后端 `find_essential_shortest` 用的也是这个代表件。）
   */
  item_id: number | null
  item_name: string
  item_quantity: number | null
  item_unit_name: string
  item_status: string
  expire_date: string | null
  level: SurvivalEssentialLevel
  issues: SurvivalIssue[]
}

/** 核心必需品里最先见底的那一件 */
export interface SurvivalEssentialShortest {
  essential_id: number
  name: string
  item_name: string
  category_name: string
  days: number | null
  level: SurvivalEssentialLevel
}

/** 尚未闭合的核心项：未录入 或 待补数据 */
export interface SurvivalEssentialUnclosed {
  essential_id: number
  name: string
  level: SurvivalEssentialLevel
}

export interface SurvivalEssentialSummary {
  total: number
  core_total: number
  level_counts: Record<string, number>
  core_level_counts: Record<string, number>
  unclosed_core: SurvivalEssentialUnclosed[]
  unclosed_core_count: number
  /**
   * 核心项是否已全部闭合。
   *
   * 🔴 这是一个**独立的可信度信号**，不是天数：未录入的牙膏不进天数计算
   *    （那会把「还没录」说成「只够撑 0 天」，而 0 是「真的撑不了」的结论），
   *    所以必须靠这个标记告诉用户「结论还没闭环」。
   */
  complete: boolean
}

/** 综合分析里内联的对账块（只要汇总与最短，明细走列表端点） */
export interface SurvivalEssentialReconcile {
  summary: SurvivalEssentialSummary
  shortest: SurvivalEssentialShortest | null
  is_configured: boolean
}

export interface SurvivalEssentialFormData {
  name: string
  category_id: number
  scope?: SurvivalEssentialScope
  unit_name?: string
  hint?: string
  /**
   * 关联物品，可挂多件（v3.59.12）。
   *
   * ⚠️ **空数组 ≠ 不传**：空数组是「用户把勾选全取消了」，不传是「这次不动它」。
   *    后端认这个区别 —— 把清空写成「不传」，用户取消勾选后点保存，
   *    界面看着清空了、刷新又回来。
   */
  item_ids?: number[]
  note?: string
  sort_order?: number
}

export interface SurvivalEssentialSeedResult {
  created: number
  updated: number
  skipped: number
  seeded_total: number
  /** 哪些归属类别还不存在 —— 静默跳过会让人以为清单本来就这么长 */
  missing_categories: string[]
}

export interface SurvivalAnalysis {
  available: boolean
  reason: string | null
  as_of: string
  categories: SurvivalCategoryResult[]
  shortest_category: string | null
  shortest_days: number | null
  overall: SurvivalScored
  cash: SurvivalCash
  bottleneck: 'cash' | 'asset' | 'balanced' | string
  bottleneck_label: string
  coverage: SurvivalCoverage
  issues: SurvivalIssue[]
  snack_days: number | null
  has_any_item: boolean
  /** 必需品缺口对账 —— 与生存天数**并列的第二把尺子**：天数答「够撑多久」，它答「漏了什么」 */
  essentials: SurvivalEssentialReconcile
}

/**
 * 衣物可穿次数参考 —— **只在录入弹窗里当锚点，后端算法一个字段都不读它**
 *
 * ⚠️ `uses_*` 与 `days_*` 两列**不是同一把尺子**，**不要互相换算**：
 *    次数与穿法无关、跨人可比；天数隐含了一个穿着频次，换个节奏就不成立。
 *    所以表里两列并列给出，界面上也分开展示 —— 拿 365 天去反推次数，
 *    得到的是一个没人核对过的假设，而且它看起来完全合理。
 *
 * `uses_low` 有值而 `uses_high` 为 null = 「这个数以上」（羊毛大衣）。
 * `uses_low` 为 null = 这件不适合作按次估（内裤、袜子、羽绒服…），只能按天填。
 */
export interface SurvivalWearReference {
  keyword: string
  uses_low: number | null
  uses_high: number | null
  days_low: number
  days_high: number
  /** 典型轮换频次（每周穿几次）；无按次建议时为 null */
  wears_per_week: number | null
  /** 关键衰减信号 —— 「什么时候算该换了」比天数更能帮人下判断 */
  signal: string
}

export interface SurvivalMeta {
  /** 口径元信息，与 /wealth/ratios/meta/ 同结构，可直接喂给 MetricTooltip */
  metric_meta: RatioMeta[]
  consume_modes: SurvivalOption[]
  aggregate_modes: SurvivalOption[]
  satiety: SurvivalOption[]
  satiety_counted: string[]
  grades: SurvivalOption[]
  statuses: SurvivalOption[]
  priorities: SurvivalOption[]
  roles: SurvivalOption[]
  /** 按次计量的周期单位（天 / 周 / 月），与后端 constants 同一份 */
  use_cycle_units: SurvivalOption[]
  scenarios: SurvivalScenarioKey[]
  meal_scenarios: Record<string, number>
  days_per_year: number
  bottleneck_tolerance: number
  /** 基准项性质的选项（底线必需 / 改善型） */
  essential_scopes: SurvivalOption[]
  /**
   * 缺口档位的选项（值 + 中文标签）。
   *
   * ⚠️ 后端**刻意不下发分档阈值** —— 阈值到了前端就一定有人拿它重算一遍分档，
   *    那就是第二份口径，两边不一致时谁都不会发现。
   *    分档由后端算好放在每行的 `level` 里，这里只负责取标签与上色。
   */
  essential_levels: SurvivalOption[]
  /** 衣物可穿次数参考（v3.59.8）—— 仅录入锚点，算法不读它 */
  wear_reference: SurvivalWearReference[]
}

export interface SurvivalSeedResult {
  created_categories: number
  created_units: number
  updated_categories: number
  categories: SurvivalCategory[]
  /** 基准清单的初始化结果 —— 归属类别不存在时走 missing_categories 报告，不静默补 */
  essentials?: SurvivalEssentialSeedResult
}

// ── 入参 ──

export interface SurvivalCategoryFormData {
  name: string
  consume_mode: string
  aggregate_mode: string
  icon?: string
  description?: string
  sort_order?: number
}

export interface SurvivalUnitFormData {
  category_id: number
  name: string
  base_unit?: string
  to_base_rate?: number
  is_serving_unit?: boolean
  note?: string
  sort_order?: number
}

export interface SurvivalItemFormData {
  category_id: number
  name: string
  quantity: number
  unit_id?: number | null
  satiety?: string
  grade?: string
  status?: string
  priority?: string
  days_per_unit?: number | null
  // 按次计量：两条口径**二选一**，由界面保证不同时提交。
  // 后端判据是「填了 uses_per_unit 就按次算」，所以按天那条必须显式提交 null。
  // ⚠️ 频次三兄弟（num / unit / times）**同生同灭** —— 只置空其中两个，
  //    「每 N 周期用 M 次」这句话就剩半句留在库里，而且界面上看不出来。
  uses_per_unit?: number | null
  use_cycle_num?: number | null
  use_cycle_unit?: string | null
  use_times?: number | null
  stocktake_cycle_days?: number | null
  restock_threshold?: number | null
  hours_per_unit?: number | null
  expire_date?: string | null
  purchase_date?: string | null
  purchase_cost?: number | null
  notes?: string
  tags?: string[]
}

export interface SurvivalRecipeLineFormData {
  item_id: number
  role: string
  quantity_per_serving: number | string
  unit_id?: number | null
  note?: string
}

export interface SurvivalRecipeFormData {
  category_id: number
  name: string
  meals_per_day: number
  note?: string
  sort_order?: number
  lines: SurvivalRecipeLineFormData[]
  /** 组合行（v3.59.13）—— 不传 = 这次不动它，传 [] = 清空 */
  combo_lines?: SurvivalRecipeComboLineFormData[]
}

/** 配方里的组合行入参
 *
 * ⚠️ 刻意**没有**「份数」这个字段：组合的用量在成员上，再加一个倍率
 *    就是「两个数相乘」的形状（本项目踩过：一份 × 数量 = 45,000 天）。
 *    要加量请去改组合里那一行的「每餐用量」。
 */
export interface SurvivalRecipeComboLineFormData {
  combo_id: number
  role: string
  note?: string
}

// ── 组合（v3.59.13） ──

export interface SurvivalComboMember {
  item_id: number
  item_name: string
  quantity_per_serving: number
  unit_id: number | null
  unit_name: string
  item_unit_name: string
  stock: number
  stock_unit_name: string
}

export interface SurvivalCombo {
  id: number
  category_id: number
  category_name: string
  name: string
  note: string
  sort_order: number
  member_count: number
  /** 被几个配方引用 —— 被引用的组合**删不掉**，界面要能在点之前就看见 */
  recipe_ref_count: number
  members?: SurvivalComboMember[]
}

export interface SurvivalComboMemberFormData {
  item_id: number
  quantity_per_serving: number | string
  unit_id?: number | null
}

export interface SurvivalComboFormData {
  category_id: number
  name: string
  note?: string
  sort_order?: number
  members: SurvivalComboMemberFormData[]
}

// ── 盘点快照（v3.59.0 二期） ──

/**
 * 快照里的单个类别。
 *
 * `category_id` 可为 null（那个类别后来被删了）—— **`category_name` 才是稳定标识**：
 * 历史点自带当时的名字，所以类别改名或删除都不会改写过去。
 */
export interface SurvivalSnapshotCategory {
  category_id: number | null
  category_name: string
  consume_mode: string
  aggregate_mode_effective: string
  days: SurvivalScenarioTriple
  expected: number | null
  usable_item_count: number
  item_count: number
  snack_days: number | null
  hours_total: number | null
  issue_count: number
  trustworthy: boolean
}

/**
 * 一份盘点快照。
 *
 * ⚠️ 所有天数都可能是 `null` 且**与 0 不同义**：
 *    null = 那天算不出来，0 = 那天真的撑不了。
 *    显示时必须走「算不出来」而不是掉成 0。
 */
export interface SurvivalSnapshot {
  id: number
  date: string
  source: string
  source_label: string
  note: string
  days: SurvivalScenarioTriple
  expected: number | null
  spread: number | null
  shortest_category: string | null
  bottleneck: string
  bottleneck_label: string
  cash_months: number | null
  cash_days: number | null
  coverage_pct: number | null
  coverage_remaining_days: number | null
  category_count: number
  item_count: number
  snack_days: number | null
  issue_count: number
  trustworthy: boolean
  created_at: string | null
  /** 仅详情返回 —— 列表刻意不带明细，免得列表接口越用越重 */
  categories?: SurvivalSnapshotCategory[]
}

/** 趋势上的一个点 = 快照 + 相对上一点的差 */
export interface SurvivalSnapshotPoint extends SurvivalSnapshot {
  /** null = 算不出来（任一端缺值），**不是 0**；0 会显示成「跟上期持平」 */
  delta_expected: number | null
  delta_kind: 'up' | 'down' | 'flat' | null
  days_since_previous: number | null
}

/** 折线用的扁平数组；空值保持 null 由前端画断点（补 0 会画出假线） */
export interface SurvivalTrendSeries {
  dates: string[]
  expected: (number | null)[]
  optimistic: (number | null)[]
  pessimistic: (number | null)[]
  cash_days: (number | null)[]
  item_count: number[]
}

/**
 * 最近两期之间的对比。
 *
 * `comparable === false` 时**必须把 `reason` 显示出来**：
 * 期间改过类别构成或消耗模式的话，天数的差里混着「换了算法」这一项，
 * 只显示差值等于把配置变更说成了物资变化。
 */
export interface SurvivalComparison {
  comparable: boolean
  config_changed: boolean
  changed_categories: string[]
  reason: string
  delta_expected: number | null
  delta_item_count: number | null
  days_since_previous: number | null
  latest_date?: string
  previous_date?: string
  latest_expected?: number | null
  previous_expected?: number | null
}

export interface SurvivalTrend {
  available: boolean
  count: number
  min_points: number
  /** false = 点数不够谈方向（一个点是状态，两个点才有方向） */
  has_enough_points: boolean
  /** ⚠️ 按日期**升序**（折线从左到右）；列表端点则是倒序 */
  points: SurvivalSnapshotPoint[]
  comparison: SurvivalComparison
  series: SurvivalTrendSeries
}

export interface SurvivalSnapshotCreateFormData {
  date?: string | null
  note?: string
  /** 显式的「我知道今天盘过了，替换掉它」—— 不传时同一天重复盘点会被拒绝 */
  overwrite?: boolean
}

// ── 实盘盘点（v3.59.3） ──

/**
 * 盘点工作表的一行：待盘物品 + 系统记的账面 + 上次盘点。
 *
 * ⚠️ `book_quantity` **只用于界面回显**。提交时不带上它 ——
 *    服务端会在提交那一刻重新读一次。
 *    这不是防篡改，是防一个必然发生的过期读：盘点页可能开着半小时，
 *    其间库存在别处已经变过，而你手上那个数还是打开页面时的。
 */
export interface SurvivalWorksheetRow {
  item_id: number
  name: string
  category_id: number
  category_name: string
  unit_name: string
  book_quantity: number | null
  status: string
  expire_date: string | null
  /** 上次盘它是哪天；从没盘过是 null（不是空串） */
  last_stocktake_date: string | null
  /** 距上次盘点多少天；从没盘过是 null —— 0 会被读成「今天刚盘过」 */
  days_since_stocktake: number | null
  stocktake_cycle_days: number | null
  /** 只在设了盘点周期时才可能为 true，否则一律 false（人人标红 = 没有标） */
  stocktake_due: boolean
  restock_threshold: number | null
  /** 库存降到阈值（含等于）就该补货 */
  below_threshold: boolean
}

/** 盘点明细的一行；`delta` 与 `delta_kind` 由后端现算，表里没有这两列 */
export interface SurvivalStocktakeLine {
  id: number
  /** 物品后来被删掉时是 null，但 `item_name` 仍在 */
  item_id: number | null
  item_name: string
  category_name: string
  unit_name: string
  /** 提交那一刻系统读到的库存，不是前端传的 */
  book_quantity: number | null
  actual_quantity: number | null
  /** 实盘 − 账面：正是盘盈、负是盘亏、零是核对无误 */
  delta: number | null
  /** 'surplus' / 'deficit' / 'flat' */
  delta_kind: string
  note: string
}

/** 一次盘点（头 + 明细） */
export interface SurvivalStocktake {
  id: number
  stocktake_date: string
  source: string
  source_label: string
  note: string
  line_count: number
  surplus_count: number
  deficit_count: number
  flat_count: number
  created_at: string | null
  lines?: SurvivalStocktakeLine[]
}

export interface SurvivalStocktakeLineFormData {
  item_id: number
  /** ⚠️ 只提交实盘数 —— 账面由服务端读 */
  actual_quantity: number | string
  note?: string
}

export interface SurvivalStocktakeFormData {
  date?: string | null
  note?: string
  source?: string
  lines: SurvivalStocktakeLineFormData[]
}

// ══════════════════════════════════════════════════════════════
// 库存流水（v3.60.18 · P0）—— 库存**怎么变的**
// ══════════════════════════════════════════════════════════════

/**
 * 一条流水。
 *
 * 🔴 `delta` 是**变化量**，不是存量：正数为入库、负数为消耗。
 *    「还剩多少」**不在这一层** —— 它由 `item.quantity` 反推一次（纯展示），
 *    因为存量只有一个真源（同后端的「流表永不出现存量列」）。
 */
export interface SurvivalFlow {
  id: number
  item_id: number | null
  item_name: string
  category_name: string
  unit_name: string
  delta: number
  channel: string
  channel_label: string
  reason: string
  reason_label: string
  occurred_at: string | null
  reverses_id: number | null
  /** 已被撤销（前端据此**不再显示**「撤销」按钮，而不是让用户点一下看报错） */
  reverted: boolean
  /** 物品已被删除 —— 历史仍在，只是指不回原物品 */
  item_missing: boolean
  note: string
  created_at: string | null
}

/**
 * 记一笔。
 *
 * ⚠️ `channel` 由**动作**决定，不让用户选：手工浮层一律 `manual`（默认值）。
 * ⚠️ `reason` 留空时**后端**按类别的消耗模式自动填（配餐 → 吃掉，其余 → 用掉）——
 *    前端不复制这张映射表，那是第二份口径。
 * ⚠️ 只送 `delta`，**绝不并列送「还剩几件」**：那是同一个事实的两种说法。
 */
export interface SurvivalFlowFormData {
  item_id: number
  delta: number | string
  channel?: string
  reason?: string
  note?: string
  occurred_at?: string | null
}

/** 批量：时间与原因是**整批一个**，不把单件表单复制 N 份 */
export interface SurvivalFlowBatchFormData {
  rows: SurvivalFlowFormData[]
  occurred_at?: string | null
}

/** 汇总的一行。⚠️ **一定带 `unit_name`**：跨单位不相加，桶内才可比。 */
export interface SurvivalFlowSummaryRow {
  unit_name: string
  consumed: number
  gained: number
  net: number
  count: number
  category_name?: string
  item_name?: string
}

/**
 * 按月汇总。
 *
 * 🔴 **刻意没有「总消耗 X 件」这个合计数** ——「3 斤米 + 2 罐罐头」不可通约。
 *    要说总量，只能按 `by_unit` 分别说。
 */
export interface SurvivalFlowSummary {
  month: string
  date_from: string
  date_to: string
  count: number
  consumed_count: number
  gained_count: number
  by_unit: SurvivalFlowSummaryRow[]
  by_category: SurvivalFlowSummaryRow[]
  by_item: SurvivalFlowSummaryRow[]
}
