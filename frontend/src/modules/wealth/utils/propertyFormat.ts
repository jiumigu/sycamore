/**
 * 物件资产 · 展示格式化（v3.60.0）
 *
 * 🔴 这个文件承担本模块前端**唯一**的两处换算：
 *    ① 年 ↔ 月（界面按年填、接口按「月」收发）
 *    ② 金额 null → 「—」
 *    别处不许再写 `* 12` / `/ 12`，也不许再写一个 `?? 0`
 *    —— 口径一旦有两份，改一处必然漏另一处，而漏掉是**静默**的。
 *
 * 🔴 本文件里**没有第二个除法**：净值、月折旧、剩余月数全部来自后端
 *    （`services/property_calc.py` 唯一真源）。这里只把数说成人话。
 *
 * ⚠️ 金额一律走 `shared/utils/format.ts`（唯一实现，隐私掩码也在里面）——
 *    本模块不新写第二份金额格式化。
 */

import { formatSignedAmount } from '@/shared/utils/format'
import type { PropertyZeroReason } from '../types/propertyTypes'

const MONTHS_PER_YEAR = 12

// ──────────────────────────────────────────────────────────────
// 年 ↔ 月（本模块前端唯一换算点）
// ──────────────────────────────────────────────────────────────

/**
 * 「年」→「月」：界面填 8.5（8 年 6 月），接口收 102。
 *
 * ⚠️ 后端 `property_calc.years_to_months()` 是同一判据的另一份实现 ——
 *    它在服务端用于文案与测试，**不参与接口接收**（接口字段就叫
 *    `lifespan_months`，本来就按月收）。两边各自只此一份，是刻意的取舍。
 * ⚠️ 留空返回 null，**不返回 0**："没填年限"与"年限是 0"是两件事
 *    （后者会让除法炸掉，而且界面上看起来一样）。
 */
export function yearsToMonths(years: number | null | undefined): number | null {
  if (years === null || years === undefined || Number.isNaN(years)) return null
  return Math.round(years * MONTHS_PER_YEAR)
}

/**
 * 「月」→「年」：编辑时把 102 填回输入框成 8.5。
 *
 * ⚠️ 只在**表单回填**时用；展示一律用 `formatMonths`（说人话，不是小数年）。
 */
export function monthsToYears(months: number | null | undefined): number | null {
  if (months === null || months === undefined || Number.isNaN(months)) return null
  return months / MONTHS_PER_YEAR
}

// ──────────────────────────────────────────────────────────────
// 月数说人话
// ──────────────────────────────────────────────────────────────

/**
 * 月数 → 「3 年 2 月」/「5 月」/「—」。
 *
 * ⚠️ 负数**原样保留符号**（「-2 年 2 月」）—— 超期是事实，不是错误，
 *    不在这里悄悄取绝对值，也不在这里换成「已超期」（那是另一句话，见
 *    `formatOverdue`）。把两个语义混进一个函数，调用方就再也分不出
 *    「还有 2 年」和「超期 2 年」。
 */
export function formatMonths(months: number | null | undefined): string {
  if (months === null || months === undefined || Number.isNaN(months)) return '—'
  const sign = months < 0 ? '-' : ''
  const total = Math.abs(Math.trunc(months))
  const years = Math.floor(total / MONTHS_PER_YEAR)
  const rest = total % MONTHS_PER_YEAR
  if (years && rest) return `${sign}${years} 年 ${rest} 月`
  if (years) return `${sign}${years} 年`
  return `${sign}${rest} 月`
}

/** 「已超期 2 年 2 月」—— 中性标注，**不带颜色、不带建议** */
export function formatOverdue(overdueMonths: number | null | undefined): string {
  if (overdueMonths === null || overdueMonths === undefined || overdueMonths <= 0) return ''
  return `已超期 ${formatMonths(overdueMonths)}`
}

/**
 * 明细行「已用 / 计划」那一格：`5 年 3 月 / 10 年`。
 *
 * ⚠️ 两段各算各的：已用算不出但年限填了，就显示「— / 10 年」，
 *    而不是整格变成「—」（那是另一件事，会让人以为年限也没填）。
 */
export function formatUsedVsPlanned(
  ageMonths: number | null | undefined,
  lifespanMonths: number | null | undefined,
): string {
  if (ageMonths === null || ageMonths === undefined) return '—'
  return `${formatMonths(ageMonths)} / ${formatMonths(lifespanMonths)}`
}

/** 「计划用 8 年」—— 试算行用的短句 */
export function formatPlannedLifespan(months: number | null | undefined): string {
  if (months === null || months === undefined) return '未填年限'
  return `计划用 ${formatMonths(months)}`
}

// ──────────────────────────────────────────────────────────────
// 金额
// ──────────────────────────────────────────────────────────────

