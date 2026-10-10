/**
 * 生存资源盘点的展示口径（唯一实现）
 *
 * 🔴 这里只做「怎么显示」，**不做任何换算意义上的除法**。
 *    可支撑餐数、天数、期望值全在后端算好；前端碰到的数是终值。
 *    唯一允许的换算就是「天 → 年」，因为「1168 天」读不出是多少年，
 *    而它是纯展示，不参与任何判断。
 *
 * ⚠️ `null` 一律显示成「算不出来」而不是 0 / 「-」：
 *    前者说明「还没配好」，后者看起来像「真的是零」。
 *    四卡上出现 0 会让人以为明天就断粮。
 */

import type { SurvivalScenarioTriple } from '../types/survivalTypes'

const EMPTY = '算不出来'

/**
 * 天数 → 展示单位：≥ 365 天换成「X.X 年」，不四舍五入到整数年（差一整季）。
 *
 * 🔴 `formatDays` 与 `formatSpread` **必须共用这一份**（v3.59.10）。
 *    离差单走一条「永远给天」的路，卡片上就会出现
 *    「18.5 年 ~ 30.0 年 · ± 701.9 天」—— 同一行两种单位，
 *    读的人得先在脑子里把 701.9 天换成年，才知道它相对区间是大是小。
 */
function formatDayQuantity(value: number): string {
  if (value >= 365) return `${(value / 365).toFixed(1)} 年`
  return `${Number(value.toFixed(1))} 天`
}

/** 天数展示 */
export function formatDays(value: number | null | undefined, empty = EMPTY): string {
  if (value === null || value === undefined) return empty
  return formatDayQuantity(value)
}

/** 小时展示：≥ 100 取整，否则保留一位（读得出量级即可） */
export function formatHours(value: number | null | undefined, empty = EMPTY): string {
  if (value === null || value === undefined) return empty
  return value >= 100 ? `${Math.round(value)} 小时` : `${Number(value.toFixed(1))} 小时`
}

/** 餐数展示 */
export function formatMeals(value: number | null | undefined, empty = EMPTY): string {
  if (value === null || value === undefined) return empty
  return `${Number(value.toFixed(1))} 餐`
}

/** 区间文案：`26 ~ 58 天`；三档缺一档就退化成单值 */
export function formatScenarioRange(days: SurvivalScenarioTriple | null | undefined): string {
  if (!days) return EMPTY
  const { optimistic: o, likely: m, pessimistic: p } = days
  if (o === null || p === null) return m === null ? EMPTY : formatDays(m)
  return `${formatDays(p, '')} ~ ${formatDays(o, '')}`.trim()
}

/**
 * 三档的档位标签。
 *
 * ⚠️ 语义铁律：**乐观 = 消耗慢 = 撑得久**。
 *    「最乐观」永远指「省着用能撑多久」，不是「情况最好的日子」。
 */
export const SCENARIO_LABELS: Record<string, string> = {
  optimistic: '最乐观（省着用）',
  likely: '最可能',
  pessimistic: '最悲观（放开用）',
}

/**
 * 离散度说明：越小越说明这个估计稳。
 *
 * ⚠️ 单位跟 `formatDays` 走（见 `formatDayQuantity`），不自己拼「天」——
 *    乐观/悲观区间用「年」而离差用「天」，是同一行里的两把尺子。
 */
export function formatSpread(value: number | null | undefined): string {
  if (value === null || value === undefined) return EMPTY
  return `± ${formatDayQuantity(value)}`
}

/** 瓶颈 → 标签配色（与卡片的语义色一致） */
export function bottleneckType(bottleneck: string): 'danger' | 'warning' | 'success' {
  if (bottleneck === 'asset') return 'danger'
  if (bottleneck === 'cash') return 'warning'
  return 'success'
}

/** 配方行的餐位标签配色：主食位可替代、必配位缺一不可 */
export function roleTagType(role: string): 'success' | 'info' {
  return role === 'staple' ? 'success' : 'info'
}

/** 问题码 → 是否属于「必须去修，否则数字不可信」 */
const BLOCKING_ISSUE_CODES = new Set([
  'no_unit', 'unit_mismatch', 'bad_quantity', 'missing_item',
  'no_days_per_unit', 'no_recipe', 'empty_recipe',
])

export function isBlockingIssue(code: string): boolean {
  return BLOCKING_ISSUE_CODES.has(code)
}

