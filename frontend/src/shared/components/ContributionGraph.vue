<template>
  <div class="contrib-graph" ref="rootEl">
    <div class="contrib-header">
      <span class="contrib-title">{{ title }}</span>
      <span class="contrib-stats">
        活跃 {{ summary.total_days }} 天 · 峰值 {{ summary.max_date ? summary.max_date + ' · ' + formatValue(summary.max_value) : '-' }}
        <template v-if="isAttrMode"> · 主导 {{ attrSummaryText }}</template>
        · {{ years[0] }} ~ {{ years[years.length - 1] }}
      </span>
    </div>

    <!-- 年份窗口：多年图默认只显示最近 N 年，早期记录折在上方。
         工具条 sticky —— 滚到任意年份都能跳转或收起，不用滚回顶。 -->
    <div v-if="collapsible" class="contrib-toolbar">
      <div v-if="expanded" class="anchor-list">
        <span v-for="y in allYears" :key="y" class="anchor-chip" @click="scrollToYear(y)">{{ y }}</span>
      </div>
      <span class="anchor-toggle" @click="toggleExpand">
        {{ expanded ? '收起早期记录' : `展开更早的记录（${allYears[0]} – ${years[0] - 1}）` }}
      </span>
    </div>

    <div class="contrib-scroll" ref="scrollBox">
      <div class="contrib-body">
        <div class="contrib-year" v-for="year in years" :key="year" :data-year="year">
          <div class="year-cell">{{ year }}</div>
          <div class="year-content">
            <div class="month-labels" :style="{ width: gridWidth + 'px' }">
              <span v-for="ml in monthLabels(year)" :key="ml.col" class="month-label"
                    :style="{ left: (ml.col * (CELL + GAP) + 6.5) + 'px' }">{{ ml.name }}</span>
            </div>
            <div class="week-row">
              <div class="weekday-labels">
                <span v-for="wd in 7" :key="wd" class="wd-label" :style="{ height: CELL + 'px', lineHeight: CELL + 'px' }">
                  {{ WEEKDAYS[wd - 1] }}
                </span>
              </div>
              <div class="cells-grid">
                <div v-for="d in yearDays(year)" :key="d.date"
                     class="day-cell"
                     :class="{ clickable: d.v !== 0 }"
                     :style="{ left: d.col * (CELL + GAP) + 'px', top: d.row * (CELL + GAP) + 'px', backgroundColor: dayColor(d) }"
                     @click="d.v !== 0 && emit('cell-click', d.date)">
                  <el-tooltip v-if="d.v !== 0" :content="d.tip" placement="top" :show-after="150">
                    <div class="cell-inner"></div>
                  </el-tooltip>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="contrib-legend">
      <!-- 归因模式：颜色 = 当天主导归因（固定语义色，不做深浅） -->
      <template v-if="isAttrMode">
        <span v-for="name in legendKeys" :key="name" class="legend-item">
          <span class="legend-cell" :style="{ backgroundColor: palette?.[name] }"></span>{{ name }}
        </span>
        <span v-if="unclassifiedDays > 0" class="legend-item">
          <span class="legend-cell legend-cell--unclassified"></span>未归类
        </span>
      </template>
      <template v-else>
        <span class="legend-label">少</span>
        <span class="legend-cell" :style="{ backgroundColor: legendColor(0.1) }"></span>
        <span class="legend-cell" :style="{ backgroundColor: legendColor(0.35) }"></span>
        <span class="legend-cell" :style="{ backgroundColor: legendColor(0.6) }"></span>
        <span class="legend-cell" :style="{ backgroundColor: legendColor(0.85) }"></span>
        <span class="legend-label">多</span>
        <span v-if="positiveNegative" class="legend-hint">
          <span class="legend-chip" style="background:#40C463"></span> 收入 &nbsp;
          <span class="legend-chip" style="background:#F87171"></span> 支出
        </span>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

const emit = defineEmits<{ 'cell-click': [date: string] }>()

/** 同页只挂一份图，锚点查询限定在根节点内 */
const rootEl = ref<HTMLElement | null>(null)
/** 年份区的滚动盒：展开后在此内部滚动，页头统计与工具条始终可见 */
const scrollBox = ref<HTMLElement | null>(null)

