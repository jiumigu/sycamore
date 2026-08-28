<template>
  <div class="contrib-graph">
    <div class="contrib-header">
      <span class="contrib-title">{{ title }}</span>
      <span class="contrib-stats">
        活跃 {{ summary.total_days }} 天 · 峰值 {{ summary.max_date ? summary.max_date + ' · ' + formatValue(summary.max_value) : '-' }}
        · {{ minYear }} ~ {{ maxYear }}
      </span>
    </div>

    <div class="contrib-body">
      <div class="contrib-year" v-for="year in years" :key="year">
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
                   :style="{ left: d.col * (CELL + GAP) + 'px', top: d.row * (CELL + GAP) + 'px', backgroundColor: dayColor(d.v) }">
                <el-tooltip v-if="d.v !== 0" :content="d.tip" placement="top" :show-after="150">
                  <div class="cell-inner"></div>
                </el-tooltip>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="contrib-legend">
      <span class="legend-label">少</span>
      <span class="legend-cell" :style="{ backgroundColor: legendColor(0.1) }"></span>
      <span class="legend-cell" :style="{ backgroundColor: legendColor(0.35) }"></span>
      <span class="legend-cell" :style="{ backgroundColor: legendColor(0.6) }"></span>
      <span class="legend-cell" :style="{ backgroundColor: legendColor(0.85) }"></span>
      <span class="legend-label">多</span>
      <span v-if="positiveNegative" class="legend-hint">
        <span class="legend-chip" style="background:#F87171"></span> 收入 &nbsp;
        <span class="legend-chip" style="background:#40C463"></span> 支出
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: Array<{ date: string; value: number }>
  minYear: number
  maxYear: number
  title?: string
  unitLabel?: string
  positiveNegative?: boolean
}>()

const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const CELL = 13
const GAP = 3
const COLS = 53  // 一年最多 53 周
const gridWidth = COLS * (CELL + GAP)  // 53*16 = 848px

function positionOf(year: number, month: number, day: number) {
  const date = new Date(year, month - 1, day)
  const jan1 = new Date(year, 0, 1)
  const offset = (jan1.getDay() + 6) % 7
  const diff = Math.floor((date.getTime() - jan1.getTime()) / 86400000)
  const idx = diff + offset
  return { col: Math.floor(idx / 7), row: idx % 7 }
}

function yearDays(year: number) {
  const days: Array<{ date: string; col: number; row: number; v: number; tip: string }> = []
  const start = new Date(year, 0, 1)
  const end = new Date(year, 11, 31)
  for (let t = start.getTime(); t <= end.getTime(); t += 86400000) {
    const d = new Date(t)
    if (d.getFullYear() !== year) continue
    const pos = positionOf(year, d.getMonth() + 1, d.getDate())
    const iso = `${year}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    const v = (dateMap.value.get(iso) || 0)
    const tip = `${iso} · ${v.toLocaleString()} ${props.unitLabel ?? ''}`
    days.push({ date: iso, col: pos.col, row: pos.row, v, tip })
  }
  return days
}

const dateMap = computed(() => {
  const m = new Map<string, number>()
  for (const item of props.data) m.set(item.date, item.value)
  return m
})

const years = computed(() => {
  const list: number[] = []
  for (let y = props.minYear; y <= props.maxYear; y++) list.push(y)
  return list
})

const maxAbs = computed(() => {
  let mx = 0
  for (const v of props.data) mx = Math.max(mx, Math.abs(v.value))
  return mx || 1
})

const summary = computed(() => {
  const days = props.data.filter(d => d.value !== 0).length
  let maxDate = ''
  let maxValue = 0
  for (const d of props.data) {
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

function formatValue(v: number) {
  return v.toLocaleString() + (props.unitLabel ? ` ${props.unitLabel}` : '')
}

function legendColor(ratio: number) { return colorFor(ratio, 1) }

function colorFor(ratio: number, sign: 1 | -1): string {
  if (props.positiveNegative) {
    if (sign > 0) {
      return ratio > 0.75 ? '#B91C1C' : ratio > 0.5 ? '#DC2626' : ratio > 0.25 ? '#F87171' : '#FCA5A5'
    }
    return ratio > 0.75 ? '#216E39' : ratio > 0.5 ? '#30A14E' : ratio > 0.25 ? '#40C463' : '#9BE9A8'
  }
  return ratio > 0.75 ? '#216E39' : ratio > 0.5 ? '#30A14E' : ratio > 0.25 ? '#40C463' : '#9BE9A8'
}

function dayColor(v: number): string {
  if (v === 0) return '#ebedf0'
  const ratio = Math.abs(v) / maxAbs.value
  const sign = v > 0 ? 1 : -1
  return colorFor(ratio, sign)
}
</script>

<style scoped>
.contrib-graph { font-family: inherit; user-select: none; overflow-x: auto; }
.contrib-header {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 12px; flex-wrap: wrap; gap: 6px;
}
.contrib-title { font-size: 16px; font-weight: 600; }
.contrib-stats { font-size: 12px; color: #909399; }
.contrib-body { display: flex; flex-direction: column; gap: 16px; }

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
.cell-inner { width: 100%; height: 100%; }

.contrib-legend { display: flex; align-items: center; gap: 4px; margin-top: 14px; justify-content: flex-end; }
.legend-label { font-size: 11px; color: #909399; }
.legend-cell { width: 12px; height: 12px; border-radius: 2px; }
.legend-hint { margin-left: 14px; font-size: 11px; color: #909399; display: inline-flex; align-items: center; gap: 4px; }
.legend-chip { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
</style>