/** 响应里的金额是字符串 —— 要算数先转回来；空值保持 null，**不掉成 0** */
export function toNumberOrNull(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isNaN(parsed) ? null : parsed
}

/**
 * 金额 → `¥1,234.50`；**null → 「—」**。
 *
 * 🔴 绝不能直接调 `formatAmount(value)`：它对 null 返回 `0.00`，
 *    那会把「算不出来」显示成「真的折完了」—— 两件事该采取的行动相反
 *    （一个该补数据，一个该换新），而界面上长得一模一样。
 * ⚠️ 走 `formatSignedAmount`（项目统一口径：货币符号在前、正负号紧随其后），
 *    隐私掩码在它内部完成，本模块不碰掩码。
 */
export function formatMoneyOrDash(value: string | number | null | undefined): string {
  const parsed = toNumberOrNull(value)
  if (parsed === null) return '—'
  return formatSignedAmount(parsed)
}

// ──────────────────────────────────────────────────────────────
// 排序（在前端做，后端刻意不开 `?ordering=`）
// ──────────────────────────────────────────────────────────────

/** 表头点出来的排序方向；null = 不按金额排（回到后端的默认序） */
export type AmountSortOrder = 'asc' | 'desc' | null

/**
 * 按金额排序 —— **未填金额的恒排最后，两个方向都是**。
 *
 * 🔴 这是验收标准第 12 条：未填金额不是一个「便宜」的值。
 *    若按 0 参与排序，升序时那些「想不起来多少钱」的物件会挤在最前面，
 *    看起来像一堆破铜烂铁；而实际上它们只是**没填**。
 *    「未填金额」与「金额 0」在界面上必须始终是两件事。
 */
export function sortItemsByAmount<T extends { purchase_amount: string | null }>(
  rows: T[],
  order: AmountSortOrder,
): T[] {
  if (!order) return rows
  return [...rows].sort((a, b) => {
    const left = toNumberOrNull(a.purchase_amount)
    const right = toNumberOrNull(b.purchase_amount)
    if (left === null && right === null) return 0
    if (left === null) return 1
    if (right === null) return -1
    return order === 'asc' ? left - right : right - left
  })
}

/** 金额排序的读法提示 —— 让「未填恒排最后」这件事在界面上说出来 */
export function amountSortHint(order: AmountSortOrder): string {
  if (!order) return ''
  return order === 'asc' ? '金额从低到高（未填金额的排在最后）' : '金额从高到低'
}

/**
 * 净值为 0 时那行小字 —— 必须说清是「折完了」还是「坏了」。
 *
 * 🔴 净值 0 现在有**两个来源**（2026-09-26 起）：
 *      `depreciated` → 计划年限真的用完了，该考虑换新；
 *      `broken`      → 还没到年限但坏了，该修或者该扔。
 *    两者该采取的行动不同，所以不能都写「已折完」——
 *    把「坏了」说成「用够了」正是本模块最防的那种**看着合理的错话**。
 *
 * ⚠️ 只查表，**不在这里判** `condition === 'broken'`：
 *    在后端判是「口径」，在前端判是「第二份口径」，而第二份迟早被漏掉。
 *    取不到（净值不为 0）返回空串，调用方据此不渲染。
 */
export function formatZeroReason(reason: PropertyZeroReason | null | undefined): string {
  if (reason === 'broken') return '损坏归 0'
  if (reason === 'depreciated') return '已折完'
  return ''
}

/**
 * 未计入件数的一句话 —— 几个原因分开说。
 *
 * 🔴 「没填金额」与「填了但算不出」必须分开报：一个要去补价格、
 *    一个要去补日期或年限。合成一句「5 件未计入」就看不出去补哪个了。
 *
 * 🔴 第三个原因（`broken_count`，2026-09-26 随「损坏 ⇒ 净值归 0」加的）**性质不同**：
 *    那些件**是计入的**，只是按 0 计。所以措辞必须写「按 0 计」——
 *    写成「未计入」会把它跟前两个混成一类，而那两类的动作是「去补数据」，
 *    这一类的动作是「不用补，它就是不值钱了」。
 *    排在**最前**也是这个原因：紧接「计入 N 件」，读起来是「其中 N 件按 0 计」。
 */
export function formatExcludedHint(block: {
  unpriced_count: number
  unvalued_count: number
  /** 只有净值块会有这个键 —— 原值合计与状况无关 */
  broken_count?: number
}): string {
  const parts: string[] = []
  if (block.broken_count) parts.push(`${block.broken_count} 件损坏按 0 计`)
  if (block.unpriced_count) parts.push(`${block.unpriced_count} 件未填金额`)
  if (block.unvalued_count) parts.push(`${block.unvalued_count} 件算不出净值`)
  return parts.join(' · ')
}