const props = defineProps<{
  data: Array<{ date: string; value: number; attr?: string | null; breakdown?: Record<string, number> }>
  minYear: number
  maxYear: number
  title?: string
  unitLabel?: string
  positiveNegative?: boolean
  /** 'value'（默认）= 量值热度着色；'attribution' = 每天取主导归因，按 palette 固定语义色着色 */
  mode?: 'value' | 'attribution'
  /** 归因模式下的「归因名 → 颜色」映射，同时也决定图例顺序 */
  palette?: Record<string, string>
  /**
   * 默认显示的年份数；不传或 0 = 全部年份平铺。
   * 多年图（时间/日记/健康/财富贡献图）传 3：一屏放得下，早期记录折起来按需展开。
   * 单年图（如某一年的日记热力图）不需要传，年份不足 N 时也不显示折叠按钮。
   */
  defaultYears?: number
}>()

const isAttrMode = computed(() => props.mode === 'attribution')
const legendKeys = computed(() => Object.keys(props.palette ?? {}))

const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const CELL = 13
const GAP = 3
const COLS = 53  // 一年最多 53 周
const gridWidth = COLS * (CELL + GAP)  // 53*16 = 848px

// 空格 / 未归类（有记录但无归因）/ 归因名不在 palette 中的兜底
const EMPTY_CELL = '#ebedf0'
const UNCLASSIFIED_CELL = '#CBD5E1'
const UNKNOWN_CELL = '#94A3B8'

function positionOf(year: number, month: number, day: number) {
  const date = new Date(year, month - 1, day)
  const jan1 = new Date(year, 0, 1)
  const offset = (jan1.getDay() + 6) % 7
  const diff = Math.floor((date.getTime() - jan1.getTime()) / 86400000)
  const idx = diff + offset
  return { col: Math.floor(idx / 7), row: idx % 7 }
}

