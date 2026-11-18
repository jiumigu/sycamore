/**
 * 体重的两个称重单位 —— **唯一实现**。
 *
 * 🔴 换算系数、刻度（min/max/precision/step）、上次用过的单位，
 *    三样东西只此一份。原因不是「优雅」，是错法很隐蔽：
 *    · 系数写成 2 的地方多一处，就多一处「斤当 kg 存」；
 *    · 沿用对方的 min ⇒ 在 kg 模式下输 45 被静默钳到 50（界面不报错）；
 *    · kg 只给 1 位小数 ⇒ 125.3 斤换来的 62.65 被抹成 62.7，显示回斤变 125.4。
 *
 * 库里的真源只有一列 `weight_kg`：库里**不记录**这条是用哪个秤量的，
 * 所以任何方向都只能换算，不能反推。
 */

export type WeightUnit = 'kg' | 'jin'

export interface WeightUnitSpec {
  value: WeightUnit
  /** 按钮上的短名，如「KG」「斤」 */
  label: string
  /** 完整叫法，如「KG模式」 */
  fullLabel: string
  /** 输入框后缀 */
  suffix: string
  min: number
  max: number
  precision: number
  step: number
}

/** 1 kg = 2 斤。 */
export const JIN_PER_KG = 2

/** 库列 `weight_kg` 是 Decimal(5,2)，入库值必须落在 2 位小数内，否则 DRF 拒收。 */
export const KG_DECIMALS = 2

export const WEIGHT_UNITS: Record<WeightUnit, WeightUnitSpec> = {
  kg: { value: 'kg', label: 'KG', fullLabel: 'KG模式', suffix: 'kg', min: 25, max: 200, precision: 2, step: 0.1 },
  jin: { value: 'jin', label: '斤', fullLabel: '斤模式', suffix: '斤', min: 50, max: 400, precision: 1, step: 0.5 },
}

/** 顺序即界面顺序，与原体重弹窗一致（KG 在左、斤在右）。 */
export const WEIGHT_UNIT_OPTIONS: WeightUnitSpec[] = [WEIGHT_UNITS.kg, WEIGHT_UNITS.jin]

/** 记住上次用的模式：两个秤随机换着用，每次都重选太费事。 */
export const WEIGHT_UNIT_STORAGE_KEY = 'sycamore.health.weightUnit'

export function roundTo(value: number, precision: number): number {
  const factor = 10 ** precision
  return Math.round(value * factor) / factor
}

/** 读上次用过的单位；隐私模式 / 存储被禁用时回退到「斤」，不影响录入。 */
export function readStoredWeightUnit(): WeightUnit {
  try {
    const stored = localStorage.getItem(WEIGHT_UNIT_STORAGE_KEY)
    return stored === 'kg' || stored === 'jin' ? stored : 'jin'
  } catch {
    return 'jin'
  }
}

export function storeWeightUnit(unit: WeightUnit): void {
  try {
    localStorage.setItem(WEIGHT_UNIT_STORAGE_KEY, unit)
  } catch {
    // 存不进去不影响本次录入，下次打开回落默认值
  }
}

/** 界面上的数字 → 入库值（kg）。空值给 `null`，不拿 0 冒充「称了 0 公斤」。 */
export function toKg(displayed: number | null | undefined, unit: WeightUnit): number | null {
  if (displayed === null || displayed === undefined || !Number.isFinite(displayed)) return null
  const kg = unit === 'kg' ? displayed : displayed / JIN_PER_KG
  return Number(roundTo(kg, KG_DECIMALS).toFixed(KG_DECIMALS))
}

/** 入库值（kg）→ 界面上的数字，按给定单位与刻度取舍。 */
export function fromKg(kg: number, unit: WeightUnit): number | null {
  if (!Number.isFinite(kg)) return null
  const shown = unit === 'kg' ? kg : kg * JIN_PER_KG
  return roundTo(shown, WEIGHT_UNITS[unit].precision)
}

/**
 * 切换单位时把已填的数字按「同一个物理重量」换算过去。
 *
 * 🔴 只换标签不动数字 ⇒ 125（斤）原地变成 125 kg（= 250 斤）。
 *    链路上没有任何一步会报错，只会在趋势图上多一根暴涨柱。
 */
export function convertBetweenUnits(value: number, from: WeightUnit, to: WeightUnit): number {
  if (from === to) return value
  const kg = from === 'kg' ? value : value / JIN_PER_KG
  return roundTo(to === 'kg' ? kg : kg * JIN_PER_KG, WEIGHT_UNITS[to].precision)
}