// ── 盘点快照（v3.59.0 二期） ──

/**
 * 变化方向 → 语义色。
 *
 * ⚠️ 这里**刻意不套「涨红跌绿」**：那套是**价格**语义（涨 = 赚 = 红）。
 *    生存天数变长是好事（更抗饿），变短才是坏消息 —— 颜色跟**语义**走，
 *    不跟数值方向走。照搬价格配色会让人把「补了货」读成坏消息。
 */
export function deltaType(kind: string | null | undefined): 'success' | 'danger' | 'info' {
  if (kind === 'up') return 'success'
  if (kind === 'down') return 'danger'
  return 'info'
}

/**
 * 与上期的差值文案。
 *
 * ⚠️ 两种「没有数」要分开说：
 *    · `kind === 'flat'` → 持平（后端已按 epsilon 判过，这是真持平）
 *    · 值为 null → 不可比（有一端算不出来）
 *    混成一句「-」会把「不知道」显示成「没变化」。
 */
export function formatDelta(
  value: number | null | undefined,
  kind?: string | null,
  empty = '不可比',
): string {
  if (kind === 'flat') return '持平'
  if (value === null || value === undefined) return empty
  const sign = value > 0 ? '+' : '-'
  return `${sign}${Number(Math.abs(value).toFixed(1))} 天`
}

/** 短日期：折线横轴用 `09-21`（同一段区间里年份通常一样，省下的宽度给刻度） */
export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return ''
  return iso.slice(5, 10)
}

/** 两期相隔多久 */
export function formatInterval(days: number | null | undefined): string {
  if (days === null || days === undefined) return ''
  return days > 0 ? `间隔 ${days} 天` : '同日'
}

// ── 按次计量（v3.59.3） ──

/**
 * 按次计量的「原话」：`每 3 天用 1 次`。
 *
 * ⚠️ 只是把后端给的四个字段拼起来，**不做任何换算** ——
 *    「每周 2 次 = 3.5 天一次」那类换算是计算层的活（唯一真源），
 *    前端再算一遍就有了第二份口径，改后端时必然漏改。
 */
export function formatUseCycle(
  num: number | null | undefined,
  unitLabel: string,
  times: number | null | undefined,
): string {
  if (num === null || num === undefined || times === null || times === undefined) return ''
  return `每 ${Number(num.toFixed(2))} ${unitLabel || '天'}用 ${Number(times.toFixed(2))} 次`
}

/** 计量口径标签：未填也要说出来，不能显示成空 */
export function lifeModeLabel(mode: string | null | undefined): string {
  if (mode === 'cycle') return '按次'
  if (mode === 'day') return '按天'
  return '未填'
}

// ── 实盘盘点（v3.59.3） ──

/**
 * 盘盈盘亏的方向色。
 *
 * ⚠️ 刻意**不套「涨红跌绿」那一套**：那套是**价格**语义（涨 = 赚 = 红）。
 *    盘点的差异只说明「实物与账面不一致」这个事实 ——
 *    亏了要去看看是不是消耗比记的快，盈了要去看看是不是漏记了消耗，
 *    两边都不是单纯的好消息或坏消息。所以这里只用「要不要留意」来上色：
 *    核对无误给绿（唯一确定的好结果），有差异给提醒色。
 */
export function deltaKindType(kind: string | null | undefined): 'success' | 'warning' | 'danger' {
  if (kind === 'flat') return 'success'
  if (kind === 'deficit') return 'danger'
  return 'warning'
}

/**
 * 盘盈盘亏文案：`+2` / `-6` / `0`。
 *
 * ⚠️ 正负号要显式给出来 —— 只给绝对值时「少了 6 件」和「多了 6 件」
 *    看起来一模一样，而它们要采取的行动完全相反。
 */
export function formatStocktakeDelta(
  value: number | null | undefined,
  empty = '—',
): string {
  if (value === null || value === undefined) return empty
  const num = Number(value.toFixed(2))
  if (num === 0) return '0'
  return num > 0 ? `+${num}` : `${num}`
}

/** 数量文案：`10 件`；没给单位就只给数 */
export function formatQuantity(
  value: number | null | undefined,
  unit = '',
  empty = '—',
): string {
  if (value === null || value === undefined) return empty
  const num = Number(value.toFixed(2))
  return unit ? `${num} ${unit}` : String(num)
}

