<template>
  <div ref="chartRef" class="sunburst-chart" :style="{ height: height + 'px' }"></div>
</template>

<script setup lang="ts">
/**
 * 时间结构图：三层同心环 + 圆外引线标注
 * - 内环 L1 归因 → 中环 L2 类型 → 外环 L3 任务名
 * - L1 / L2 标签**恒在环内**，且**不做「放不下就隐藏」的判定**：
 *   文字沿弧长方向做松弛避让，中心点仍锚在各自扇区中点；极窄扇区（≈1%）
 *   的文字允许溢出到自己扇区之外、落在相邻扇区的空白处，不引线、不出圆
 * - L3 任务名**恒在圆外**：引线 + 左右分侧 + 垂直避让，避免文字互相堆叠
 */
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { SunburstData } from '../types/temporalTypes'
import { ACTIVITY_TYPE_COLOR_MAP, ATTRIBUTION_COLOR_MAP } from '../types/temporalTypes'

const props = withDefaults(defineProps<{
  data: SunburstData | null
  height?: number
}>(), { height: 400 })

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const FONT = '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif'
const FALLBACK_COLOR = '#94A3B8'

type Level = 'l1' | 'l2' | 'l3'

interface RingNode {
  name: string
  value: number
  color: string
  kind: Level
  ang: number      // 扇区角度（度）
  mid: number      // 扇区中点角度（度，自 12 点顺时针）；会被松弛避让微调
}

interface OutLabel {
  name: string
  color: string
  kind: Level
  dx: number
  dy: number
  sx: number
  sy: number
  y: number
}

/** 在扇区色基础上加深，浅色系（灰/浅蓝）作为文字色也能读清 */
function darken(hex: string, k: number): string {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(String(hex || ''))
  if (!m) return hex
  const n = parseInt(m[1], 16)
  const rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(v * k))))
  return '#' + rgb.map((v) => v.toString(16).padStart(2, '0')).join('')
}

/** 估算文本像素宽：中文按 1 字号，ASCII 按 0.58 字号 */
function measure(str: string, fs: number): number {
  let w = 0
  for (const ch of String(str || '')) w += /[\u0000-\u00ff]/.test(ch) ? fs * 0.58 : fs
  return w || fs
}

const TAU = Math.PI * 2
function cwDiff(a: number, b: number): number {
  let d = a - b
  while (d < 0) d += TAU
  while (d >= TAU) d -= TAU
  return d
}

/**
 * 同一环带内的标签沿弧长方向松弛避让。
 * 理想位置 = 扇区中点（保证「中心点仍在原扇区」）；当文字宽度超出扇区宽度时，
 * 不与邻居均摊位移，而是按「扇区宽裕度」分配让步量——大扇区多让、极窄扇区几乎不动，
 * 于是 1% 级扇区的文字就稳稳压在自家扇区上、只向两侧邻区空白处溢出，
 * 既不重叠、也不隐藏、也不需要引线。
 */
function relaxOnRing(nodes: RingNode[], rMid: number, fs: number, pad: number): void {
  const n = nodes.length
  if (n <= 1 || rMid <= 0) return
  const list = nodes.slice().sort((a, b) => a.mid - b.mid)
  const half = list.map((d) => (measure(d.name, fs) / 2 + pad / 2) / rMid)  // 弧度：标签半占位
  const slot = half.map((h) => h * 2 * rMid)                                // 像素：标签所需弧长
  // 让步权重 = 扇区弧长 / 标签所需弧长（越小说明扇区越窄、越要钉住不动）
  const give = list.map((d, i) => {
    const arc = ((d.ang * Math.PI) / 180) * rMid
    return Math.max(0.02, Math.min(1, arc / Math.max(slot[i], 0.001)))
  })
  const th = list.map((d) => (d.mid * Math.PI) / 180)
  for (let iter = 0; iter < 120; iter++) {
    let moved = false
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n
      const gap = cwDiff(th[j], th[i])
      const need = half[i] + half[j]
      if (gap < need - 1e-4) {
        const shift = need - gap
        const t = give[i] / (give[i] + give[j])   // i 承担的让步比例
        th[i] -= shift * t
        th[j] += shift * (1 - t)
        moved = true
      }
    }
    if (!moved) break
  }
  list.forEach((d, i) => { d.mid = (((th[i] * 180) / Math.PI) % 360 + 360) % 360 })
}

