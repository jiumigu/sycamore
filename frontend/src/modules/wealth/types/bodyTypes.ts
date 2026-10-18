/**
 * 身上之物（v3.62.4）类型定义
 *
 * ⚠️ 与 `propertyTypes.ts` / `survivalTypes.ts` **刻意分开、不互相 import**：
 *    物件资产是「已经买回来的」（有价格、有年限），
 *    物品清单是「会被用完的」（答案是天），
 *    这边是「**我该有什么、称不称心**」—— 一样数量都不记，只记结论。
 *
 * 🔴 四个必须记住的类型事实：
 *    ① `satisfaction` 为空 **不等于**「凑合」。空的两种来由由后端下发
 *       （`no_item` / `unrated`），**前端只查表、不自己拿别的字段推** ——
 *       推错了没人发现，而且界面上看起来完全正常。
 *    ② 三把尺子（进度 / 满意 / 归属）**正交、互不推导**：
 *       「已找到 + 凑合」与「寻找中 + 称心」都是合法状态，不是矛盾数据。
 *    ③ 两个关联源（`property_id` / `survival_item_id`）**最多挂一个** ——
 *       互斥在后端校验，前端只管把 `linked_kind` 显示出来。
 *    ④ 枚举 label 一律随接口下发（`/wealth/body/meta/`），前端**零副本**。
 */

// `bands` 的元组形状与财富侧比率模块同源，直接复用，别另立一份
import type { RatioBand } from './wealthTypes'

// ──────────────────────────────────────────────────────────────
// 枚举（真源在后端 constants.py，这里只是为了类型收窄）
// ──────────────────────────────────────────────────────────────

/**
 * 进度轴 —— 回答「这件事办到哪一步了」。
 *
 * 🔴 **刻意没有「不想找了」**：那个值会变成兜底桶，同时装
 *    「真的不需要」和「暂时懒得找」两种相反的东西。
 *    不需要这一条了，出口是**删掉它**（位本来就是你自己建的）。
 */
export type BodyFindStatus = 'todo' | 'searching' | 'settled'

/** 满意轴 —— 回答「现在顶着用的这件，我称不称心」。**可空**，且空 ≠ 凑合 */
export type BodySatisfaction = 'meh' | 'ok' | 'good'

/** 满意为空时的**两种来由** —— 由后端算，前端只查表 */
export type BodyBlankReason = 'no_item' | 'unrated'

/** 关联挂在哪个池子上 —— 由后端下发，前端不做三分支判断 */
export type BodyLinkedKind = 'property' | 'survival_item'

// ──────────────────────────────────────────────────────────────
// 部位（轻量主数据）
// ──────────────────────────────────────────────────────────────

/**
 * 部位 —— 眼 / 耳 / 鼻 / 口 / 脸 / 头发 / 手 / 指甲 / 身体四肢 / 脚 / 私处
 *
 * ⚠️ 它**是主数据表、不是固定枚举**：你列的六项里「指甲」是「手」的一部分，
 *    写死六个值的话「口腔」「耳朵」「私处」「头发」就没有地方放。
 *    随时可以自己增删改。
 */
export interface BodyPart {
  id: number
  name: string
  sort_order: number
  note: string
  /** 其下还有几条位 —— 它同时也是「为什么这个部位删不掉」的答案 */
  need_count: number
}

export interface BodyPartFormData {
  name: string
  sort_order?: number
  note?: string
}

export interface BodySeedResult {
  created: number
  updated: number
  skipped: number
  parts: BodyPart[]
}

// ──────────────────────────────────────────────────────────────
// 位
// ──────────────────────────────────────────────────────────────

export interface BodyNeed {
  id: number
  part_id: number
  part_name: string
  /** 这个部位要的那样东西：眼镜 / 护手霜 / 指甲剪 */
  name: string

  // ── 进度轴 ──
  find_status: BodyFindStatus

  // ── 满意轴（可空）──
  satisfaction: BodySatisfaction | null
  /**
   * 空的**来由**，后端下发；评过之后是 `null`。
   *
   * 🔴 拿 `property_id === null` 在前端自己推一遍，就是第二份口径 ——
   *    下次改规则时漏掉的就是它，而漏掉是静默的。
   */
  satisfaction_blank_reason: BodyBlankReason | null

