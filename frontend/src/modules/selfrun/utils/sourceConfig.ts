/** 自我运转 · 取数方式（`source_config`）的唯一实现
 *
 * 🔴 为什么单独抽出来：模板库和「改这条 KPI」两处都要拼同一份 `source_config`。
 *    各写一份的话，`where` 的处理迟早分叉 —— 而分叉的表现是
 *    「同一件事在模板里配对了、落到 KPI 上就漏了一个条件」（或者反过来），
 *    页面上两个地方都看着正常。
 */
import type { SourceKind } from '../types/selfrunTypes'

/** 界面上的 `where` 值：多选取数器是数组，单选是字符串 */
export type WhereValue = string | string[]

/** `where` 里那个键的原始值 → 界面形态（多选 ⇒ 数组，单选 ⇒ 字符串） */
export function toFormValue(raw: unknown, list: boolean): WhereValue {
  if (list) {
    if (Array.isArray(raw)) return raw.map(String)
    return raw ? [String(raw)] : []
  }
  if (Array.isArray(raw)) return raw.length ? String(raw[0]) : ''
  return raw ? String(raw) : ''
}

/**
 * `source_kind` + `where` 组装成 `source_config`。
 *
 * 🔴 **编辑时不能整包替换 `where`** —— 内置模板的 `bill_income` 带着
 *    `transaction_type` / `category` 两个固定条件，它们不在界面上；
 *    整包替换会把它们**静默抹掉**（表现是「改了个名字，收入验证的数就变了」）。
 *    所以：在**原始 where 上叠加**，只动界面上真的有的那个键。
 */
export function buildSourceConfig(
  sourceKind: SourceKind,
  readerKind: string,
  whereKey: string | undefined,
  whereValue: WhereValue,
  baseWhere: Record<string, unknown>,
): Record<string, unknown> {
  if (sourceKind === 'manual') return { kind: 'manual_sum' }

  const where: Record<string, unknown> = { ...baseWhere }
  if (whereKey) {
    // `!v` 同时兜住 `''`（下拉 clear 后的值）与 `undefined`（还没选过）——
    // 用 `v === ''` 会把 undefined 当成「有值」，存进去变成 `where: { work_kind: undefined }`，
    // 序列化时这个键悄悄消失，看起来像「没配」，但读代码会以为配了。
    const empty = Array.isArray(whereValue) ? whereValue.length === 0 : !whereValue
    if (empty) delete where[whereKey]
    else where[whereKey] = whereValue
  }
  return { kind: readerKind, where }
}
