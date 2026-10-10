/**
 * 实盘盘点 · 挑选判据（唯一实现）
 *
 * 这个模块存在的理由是**可维护性**，不是新功能。
 *
 * 2026-09-29 优化前，「勾上该盘的 N 件」这件事在**两个组件里各写了一遍**：
 *     SurvivalItemLedger.vue  → selectDue()
 *     SurvivalStocktakeDialog.vue → checkDue()
 * 两份逻辑长得像、其实不等价（一个只处理勾选，另一个顺带写入实盘默认值），
 * 改一处不会带着另一处改，而漏掉是**静默**的 —— 用户只会看到两个地方的
 * 「该盘的」件数对不上。⇒ 抽到这里，两处都调它。
 *
 * ══════════════════════════════════════════════════════════════
 * 🔴 核心判据：「该盘了」与「最久没盘」是两件事，不许合并
 * ══════════════════════════════════════════════════════════════
 *
 * 两者回答的问题不同：
 *
 *   ① 「该盘了」（`stocktake_due`，**后端判**）——
 *      判据：设了盘点周期、且距上次盘点已达到这个周期。
 *      这是**提醒**：它亮起来的意思是「按你自己定的规矩，这件该数一数了」。
 *
 *   ② 「最久没盘」（本模块的排序）——
 *      它是**事实顺序**：谁离上次盘点最远，谁排前面。
 *      从未盘点过的排最前（它确实离得最远）。
 *
 * 为什么必须分开 —— 2026-09-21 立下的那条判据：
 *
 * > 若把「从未盘过」也算作该盘，那所有没设周期的物品会一律标红 ——
 * > 等于没有标，用户很快就学会无视这个标记。
 *
 * 实测（2026-09-29）：43 件物品里 **0 件**设了盘点周期。
 * ⇒ `stocktake_due` 恒为 false ⇒ 「勾上该盘的 0 件」这枚按钮**永远是灰的**，
 *    批量入口实际上不存在。而它旁边一个解释都没有，用户看到的是「按钮坏了」。
 *
 * 但**根因不是判据写错了**，是那个字段在问一个用户答不上来的问题：
 *    「牛奶，多久该盘一次？」
 * 同一个弹窗里的「补货线」有 5 件填了 —— 因为那个问题有答案
 *（「降到 2 包就该补」）。
 *
 * ⇒ 处置方式不是把判据放宽（那会毁掉提醒的可信度），而是
 *   **另加一条不依赖任何配置的批量入口**：按「最久没盘」挑。
 *   零配置、开箱可用，且**仍然不打「该盘了」标签**。
 *
 * ⚠️ 别忘了：本模块只负责**排序与挑件**，它不下发任何标签、
 *    也不改写 `stocktake_due`（那是后端的事）。
 */

import type { SurvivalStocktake, SurvivalStocktakeLine } from '../types/survivalTypes'

/** 一次「按最久没盘」勾选的默认件数 —— 十件是「一次数得完」的量级 */
export const STALEST_PICK_COUNT = 10

/**
 * 能参与「最久没盘」排序的行必须提供的字段。
 *
 * 刻意用**结构类型**而不是具体接口：清单页的行是
 * `SurvivalItem ∪ worksheet`、弹窗的行是 `SurvivalWorksheetRow`，
 * 两种行模型不同（见设计稿 §2.2）—— 只要它们都带这两个字段，
 * 就能共用同一份判据，不必先统一模型。
 */
export interface StocktakePickable {
  /** 物品 id；两种行模型统一用这个键（清单页的行由 `id` 映射而来） */
  item_id: number
  /** 距上次盘点多少天；`null` = 从未盘点（**不是 0**，0 是「今天盘过」） */
  days_since_stocktake: number | null
}

/**
 * 「离上次盘点有多远」的可比较值 —— **越大越久**。
 *
 * ⚠️ `null`（从未盘点）排在**最前**，所以要给它一个比任何实数都大的值。
 *    不能简单地把 null 当 0 —— 那会让从未盘过的物件排到最后，
 *    而它恰恰是最该先数的（它连一次都没数过）。
 */
function staleness(days: number | null): number {
  return days === null ? Number.POSITIVE_INFINITY : days
}

/**
 * 按「最久没盘」排序：从未盘过的在最前，其余越久越前。
 *
 * ⚠️ 返回的是**新数组**，不改原数组 —— 调用点常常直接拿
 *    `store.worksheet` 或 computed 的产物，原地 `sort()` 会把共享状态改掉。
 * ⚠️ 同一天的（含多件「从未盘点」）按 `item_id` 兜底排序：
 *    否则 `Array.sort` 在不同浏览器/不同次渲染里的顺序不稳定，
 *    用户会看到列表「自己跳」。
 */
export function sortRowsByStaleness<T extends StocktakePickable>(rows: T[]): T[] {
  return [...rows].sort((a, b) => {
    const diff = staleness(b.days_since_stocktake) - staleness(a.days_since_stocktake)
    if (diff !== 0) return diff
    return a.item_id - b.item_id
  })
}