/**
 * 距上次盘点多久。
 *
 * ⚠️ 「从未盘点」不能显示成「0 天前」—— 那读起来像「今天刚盘过」，
 *    而事实恰好相反。这正是二期立下的「空值不许重载两种含义」。
 */
export function formatStocktakeGap(days: number | null | undefined): string {
  if (days === null || days === undefined) return '从未盘点'
  if (days === 0) return '今天盘过'
  return `${days} 天前`
}

/**
 * 「上次盘点」这一格的**整格文案** —— 日期 + 间隔，一句话说完。
 *
 * 🔴 存在的理由是一次真实的显示事故（2026-09-29）：
 *    日期与间隔原本是两个相邻的 `<span>`，靠 CSS `margin-left` 拉开 ——
 *    于是**漏写那个 class 的地方就粘成了 `2026-09-236 天前`**
 *    （「2026-09-23」+「6 天前」），看起来像一个乱码日期。
 *    它在清单页正常、在盘点弹窗里粘住，因为两处的样式类不同名。
 *
 *    ⇒ 改成**由函数产出整格字符串**、分隔符写在串里：
 *      分隔符比间距稳 —— 换主题、换字号、漏写 class 都不会再粘。
 *      三处调用（清单 / 弹窗 / 类别明细）从此共用一份，不可能再各粘各的。
 */
export function formatLastStocktake(
  date: string | null | undefined,
  days: number | null | undefined,
): string {
  const gap = formatStocktakeGap(days)
  return date ? `${date} · ${gap}` : gap
}

/**
 * 备注（自由文本）的展示：**空就留白**，不留「—」。
 *
 * ⚠️ 这条与数值的空值规则**相反**，是刻意的：
 *    数值的 `null` 有歧义（「真的是 0」与「算不出」），必须显式占位区分；
 *    备注是自由文本，「空」只有一种含义 —— 没写。
 *
 * 实测（2026-09-29）：明细备注 **10 行全空**、记录备注 5/8 是空 ——
 * 一屏里 15 个「—」，读者要逐个确认「这里没有信息」，全是噪音。
 */
export function formatNote(text: string | null | undefined): string {
  return text ?? ''
}

/**
 * 记录时刻：从 ISO 字符串里切出 `HH:MM`。
 *
 * 🔴 **绝不 `new Date(iso).toLocaleString()`**。
 *    服务端 `isoformat()` 已经本地化到 `+08:00`（实测
 *    `2026-09-29T10:50:23.116322+08:00`），前端再解析成 Date 又格式化一次，
 *    就是**同一件事两把尺子**：系统时区一改，这里会静默差 8 小时，
 *    而界面上只是「时间看着不太对」，没人能一眼发现。
 *    与 `formatDateShort`（`slice(5, 10)`）是同一套做法。
 *
 * ⚠️ 格式不符时返回**空串**（不显示），而不是切出一段乱码 ——
 *    宁可不显示，也不显示错的。
 */
const ISO_TIME = /^\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})/

export function formatClock(iso: string | null | undefined): string {
  if (!iso) return ''
  const matched = ISO_TIME.exec(iso)
  return matched ? matched[1] : ''
}

/** 「一次盘点的结论」徽章 —— 三态的顺序与配色在此**单一实现** */
export interface StocktakeResultTag {
  type: 'warning' | 'danger' | 'success'
  label: string
}

/**
 * 一次盘点的结论标签。
 *
 * ⚠️ 配色沿用 `deltaKindType` 的那套（核对无误给绿、有差异给提醒色），
 *    **仍然不套「涨红跌绿」** —— 那套是价格语义，见 `deltaKindType` 的说明。
 *    这里只是把模板里原本 inline 的三个 `v-if` 收成一份，口径一字未改。
 */
export function stocktakeResultTags(head: {
  surplus_count: number
  deficit_count: number
  flat_count: number
}): StocktakeResultTag[] {
  const tags: StocktakeResultTag[] = []
  if (head.surplus_count) tags.push({ type: 'warning', label: `盘盈 ${head.surplus_count}` })
  if (head.deficit_count) tags.push({ type: 'danger', label: `盘亏 ${head.deficit_count}` })
  if (head.flat_count) tags.push({ type: 'success', label: `核对无误 ${head.flat_count}` })
  return tags
}