  /** 想找什么样的 —— 「已找到」之后**不清空**，那是你当时的标准 */
  wish: string
  note: string

  // ── 归属（事实，最多挂一件）──
  property_id: number | null
  survival_item_id: number | null
  /** 挂在哪张表；没挂时是 null */
  linked_kind: BodyLinkedKind | null
  /** 「物件资产」/「物品清单」—— 由后端给，前端不自己映射 */
  linked_kind_label: string
  /** 那件东西叫什么。⚠️ 只给名字，价格 / 天数一律不搬过来（那是两份口径） */
  linked_name: string

  /**
   * 好恶物档案馆回流的评价 —— **只读**。
   *
   * 🔴 `null` = 还没评过 ⇒ 界面**什么都不显示**（不是灰色的「无」）。
   * ⚠️ 它与本模块的「满意」是两把正交的尺子：一件东西可以
   *    「档案馆 👎 踩坑」而「这里 凑合」（一个问值不值，一个问这个位够不够用），
   *    结论相反是**允许的** —— 界面不做任何「要不要同步」的提示。
   */
  treasure_badge: string | null
  treasure_record_id: number | null

  created_at: string | null
  updated_at: string | null
}

/** 新增 / 编辑的入参 —— 派生字段（`blank_reason` / `linked_*`）一律不送 */
export interface BodyNeedFormData {
  part_id: number
  name: string
  find_status?: BodyFindStatus
  /** `null` = 撤掉评分；**不要送空串**（后端会归一，但前端不该制造两种空） */
  satisfaction?: BodySatisfaction | null
  wish?: string
  note?: string
  property_id?: number | null
  survival_item_id?: number | null
}

// ──────────────────────────────────────────────────────────────
// 汇总与口径
// ──────────────────────────────────────────────────────────────

/**
 * 顶部计数。
 *
 * 🔴 `pending_count`（还没搞定）**必须等于**点进去看到的行数 ——
 *    它与列表筛选走的是后端同一个函数，不是两处各写一遍。
 */
export interface BodySummary {
  total: number
  todo: number
  searching: number
  settled: number
  pending_count: number
}

export interface BodyOption {
  value: string
  label: string
}

/**
 * 满意为空时的说明 —— `short` 是格子里的字，`label` 是悬停的解释。
 *
 * ⚠️ 两个都给是有意的：只给长句的话前端得自己截短，那是第二份映射，
 *    改后端文案时它不会被改到，而界面上照旧说得通。
 */
export interface BodyBlankReasonOption {
  value: BodyBlankReason
  short: string
  label: string
}

/**
 * 口径气泡 —— 结构与 `RatioMeta` 一致，因为共用同一个气泡组件。
 * `bands` **恒为空数组**：本模块不设绝对判定线（几条算多只有你自己知道）。
 */
export interface BodyMetricMeta {
  key: string
  label: string
  unit: string
  /** 恒为 'neutral' —— 没搞定不代表坏，称心也不代表好 */
  direction: string
  formula: string
  /** 口径说明，逐行渲染；**纯文本**，不含 Markdown 标记 */
  note: string[]
  bands: RatioBand[]
}

export interface BodyMeta {
  find_statuses: BodyOption[]
  satisfactions: BodyOption[]
  blank_reasons: BodyBlankReasonOption[]
  metric_meta: BodyMetricMeta[]
  part_seeds_available: boolean
  /** 页面里固定那几句说明 —— 放后端是为了它们只有一个来源 */
  subtitle: string
  satisfaction_note: string
}

// ──────────────────────────────────────────────────────────────
// 展示辅助（**只做查表与取字，不做任何判断**）
// ──────────────────────────────────────────────────────────────

/** 原因码 → 格子里的那个短字（「—」/「未评」）；查不到时给破折号 */
export function blankReasonShort(
  meta: BodyMeta | null,
  reason: BodyBlankReason | null,
): string {
  if (!reason) return '—'
  return meta?.blank_reasons?.find((r) => r.value === reason)?.short ?? '—'
}

/** 原因码 → 悬停那句完整解释；查不到时给空串（**不编一句话**） */
export function blankReasonLabel(
  meta: BodyMeta | null,
  reason: BodyBlankReason | null,
): string {
  if (!reason) return ''
  return meta?.blank_reasons?.find((r) => r.value === reason)?.label ?? ''
}