function yearDays(year: number) {
  const days: Array<{ date: string; col: number; row: number; v: number; attr: string | null; tip: string }> = []
  const start = new Date(year, 0, 1)
  const end = new Date(year, 11, 31)
  for (let t = start.getTime(); t <= end.getTime(); t += 86400000) {
    const d = new Date(t)
    if (d.getFullYear() !== year) continue
    const pos = positionOf(year, d.getMonth() + 1, d.getDate())
    const iso = `${year}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    const v = (dateMap.value.get(iso) || 0)
    const info = isAttrMode.value ? attrMap.value.get(iso) : undefined
    const attr = info?.attr ?? null
    const tip = isAttrMode.value
      ? attrTip(iso, v, attr, info?.breakdown)
      : `${iso} · ${v.toLocaleString()} ${props.unitLabel ?? ''}`
    days.push({ date: iso, col: pos.col, row: pos.row, v, attr, tip })
  }
  return days
}

/** 归因模式的悬浮提示：主导归因 + 当天各归因时长（只列非零） */
function attrTip(iso: string, v: number, attr: string | null, breakdown?: Record<string, number>) {
  const head = attr ? `主导 ${attr}` : '无已归因时长'
  const parts = Object.entries(breakdown ?? {})
    .filter(([, hv]) => hv > 0)
    .map(([k, hv]) => `${k} ${hv}h`)
  const tail = `全天 ${v.toLocaleString()} ${props.unitLabel ?? ''}`
  return parts.length ? `${iso} · ${head} · ${parts.join(' · ')} · ${tail}` : `${iso} · ${head} · ${tail}`
}

const dateMap = computed(() => {
  const m = new Map<string, number>()
  for (const item of props.data) m.set(item.date, item.value)
  return m
})

/** 归因模式：日期 → 主导归因与当天归因时长明细 */
const attrMap = computed(() => {
  const m = new Map<string, { attr: string | null; breakdown?: Record<string, number> }>()
  for (const item of props.data) m.set(item.date, { attr: item.attr ?? null, breakdown: item.breakdown })
  return m
})

/** 各归因作为「当天主导」的天数统计（用于页头文案与图例），只算可见年份 */
const attrDayCount = computed(() => {
  const c: Record<string, number> = {}
  for (const item of visibleData.value) if (item.attr) c[item.attr] = (c[item.attr] || 0) + 1
  return c
})

const unclassifiedDays = computed(() => visibleData.value.filter(d => !d.attr).length)

const attrSummaryText = computed(() =>
  legendKeys.value.map(k => `${k} ${attrDayCount.value[k] || 0}`).join(' · ')
)

/** 全部年份（接口给的 min_year ~ max_year），折叠与展开都从这里切窗口 */
const allYears = computed(() => {
  const list: number[] = []
  for (let y = props.minYear; y <= props.maxYear; y++) list.push(y)
  return list
})

/** 默认窗口的年份数：数据不足 N 年时退化为全部，不出现折叠按钮 */
const windowSize = computed(() => {
  const n = props.defaultYears ?? 0
  const total = allYears.value.length
  return !n || n >= total ? total : n
})

const collapsible = computed(() => windowSize.value < allYears.value.length)
const expanded = ref(false)

const years = computed(() => {
  const list = allYears.value
  return collapsible.value && !expanded.value ? list.slice(-windowSize.value) : list
})

/**
 * 统计口径跟随可见范围：折叠时只算近 N 年，否则页头「活跃 xxx 天」是全年数字、
 * 图里只有三年，同一屏两个口径。
 * 注意颜色尺度（maxAbs）故意仍用全量 —— 同一格子的深浅在任何视图下都代表同一个量。
 */
const visibleData = computed(() => {
  if (!collapsible.value || expanded.value) return props.data
  const fromYear = years.value[0]
  return props.data.filter((d) => Number(d.date.slice(0, 4)) >= fromYear)
})

const maxAbs = computed(() => {
  let mx = 0
  for (const v of props.data) mx = Math.max(mx, Math.abs(v.value))
  return mx || 1
})

const summary = computed(() => {
  const days = visibleData.value.filter(d => d.value !== 0).length
  let maxDate = ''
  let maxValue = 0
  for (const d of visibleData.value) {
    if (Math.abs(d.value) > Math.abs(maxValue)) {
      maxValue = d.value
      maxDate = d.date
    }
  }
  return { total_days: days, max_date: maxDate, max_value: maxValue }
})

function monthLabels(year: number) {
  const labels: Array<{ col: number; name: string }> = []
  for (let m = 1; m <= 12; m++) {
    const pos = positionOf(year, m, 1)
    labels.push({ col: pos.col, name: MONTH_NAMES[m - 1] })
  }
  return labels
}

/**
 * 展开 / 收起早期年份。
 *
 * 年份块插在**上方**，滚动位置不会自动跟着走；直接把年份区滚回顶端 ——
 * 展开就是从最早的年份往下读（像翻开旧记录），收起就是回到当前那几年。
 * 滚动发生在卡片内的年份区，不动整页，所以统计与工具条始终可见。
 */
async function toggleExpand() {
  expanded.value = !expanded.value
  await nextTick()
  if (scrollBox.value) scrollBox.value.scrollTop = 0
}

/** 年份锚点跳转（只在展开后出现）。落在容器顶部，留 8px 呼吸位。 */
function scrollToYear(year: number) {
  const el = rootEl.value?.querySelector(`.contrib-year[data-year="${year}"]`)
  if (el instanceof HTMLElement) scrollToEl(el)
}

/**
 * 把元素滚到其滚动容器顶部。
 *
 * 不用 scrollIntoView：页面真正的滚动容器是 main.layout-main，而 el-card__body
 * 自己带 overflow:auto（滚不动但会被当成滚动祖先），scrollIntoView 在里面定位会偏。
 * 这里显式挑「真能滚」的祖先，自己算位移。
 */
function scrollToEl(el: HTMLElement | null) {
  if (!el) return
  let box = el.parentElement
  let scroller: HTMLElement | null = null
  while (box) {
    const oy = getComputedStyle(box).overflowY
    if (/(auto|scroll)/.test(oy) && box.scrollHeight > box.clientHeight + 1) { scroller = box; break }
    box = box.parentElement
  }
  if (!scroller) return
  const delta = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top - 8
  scroller.scrollTo({ top: scroller.scrollTop + delta, behavior: 'smooth' })
}

function formatValue(v: number) {
  return v.toLocaleString() + (props.unitLabel ? ` ${props.unitLabel}` : '')
}

function legendColor(ratio: number) { return colorFor(ratio, 1) }

function colorFor(ratio: number, sign: 1 | -1): string {
  if (props.positiveNegative) {
    // 正负模式（收支净值）：绿=收入多（正）、红=支出多（负）
    if (sign > 0) {
      return ratio > 0.75 ? '#216E39' : ratio > 0.5 ? '#30A14E' : ratio > 0.25 ? '#40C463' : '#9BE9A8'
    }
    return ratio > 0.75 ? '#B91C1C' : ratio > 0.5 ? '#DC2626' : ratio > 0.25 ? '#F87171' : '#FCA5A5'
  }
  return ratio > 0.75 ? '#216E39' : ratio > 0.5 ? '#30A14E' : ratio > 0.25 ? '#40C463' : '#9BE9A8'
}

function dayColor(d: { v: number; attr: string | null }): string {
  if (isAttrMode.value) {
    // 归因模式：单色平铺，颜色只表达「这天最主要是哪一类」
    if (d.v === 0) return EMPTY_CELL
    return d.attr ? (props.palette?.[d.attr] ?? UNKNOWN_CELL) : UNCLASSIFIED_CELL
  }
  if (d.v === 0) return EMPTY_CELL
  const ratio = Math.abs(d.v) / maxAbs.value
  const sign = d.v > 0 ? 1 : -1
  return colorFor(ratio, sign)
}
</script>

<style scoped>
/* 横向溢出与展开后的纵向滚动都收在这一层：页面不跟着滚，
   页头的统计与年份工具条就始终留在视野里。 */
.contrib-graph { font-family: inherit; user-select: none; }
/* 留出卡片上方页头、工具条、图例和底部固定状态栏的高度，否则图例会压到状态栏下面 */
.contrib-scroll { overflow: auto; max-height: max(410px, calc(100vh - 330px)); }
.contrib-header {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 12px; flex-wrap: wrap; gap: 6px;
}
.contrib-title { font-size: 16px; font-weight: 600; }
.contrib-stats { font-size: 12px; color: #909399; }
.contrib-body { display: flex; flex-direction: column; gap: 16px; }

/* 年份窗口工具条：折叠时只有一行淡化的「展开更早记录」；展开后左侧补出年份锚点。
   注意别加 position:sticky —— el-card__body 自带 overflow:auto，会把 sticky 困在里面而不生效。 */
.contrib-toolbar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-bottom: 8px;
}
.anchor-list { display: flex; gap: 6px; flex-wrap: wrap; }
.anchor-chip {
  font-size: 11px; line-height: 16px; color: #606266; padding: 1px 8px;
  border: 1px solid #dcdfe6; border-radius: 10px; cursor: pointer;
}
.anchor-chip:hover { color: #2563eb; border-color: #2563eb; background: #eff6ff; }
.anchor-toggle {
  font-size: 11px; line-height: 16px; color: #606266; cursor: pointer;
  padding: 2px 10px; border: 1px solid #dcdfe6; border-radius: 10px; background: #fafafa;
}
.anchor-toggle:hover { color: #2563eb; border-color: #2563eb; background: #eff6ff; }

.contrib-year { display: flex; gap: 8px; align-items: flex-start; }
.year-cell {
  width: 40px; font-size: 11px; font-weight: 600; color: #606266;
  padding-top: 16px; flex-shrink: 0; text-align: right; line-height: 1.2;
}
.year-content { flex: 0 0 auto; margin: 0 auto; }

/* 月份标签：绝对定位，每月 1 号列精准对齐 */
.month-labels {
  position: relative;
  height: 14px;
  font-size: 9px;
  color: #909399;
  margin-left: 34px;  /* = weekday-labels 宽(28) + gap(6) */
}
.month-label {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  line-height: 14px;
  white-space: nowrap;
  display: inline-block;
}

/* 周行：weekday 标签与 cells 水平并排，7 行高度对齐 */
.week-row { display: flex; gap: 6px; align-items: flex-start; }

.weekday-labels {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex-shrink: 0;
  width: 28px;
}
.wd-label {
  font-size: 9px; color: #c0c4cc;
  text-align: right; padding-right: 4px;
}

/* 单元格：绝对定位，col/row 精准 */
.cells-grid {
  position: relative;
  width: 848px;  /* 53 * (13+3) */
  height: 109px; /* 7 * (13+3) */
}
.day-cell {
  position: absolute;
  width: 13px; height: 13px;
  border-radius: 2px;
  background-color: #ebedf0;
}
.day-cell.clickable {
  cursor: pointer;
}
.day-cell.clickable:hover {
  outline: 2px solid #2563EB;
  outline-offset: -1px;
  z-index: 2;
}
.cell-inner { width: 100%; height: 100%; }

.contrib-legend { display: flex; align-items: center; gap: 4px; margin-top: 14px; justify-content: flex-end; flex-wrap: wrap; }
.legend-label { font-size: 11px; color: #909399; }
.legend-cell { width: 12px; height: 12px; border-radius: 2px; }
.legend-cell--unclassified { background-color: #CBD5E1; }
.legend-item { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #606266; margin-left: 12px; }
.legend-hint { margin-left: 14px; font-size: 11px; color: #909399; display: inline-flex; align-items: center; gap: 4px; }
.legend-chip { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
</style>
