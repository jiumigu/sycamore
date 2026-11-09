<template>
  <div class="wht">
    <div v-if="!span" class="wht-empty">
      这一期没有任何时间记录 —— 不是「什么都没做」，是没记。
    </div>

    <template v-else>
      <div class="wht-scroll">
        <div class="wht-grid" :style="gridStyle">
          <!-- 列头：空白角 + 每一天 -->
          <div class="wht-corner" />
          <div v-for="c in columns" :key="c.date" class="wht-col-head" :class="{ today: c.date === todayIso }">
            <span class="wht-col-weekday">{{ c.weekday }}</span>
            <span class="wht-col-md">{{ c.md }}</span>
          </div>

          <!-- 时刻刻度 -->
          <div class="wht-axis" :style="{ height: bodyHeight + 'px' }">
            <div
              v-for="h in hourTicks" :key="h"
              class="wht-axis-label"
              :style="{ top: (h - range!.fromH) * HOUR_H + 'px' }"
            >{{ pad2(h) }}:00</div>
          </div>

          <!-- 每天一列 -->
          <div
            v-for="c in columns" :key="'col-' + c.date"
            class="wht-col" :style="{ height: bodyHeight + 'px' }"
          >
            <div
              v-for="t in hourTicks" :key="'line-' + t"
              class="wht-gridline" :style="{ top: (t - range!.fromH) * HOUR_H + 'px' }"
            />
            <!-- 范围外的跨午夜残片：不按位置画（画在边线上等于撒谎），只报数 -->
            <span
              v-if="offMarks.get(c.date)"
              class="wht-off" :title="offTitle(c.date)"
            >＋{{ offText(c.date) }}</span>
            <div
              v-for="(b, i) in layout(c.date)" :key="c.date + '-' + i"
              class="wht-block"
              :class="[b.splitTail ? 'is-tail' : '', b.splitHead ? 'is-head' : '']"
              :style="b.style"
              :title="b.title"
            >
              <span v-if="b.showName" class="wht-name">{{ b.task_name }}</span>
              <span v-if="b.showHours" class="wht-hours">{{ b.hoursText }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="wht-legend">
        <span v-for="a in legend" :key="a.label" class="wht-legend-item">
          <i :style="{ background: a.color }" />{{ a.label }}
        </span>
        <span v-if="truncated" class="wht-trunc">
          记录太多，图上只画了最长的 {{ blocks.length }} 块，另有 {{ truncated }} 条未画出
        </span>
        <!-- 有范围外的块就必须解释一次：不说，那一列看起来就是「从 07:41 才开始」 -->
        <span v-if="offMarks.size" class="wht-offnote">
          列顶「＋37m」= 跨午夜延续到这一天的残片，落在纵轴范围外，图上没画（悬停看是哪段）
        </span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * 一周时段轴：横轴 7 天、纵轴时刻，块的位置 = 几点开始、高度 = 多久。
 *
 * 🔴 三条口径都来自后端，组件一个都不自己算：
 *    · `columns` = 哪几天（连没记录的天也在，否则「周三空着」看不出来）
 *    · `blocks`  = 每条记录的「当天第几分钟」区间（**不是时间串**，不解析、不碰时区）
 *    · `span`    = 纵轴范围。**不固定 0–24** —— 记录多半从 7 点开始，
 *                  画满 24 小时会在上方留一大片空白、把白天的块压成一条缝。
 *
 * ⚠️ 但「不固定」不等于「范围外的块就画在边上」：后端把跨午夜的零碎残片
 *    （< 1 小时）排除在 `span` 之外，这些块**落到范围外**。画在边线上会让
 *    00:37 的残片看起来像 06:55 开始的 —— 那是撒谎。本组件的处理是
 *    **不按位置画，在列顶标「＋37m」**，悬停给完整时段。
 *
 * ⚠️ 这里唯一自己决定的是**渲染**：像素、分栏、最小块高。
 *    这些不改任何数，改错了最多难看；一旦在这里算时长或判断「哪些算重叠」，
 *    图和列表就会给出两个答案。
 */
import { computed } from 'vue'
import { ATTRIBUTION_COLOR_MAP } from '@/modules/temporal/types/temporalTypes'
import type { WhatHappenedBlock, WhatHappenedColumn } from '../types/selfrunTypes'

const props = defineProps<{
  columns: WhatHappenedColumn[]
  blocks: WhatHappenedBlock[]
  span: { from: number; to: number } | null
  truncated: number
  /** 各归因小时合计 —— 图例顺序与色块来源同一份 */
  attrTotals: { label: string; hours: number }[]
}>()

/** 每小时多少像素。固定值，不随数据变 —— 否则两周的图不能横着比 */
const HOUR_H = 34

/** 块最小高度：一小时里记了 5 分钟也得看得见、点得到 */
const MIN_BLOCK_H = 12
/** 每列最小宽度：窄于此任务名就被截成一个字，图失去意义 */
const MIN_COL_W = 76
const AXIS_W = 44

const todayIso = computed(() => {
  // `toISOString()` 是 UTC —— 北京时间 07:00 前会得到昨天的日期。
  // 这里用本地字段手工拼，只为一个用途（高亮「今天」那一列）。
  const d = new Date()
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
})

const range = computed(() => {
  const s = props.span
  if (!s) return null
  let fromH = Math.floor(s.from / 60)
  let toH = Math.ceil(s.to / 60)
  if (toH <= fromH) toH = fromH + 1
  // 至少 4 小时：只有 20 分钟记录的那一周，块会被放大到占满一屏，看着像干了 4 小时
  const MIN_SPAN_H = 4
  if (toH - fromH < MIN_SPAN_H) {
    const pad = Math.ceil((MIN_SPAN_H - (toH - fromH)) / 2)
    fromH = Math.max(0, fromH - pad)
    toH = Math.min(24, toH + pad)
    if (toH - fromH < MIN_SPAN_H) fromH = Math.max(0, toH - MIN_SPAN_H)
  }
  return { fromH, toH }
})

const bodyHeight = computed(() => (range.value ? (range.value.toH - range.value.fromH) * HOUR_H : 0))

/**
 * 落在纵轴范围外的块，按日期归并 —— 只可能是跨午夜被切成残片的那几段
 * （后端算 `span` 时把它们排除了，缘由见 `_span_of`）。
 * 🔴 它们**不按位置画**：37 分钟的尾巴画在 06:55 那条线上，看着就是
 *    「06:55 开始干了 37 分钟」。改成列顶报数，至少不会读错位置。
 */
const offMarks = computed(() => {
  const out = new Map<string, { minutes: number; items: WhatHappenedBlock[] }>()
  const r = range.value
  if (!r) return out
  const lo = r.fromH * 60
  const hi = r.toH * 60
  for (const b of props.blocks) {
    if (b.from >= lo && b.to <= hi) continue
    const cur = out.get(b.date) || { minutes: 0, items: [] }
    cur.minutes += b.minutes
    cur.items.push(b)
    out.set(b.date, cur)
  }
  return out
})

function offText(date: string) {
  const m = offMarks.value.get(date)
  return m ? `${Math.round(m.minutes)}m` : ''
}

function offTitle(date: string) {
  const m = offMarks.value.get(date)
  const r = range.value
  if (!m || !r) return ''
  const lines = m.items.map(b =>
    `${minutesToClock(b.from)}–${minutesToClock(b.to)} ${b.task_name}（${hoursText(b.minutes)}）`)
  return `纵轴从 ${pad2(r.fromH)}:00 画到 ${pad2(r.toH)}:00，`
    + `这些时段在范围外，图上没有画：\n${lines.join('\n')}`
}

/** 刻度：>10 小时就每 2 小时标一次，否则字会叠在一起 */
const hourTicks = computed(() => {
  const r = range.value
  if (!r) return []
  const step = r.toH - r.fromH > 10 ? 2 : 1
  const out: number[] = []
  for (let h = r.fromH; h <= r.toH; h += step) out.push(h)
  return out
})

const gridStyle = computed(() => ({
  gridTemplateColumns: `${AXIS_W}px repeat(${props.columns.length}, minmax(${MIN_COL_W}px, 1fr))`,
  minWidth: `${AXIS_W + props.columns.length * MIN_COL_W}px`,
}))

const legend = computed(() =>
  props.attrTotals.length
    ? props.attrTotals.map(a => ({ label: a.label, color: ATTRIBUTION_COLOR_MAP[a.label] || '#94A3B8' }))
    : [],
)

function pad2(n: number) {
  return n < 10 ? `0${n}` : String(n)
}

function hoursText(minutes: number) {
  if (minutes < 60) return `${Math.round(minutes)}m`
  return `${(minutes / 60).toFixed(1)}h`
}

interface Placed {
  task_name: string
  hoursText: string
  showName: boolean
  showHours: boolean
  splitHead: boolean
  splitTail: boolean
  title: string
  style: Record<string, string>
}

/**
 * 一天的块 → 具体像素位置。含**重叠分栏**。
 *
 * 🔴 分栏只在块真的会互相遮住时才发生：`2px` 以内的重叠直接叠着画。
 *    实测库里存在 18 秒级别的重叠（一条记录比上一条早结束了 18 秒），
 *    按像素级判重叠会让一整天每一块都被劈成两半 —— 那是把数据问题画成版面问题。
 *    （真正要处理的时段重叠在 `temporal` 的导入预演里，有单独一份口径。）
 */
function layout(date: string): Placed[] {
  const r = range.value
  if (!r) return []

  const lo = r.fromH * 60
  const hi = r.toH * 60
  const dayBlocks = props.blocks
    // 范围外的块不在这里画（`offMarks` 负责报数）—— 夹到边线会读成另一个时刻
    .filter(b => b.date === date && b.from >= lo && b.to <= hi)
    .sort((a, b) => a.from - b.from || b.minutes - a.minutes)
  if (!dayBlocks.length) return []

  // 贪心分栏：每栏记最后一个块的结束分钟
  const laneEnds: number[] = []
  const laneOf: number[] = []
  const EPS_MIN = (2 / HOUR_H) * 60      // 2px 对应的分钟数
  for (const b of dayBlocks) {
    let lane = laneEnds.findIndex(end => b.from >= end - EPS_MIN)
    if (lane === -1) {
      lane = laneEnds.length
      laneEnds.push(b.to)
    } else {
      laneEnds[lane] = Math.max(laneEnds[lane], b.to)
    }
    laneOf.push(lane)
  }
  const laneCount = laneEnds.length

  return dayBlocks.map((b, i) => {
    const top = (b.from / 60 - r.fromH) * HOUR_H
    const rawH = (b.minutes / 60) * HOUR_H
    const height = Math.max(rawH, MIN_BLOCK_H)
    const lane = laneOf[i]
    const widthPct = 100 / laneCount
    const hoursT = hoursText(b.minutes)

    return {
      task_name: b.task_name,
      hoursText: hoursT,
      // 块高够才放字：14px 塞一行小字已经极限，再小就是满屏噪点
      showName: height >= 15,
      showHours: height >= 30,
      splitHead: b.split === 'head',
      splitTail: b.split === 'tail',
      title: `${b.task_name} · ${minutesToClock(b.from)}–${minutesToClock(b.to)}（${hoursT}）`
        + (b.attribution ? ` · ${b.attribution}` : '')
        + (b.split === 'tail' ? ' · 接前一天' : '')
        + (b.split === 'head' ? ' · 延续到次日' : ''),
      style: {
        top: `${top}px`,
        height: `${height}px`,
        left: `calc(${lane * widthPct}% + 1px)`,
        width: `calc(${widthPct}% - 2px)`,
        background: ATTRIBUTION_COLOR_MAP[b.attribution] || '#94A3B8',
      },
    }
  })
}

/** 分钟 → `09:05`。1440 显示成 `24:00`（块的终点本来就可以是当天结束） */
function minutesToClock(m: number) {
  const v = Math.round(m)
  const h = Math.floor(v / 60)
  const mm = v % 60
  return `${pad2(h)}:${pad2(mm)}`
}
</script>

<style scoped lang="scss">
.wht { margin-top: 4px; }

.wht-empty {
  padding: 18px 0;
  text-align: center;
  font-size: 13px;
  color: #9CA3AF;
}

/* 窄屏横向滚动：宁可让人滑一下，也不把 7 天压成 7 条缝 */
/* 底部留 10px：最后一条刻度（24:00）压在底边上，`translateY(-50%)` 有一半在框外，
   `overflow-y: hidden` 会把它裁掉半个字 */
.wht-scroll { overflow-x: auto; overflow-y: hidden; padding-bottom: 10px; }

.wht-grid {
  display: grid;
  align-items: start;
}

.wht-corner { height: 30px; }

.wht-col-head {
  height: 30px;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
  font-size: 12px;
  color: #64748B;
  border-bottom: 1px solid #E5E7EB;

  &.today { color: #1F2937; font-weight: 600; }
}
.wht-col-weekday { font-weight: 600; }
.wht-col-md { font-size: 11px; color: #94A3B8; }

.wht-axis { position: relative; }
.wht-axis-label {
  position: absolute;
  right: 6px;
  transform: translateY(-50%);
  font-size: 10px;
  line-height: 1;
  color: #9CA3AF;
  font-variant-numeric: tabular-nums;
}

.wht-col {
  position: relative;
  border-left: 1px solid #F1F5F9;

  &:last-child { border-right: 1px solid #F1F5F9; }
}

/* 横线画在列里而不是绝对定位层：列高由 JS 给，线跟着走不会错位 */
.wht-gridline {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: #F1F5F9;
  pointer-events: none;
}

/* 范围外的残片：只报数，不占位置。虚线边框表示「这不是一格里的一段」 */
.wht-off {
  position: absolute;
  top: 1px;
  right: 2px;
  z-index: 1;
  padding: 0 3px;
  border: 1px dashed #CBD5E1;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.92);
  font-size: 10px;
  line-height: 14px;
  color: #94A3B8;
  font-variant-numeric: tabular-nums;
  cursor: help;
}

.wht-block {
  position: absolute;
  box-sizing: border-box;
  padding: 2px 4px;
  border-radius: 3px;
  overflow: hidden;
  color: #fff;
  font-size: 11px;
  line-height: 1.25;
  cursor: default;
  /* 白边让相邻块分得开 —— 两块紧挨着时否则像一整块 */
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.55);

  &.is-head { border-bottom: 2px dashed rgba(255, 255, 255, 0.85); }
  &.is-tail { border-top: 2px dashed rgba(255, 255, 255, 0.85); }
}

.wht-name {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.wht-hours {
  display: block;
  font-size: 10px;
  opacity: 0.92;
  font-variant-numeric: tabular-nums;
}

.wht-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: #64748B;
}
.wht-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;

  i {
    width: 9px;
    height: 9px;
    border-radius: 2px;
    display: inline-block;
  }
}
.wht-trunc { color: #B45309; }
/* 独占一行：它是「图怎么读」的说明，不该挤在色块图例里 */
.wht-offnote { flex-basis: 100%; color: #94A3B8; font-size: 11px; }
</style>