function buildOption(W: number, H: number): any {
  const groups = props.data?.groups || []
  const total = groups.reduce((s, g) => s + (Number(g.hours) || 0), 0) || 1

  // 圆外只有 L3 标签，预留横向空间可收窄，让圆更大、扇区弧更长
  const labelReserve = W < 520 ? 84 : 92
  const R3 = Math.max(56, Math.min(W / 2 - labelReserve, H / 2 - 14))
  const R0 = R3 * 0.32, R1 = R3 * 0.54, R2 = R3 * 0.82
  const cx = W / 2, cy = H / 2
  const L1_MID = (R0 + R1) / 2
  const L2_MID = (R1 + R2) / 2

  // ── 组装三层（顺序即角度顺序，三层同向对齐）──
  const l1: RingNode[] = [], l2: RingNode[] = [], l3: RingNode[] = []
  let acc = 0
  for (const g of groups) {
    const gColor = g.color || ATTRIBUTION_COLOR_MAP[g.name] || FALLBACK_COLOR
    const gAng = (Number(g.hours) || 0) / total * 360
    l1.push({ name: g.name, value: Number(g.hours) || 0, color: gColor, kind: 'l1', ang: gAng, mid: acc + gAng / 2 })
    for (const c of g.children || []) {
      const cColor = c.color || ACTIVITY_TYPE_COLOR_MAP[c.name] || gColor
      const cAng = (Number(c.hours) || 0) / total * 360
      l2.push({ name: c.name, value: Number(c.hours) || 0, color: cColor, kind: 'l2', ang: cAng, mid: acc + cAng / 2 })
      for (const t of c.children || []) {
        const tAng = (Number(t.hours) || 0) / total * 360
        l3.push({ name: t.name, value: Number(t.hours) || 0, color: cColor, kind: 'l3', ang: tAng, mid: acc + tAng / 2 })
        acc += tAng
      }
    }
  }

  // ── 环内标签避让（L1 / L2 全部标注，极窄扇区溢出到邻区空白，不隐藏）──
  const L1_FS = 12, L2_FS = 10
  relaxOnRing(l1, L1_MID, L1_FS, 8)
  relaxOnRing(l2, L2_MID, L2_FS, 6)

  const graphic: any[] = []

  /** 环内标题文字：水平排布在环带中线，锚点=避让后的角度位置 */
  function emitRingText(list: RingNode[], rMid: number, fs: number, weight: string, alpha: number) {
    list.forEach((n) => {
      const rad = (n.mid * Math.PI) / 180
      graphic.push({
        type: 'text', z: 12, silent: true,
        left: cx + Math.sin(rad) * rMid, top: cy - Math.cos(rad) * rMid,
        style: {
          text: n.name,
          fill: darken(n.color, alpha),
          font: `${weight} ${fs}px ` + FONT,
          textAlign: 'center', textVerticalAlign: 'middle',
          // 白色光晕：文字可能压在同色系或异色扇区上，光晕保证两种底色下都可读
          textShadowColor: 'rgba(255,255,255,0.92)', textShadowBlur: 3,
        },
      })
    })
  }
  emitRingText(l1, L1_MID, L1_FS, '600', 0.52)
  emitRingText(l2, L2_MID, L2_FS, '500', 0.5)

  // ── 圆外标签（仅 L3）：分侧 + 垂直避让 ──
  const labelGap = 24
  const items: OutLabel[] = l3.map((n) => {
    const rad = (n.mid * Math.PI) / 180
    const dx = Math.sin(rad), dy = -Math.cos(rad)
    return {
      name: n.name, color: n.color, kind: n.kind, dx, dy,
      sx: cx + dx * R3, sy: cy + dy * R3,
      y: cy + dy * (R3 + 14),
    }
  })

  const right = items.filter((p) => p.dx >= 0).sort((a, b) => a.y - b.y)
  const left = items.filter((p) => p.dx < 0).sort((a, b) => a.y - b.y)
  const minY = 13, maxY = H - 13

  function place(list: OutLabel[]) {
    const n = list.length
    if (!n) return
    const avail = maxY - minY
    const g = Math.min(20, avail / Math.max(n - 1, 1))
    for (let i = 0; i < n; i++) list[i].y = Math.max(list[i].y, i === 0 ? minY : list[i - 1].y + g)
    if (list[n - 1].y > maxY) {
      list[n - 1].y = maxY
      for (let i = n - 2; i >= 0; i--) list[i].y = Math.min(list[i].y, list[i + 1].y - g)
    }
    if (list[0].y < minY) {
      list[0].y = minY
      for (let i = 1; i < n; i++) list[i].y = Math.max(list[i].y, list[i - 1].y + g)
    }
    // 一侧标签偏少时均匀铺满，避免挤在一角
    if (n > 1) {
      const first = list[0].y
      const span = list[n - 1].y - first
      if (span > 0 && span < avail) {
        const k = avail / span
        for (let i = 0; i < n; i++) list[i].y = minY + (list[i].y - first) * k
      }
    }
  }
  place(right)
  place(left)

  function emit(list: OutLabel[], sign: 1 | -1) {
    list.forEach((p) => {
      const ax = cx + sign * (R3 + 5)
      const tx = cx + sign * (R3 + labelGap + 4)
      graphic.push({
        type: 'polyline', z: 10, silent: true,
        shape: { points: [[p.sx, p.sy], [ax, p.y], [tx - sign * 4, p.y]] },
        style: { stroke: darken(p.color, 0.85), lineWidth: 1, opacity: 0.7, fill: 'none' },
      })
      graphic.push({
        type: 'text', z: 11, silent: true, left: tx, top: p.y,
        style: {
          text: p.name,
          fill: darken(p.color, 0.72),
          font: '10.5px ' + FONT,
          textAlign: sign > 0 ? 'left' : 'right',
          textVerticalAlign: 'middle',
        },
      })
    })
  }
  emit(right, 1)
  emit(left, -1)

  // 圆心：总时长
  graphic.push({
    type: 'text', z: 9, silent: true, left: cx, top: cy - 8,
    style: { text: '总时长', fill: '#9CA3AF', font: '10.5px ' + FONT, textAlign: 'center', textVerticalAlign: 'middle' },
  })
  graphic.push({
    type: 'text', z: 9, silent: true, left: cx, top: cy + 7,
    style: { text: total.toFixed(1) + 'h', fill: '#111827', font: 'bold 13px ' + FONT, textAlign: 'center', textVerticalAlign: 'middle' },
  })

  const common = { center: [cx, cy], startAngle: 90, clockwise: true, sort: false, animation: false }
  const border = { borderWidth: 1, borderColor: '#fff' }
  const tip = (tag: string) => ({
    trigger: 'item',
    formatter: (p: any) => {
      const v = typeof p.value === 'number' ? p.value : 0
      return `${p.name}<br/>${tag}　${v.toFixed(2)} h　${((v / total) * 100).toFixed(1)}%`
    },
  })
  // 环内文字已由 graphic 自绘，series 标签全部关闭（tooltip 仍可查看数值）
  const ring = (nodes: RingNode[]) =>
    nodes.map((n) => ({ name: n.name, value: n.value, itemStyle: { color: n.color, ...border }, label: { show: false } }))

  return {
    graphic,
    tooltip: { confine: true },
    series: [
      {
        ...common, type: 'pie', name: 'L1 归因', radius: [R0, R1], tooltip: tip('L1 归因'),
        label: { show: false }, labelLine: { show: false },
        emphasis: { scale: false },
        data: ring(l1),
      },
      {
        ...common, type: 'pie', name: 'L2 类型', radius: [R1, R2], tooltip: tip('L2 类型'),
        label: { show: false }, labelLine: { show: false },
        emphasis: { scale: false },
        data: ring(l2),
      },
      {
        ...common, type: 'pie', name: 'L3 任务', radius: [R2, R3], tooltip: tip('L3 任务'),
        label: { show: false }, labelLine: { show: false },
        emphasis: { scale: false },
        data: ring(l3),
      },
    ],
  }
}

function render() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const W = chart.getWidth(), H = chart.getHeight()
  if (!W || !H) return
  chart.setOption(buildOption(W, H), true)
}

let rafId = 0
function handleResize() {
  if (!chart) return
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(() => {
    if (!chart) return
    chart.resize()
    render()
  })
}

watch(() => props.data, () => nextTick(render), { deep: true })

onMounted(() => {
  nextTick(render)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  cancelAnimationFrame(rafId)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.sunburst-chart { width: 100%; }
</style>