/**
 * 挑出「最久没盘」的前 N 件，返回它们的 id。
 *
 * ⚠️ 只挑传入的行 —— 调用点要先把**当前筛选结果**传进来。
 *    在用户看不见的行上悄悄勾选是说不清的（同原 `checkDue` 的注释）。
 */
export function pickStalestIds<T extends StocktakePickable>(
  rows: T[],
  count: number = STALEST_PICK_COUNT,
): number[] {
  return sortRowsByStaleness(rows).slice(0, count).map((row) => row.item_id)
}

/**
 * 这批行里有没有「该盘了」的。
 *
 * 用途只有一个：**在按钮位置给出一句解释**。
 * 43 件全未设周期时 `stocktake_due` 恒 false，原按钮会静静灰着 ——
 * 用户看到的是「按钮坏了」，而不是「我没有设过周期」。
 * ⇒ 恒空必须被解释（同硬坑⑫：把两个数并排念出来）。
 */
export function hasAnyDue(rows: { stocktake_due: boolean }[]): boolean {
  return rows.some((row) => row.stocktake_due)
}

/** 这批行里有没有一件设过盘点周期 —— 用来区分「没设过」与「设了但都没到期」 */
export function hasAnyCycle(rows: { stocktake_cycle_days: number | null }[]): boolean {
  return rows.some((row) => row.stocktake_cycle_days !== null)
}

// ══════════════════════════════════════════════════════════════
// 记录面板：把「盘点（头 + 明细）」拍平成一张表的行（v3.60.3）
// ══════════════════════════════════════════════════════════════
//
// 优化前，记录面板是**两张表**：主表（盘点日 / 物品数 / 结果 / 备注 / 操作），
// 展开后再塞一张子表（物品 / 类别 / 账面 / 实盘 / 盈亏 / 备注）——
// 11 处列定义、两套宽度，实测展开后左右两端都不齐；
// 而且想知道「盘了什么」必须先点开，可实测 8 条记录里 **6 条只盘了一件**。
//
// ⇒ 改成**一套网格 + 行合并**：明细直接成为表行，记录级字段
//   （日期 / 结果 / 备注 / 操作）靠 `span-method` 跨行合并。
//   读全全部记录从「18 行且点 8 次」变成「10 行且 0 次点击」。

/**
 * 拍平后的一行。
 *
 * `line === null` 只发生在**这次盘点没有任何明细**时 —— 它仍然要占一行
 * （否则那次盘点会在界面上整个消失），并把「没有明细」明说出来。
 * 静默吞掉一行记录，比显示一行「没有明细」糟得多。
 */
export interface StocktakeFlatRow {
  /** el-table 的 row-key：明细 id 是主键，全局唯一 */
  key: string
  record: SurvivalStocktake
  line: SurvivalStocktakeLine | null
  /** 该行所属盘点的明细行数（≥ 1）；占位行恒为 1 */
  groupSize: number
  /** 是不是该盘点的第一行 —— 记录级字段只在它身上渲染 */
  isGroupFirst: boolean
}

/**
 * 记录级列（跨行合并）的 prop 清单。
 *
 * 🔴 用 **prop** 判断，不用列序号 —— 序号与列顺序强耦合，
 *    哪天中间插一列，合并就会错到别的列上，而且**画面看着仍然正常**
 *    （只是数字串了行）。用 prop 判断的话，插列只是插列。
 *
 * 明细级的 `item_name` / `quantity` / `delta`（以及按需出现的 `line_note`）
 * 不在此列 —— 它们逐行渲染，一格不多一格不少。
 */
export const STOCKTAKE_RECORD_PROPS: ReadonlySet<string> = new Set([
  'stocktake_date', 'result', 'note', 'ops',
])

/**
 * 把盘点头 + 明细拍平成表行。顺序即显示顺序，**本函数不做排序**
 * （后端已按日期降序返回；再排一次就有了第二份排序口径）。
 *
 * ⚠️ 记录内**不重排**明细：沿用库里的顺序，也就是当初提交的顺序。
 */
export function flattenStocktakeRows(records: SurvivalStocktake[]): StocktakeFlatRow[] {
  const rows: StocktakeFlatRow[] = []
  for (const record of records) {
    const lines = record.lines ?? []
    if (!lines.length) {
      rows.push({
        key: `${record.id}-empty`,
        record,
        line: null,
        groupSize: 1,
        isGroupFirst: true,
      })
      continue
    }
    lines.forEach((line, index) => {
      rows.push({
        key: `${record.id}-${line.id}`,
        record,
        line,
        groupSize: lines.length,
        isGroupFirst: index === 0,
      })
    })
  }
  return rows
}

/**
 * 跨行合并的跨度：记录级列在**组首**返回整组高度，组内其余行返回 `[0, 0]`（不占格）。
 *
 * ⚠️ 记录级的判定走 `STOCKTAKE_RECORD_PROPS`，不在这里写死列名 ——
 *    哪天加一个记录级字段（比如「来源」），只改那个集合。
 */
export function recordSpan(
  row: StocktakeFlatRow,
  prop: string | undefined,
): [number, number] {
  if (!prop || !STOCKTAKE_RECORD_PROPS.has(prop)) return [1, 1]
  return row.isGroupFirst ? [row.groupSize, 1] : [0, 0]
}
