/**
 * 站点文案的**唯一实现**
 *
 * 「2 天 / 路过不过夜 / 天数待定」「12/02 到 / 到达待定」这两句，
 * 清单行与地图侧栏都要用。各写一份的下场是：一处把 `null` 显示成「0 天」，
 * 一处显示成「天数待定」，同一条数据在两个界面上说得不一样。
 */
import type { TravelPlanStop, TravelPlanStopCounts } from '../types/travelTypes'

/**
 * 停留天数。
 *
 * 🔴 `null` ≠ 0：`null` 是「还定不下来」，0 是「路过不过夜」。
 *    `Number(null) || 0` 会把两者压成同一个「0 天」。
 */
export function daysLabel(days: number | null): string {
  if (days === null) return '天数待定'
  if (days === 0) return '路过不过夜'
  return `${days} 天`
}

/** 到达日期：只留「月/日」（年份在计划标题上已经有了）；算不出来就说待定 */
export function arriveLabel(arriveDate: string | null): string {
  if (!arriveDate) return '到达待定'
  return `${arriveDate.slice(5).replace('-', '/')} 到`
}

/** 四类图标（键固定四类，顺序即展示顺序） */
const COUNT_ICONS: { key: keyof TravelPlanStopCounts; icon: string }[] = [
  { key: 'food', icon: '🍽 ' },
  { key: 'scenic', icon: '📍 ' },
  { key: 'transport', icon: '🚗 ' },
  { key: 'hotel', icon: '🏠 ' },
]

/** 只返回非零项：四类全 0 时一排「0」既占地方又像坏了 */
export function countChips(stop: Pick<TravelPlanStop, 'counts'>): { key: string; icon: string; n: number }[] {
  return COUNT_ICONS.map((c) => ({ key: c.key as string, icon: c.icon, n: stop.counts[c.key] ?? 0 }))
    .filter((c) => c.n > 0)
}
