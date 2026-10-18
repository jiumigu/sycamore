/**
 * 好恶物档案馆 · 类型（v3.60.32）
 *
 * 🔴 **本文件不再有类别文案**。过去那份 `CATEGORY_OPTIONS` 只有一个 label 版本，
 *    于是「🏪 好店」会出现在歹物的下拉里 —— 文案必须**按侧取**，而它只在后端
 *    有一份（`apps/treasure/constants.CATEGORY_LABELS_BY_TYPE`，经 `/meta/` 下发）。
 *    前端自己再写一份 = 第二个真源，下次改口径必然漏一份。
 */

/** 记录对象：它决定显示哪些字段（实物才有「在哪能找到」，方法才有「方法归类」） */
export const SUBJECT_KIND_PHYSICAL = '实物'
export const SUBJECT_KIND_METHOD = '方法'

export interface LinkedFacts {
  kind: 'property' | 'survival_item'
  name: string
  purchase_date: string | null
  purchase_amount: number | null
  age_months: number | null
  current_value: number | null
  quantity: number | null
  unit_name: string | null
  category_name: string | null
}

export interface GoodThing {
  id: number
  user_id: number
  record_type: string
  record_type_display?: string
  subject_kind: string
  subject_kind_display?: string
  name: string
  category: string
  category_display?: string
  method_group: string
  method_group_display?: string
  scene: string
  why_good: string
  still_available: boolean
  where_to_find: string
  avoid_reason: string
  consequence: string
  property: number | null
  survival_item: number | null
  linked_kind: 'property' | 'survival_item' | null
  linked_id: number | null
  linked_name: string | null
  linked_facts: LinkedFacts | null
  /** 是否已写理由 —— ⭐「待补理由」出口的判据（后端算，前端不自己判空） */
  has_reason: boolean
  tags: string
  rating: number
  created_at: string
  updated_at: string
}

export interface TreasureOption {
  value: string
  label: string
  hint?: string
}

/** `/meta/` 下发口径与枚举 —— 前端**不硬编码任何文案或选项** */
export interface TreasureMeta {
  subject_kind_options: TreasureOption[]
  method_group_options: TreasureOption[]
  /** ⚠️ 两侧各一套：`{好: [...], 歹: [...]}` */
  categories_by_type: Record<string, TreasureOption[]>
  record_type_options: TreasureOption[]
}

/** 「输入即搜实物」的候选（档案 → 实物的反向入口） */
export interface LinkCandidate {
  kind: 'property' | 'survival_item'
  id: number
  name: string
  source_label: string
  category_name: string
  /** 物件状况 —— 用于「要不要记成歹物？」的**提示**（绝不自动改） */
  condition: string
  /** 类别预填建议（后端按关键词猜的，用户可改） */
  suggest_category: string
}

export interface LinkCandidateResult {
  rows: LinkCandidate[]
  total: number
  limit: number
}
