<template>
  <div class="ratio-trend">
    <div class="ratio-trend__head">
      <div>
        <span class="ratio-trend__title">比率趋势</span>
        <span class="ratio-trend__sub">
          值全部由后端算好 —— 前端不做除法，也不判档位
        </span>
      </div>
      <el-select
        :model-value="months"
        size="small"
        style="width: 110px"
        @update:model-value="(v: number) => emit('update:months', v)"
      >
        <el-option v-for="opt in MONTH_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
    </div>

    <div v-if="!trend || !sparks.length" class="ratio-trend__empty">暂无趋势数据</div>
    <div v-else class="ratio-trend__grid">
      <div
        v-for="(s, si) in sparks"
        :key="s.key"
        class="ratio-trend__item"
        :class="{ 'is-active': active?.s === si }"
      >
        <div class="ratio-trend__item-head">
          <span class="ratio-trend__item-label">{{ s.label }}</span>
          <span v-if="s.last" class="ratio-trend__item-value" :class="s.last.level ?? 'normal'">
            {{ s.last.available ? `${s.last.value}${s.unit}` : '—' }}
            <template v-if="s.last.level_label">· {{ s.last.level_label }}</template>
          </span>
        </div>

        <div class="ratio-trend__plot" @mouseleave="clearPoint">
          <svg class="ratio-trend__svg" viewBox="0 0 240 56" preserveAspectRatio="none">
            <!-- 零线：跨 0 的指标（净值增长 / 支出质量）才有意义 -->
            <line
              v-if="s.zeroY !== null"
              x1="0" :y1="s.zeroY" x2="240" :y2="s.zeroY"
              stroke="var(--el-border-color)" stroke-dasharray="3 3" stroke-width="1"
            />
            <!-- 光标竖线：说明「当前读的是哪一列」 -->
            <line
              v-if="active?.s === si && activeX !== null"
              :x1="activeX" y1="0" :x2="activeX" :y2="H"
              class="ratio-trend__cursor"
              vector-effect="non-scaling-stroke"
            />
            <!-- 断点即「这个月算不出来」—— 不许用 0 连成一条平线 -->
            <path
              v-for="(d, i) in s.paths"
              :key="i"
              :d="d"
              fill="none"
              stroke="var(--el-color-primary)"
              stroke-width="1.5"
              vector-effect="non-scaling-stroke"
            />
            <circle
              v-for="(dot, i) in s.dots"
              :key="'d' + i"
              :cx="dot.x" :cy="dot.y" r="2.5"
              :fill="dot.color"
            />
            <!--
              命中层：**整列一个透明矩形**，画在最上层（必须最后渲染，
              否则会被折线盖掉一截）。见 script 里第 ① 条注释。
            -->
            <rect
              v-for="(h, pi) in s.hits"
              :key="'h' + pi"
              :x="h.x" y="0" :width="h.w" :height="H"
              class="ratio-trend__hit"
              @mouseenter="showPoint(si, pi, $event)"
              @click="showPoint(si, pi, $event)"
            />
          </svg>

          <!-- 信息泡：HTML 浮层，不画进 SVG（会被 preserveAspectRatio 拉变形） -->
          <div
            v-if="active?.s === si && activePoint"
            class="ratio-trend__tip"
            :style="tipStyle"
          >
            <span class="ratio-trend__tip-ym">{{ activePoint.ym }}</span>
            <span class="ratio-trend__tip-sep">·</span>
            <span class="ratio-trend__tip-value" :class="tipValueClass">
              {{ activePoint.available && activePoint.value !== null
                ? `${activePoint.value}${activePoint.unit}`
                : '无数据' }}
            </span>
            <span v-if="activePoint.levelLabel" class="ratio-trend__tip-level">
              {{ activePoint.levelLabel }}
            </span>
          </div>
        </div>

        <div class="ratio-trend__axis">
          <span>{{ s.firstYm }}</span>
          <span>{{ s.lastYm }}</span>
        </div>
      </div>
    </div>

    <div v-if="trend && trend.excluded.length" class="ratio-trend__excluded">
      <el-icon><InfoFilled /></el-icon>
      <span>
        以下指标不进趋势：
        <template v-for="(ex, i) in trend.excluded" :key="ex.key">
          {{ ex.label }}（{{ ex.reason }}）<span v-if="i < trend.excluded.length - 1">；</span>
        </template>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, type CSSProperties } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { levelColor } from '../../utils/ratioLevel'
import type { RatioTrend, RatioTrendPoint } from '../../types/wealthTypes'

/**
 * 比率趋势 —— 每条线一个 sparkline。
 *
 * ⚠️ 三条口径，违反即回归：
 *   ① **缺月必须画成断点**。后端用 `available=false` 表达「这个月算不出来」，
 *      若前端把它当 0 补点，会画出一条「净资产这个月没变化」的平线 ——
 *      与「本月没盘点」是完全相反的两个结论。
 *   ② 比率是百分比/月数，**不是金额**，故不做金额掩码
 *      （与 `goals.progress_percentage` 同一条判据：百分比非隐私项）。
 *      掩了趋势线就失去全部意义。
 *   ③ 档位颜色只看 `point.level`；本组件没有任何阈值。
 *
 * ── 点交互（v3.60.21）────────────────────────────────────────────
 * 起因：卡片右上角只有「最后值」，折线上**其余 11 个月的值无处可查**。
 * 现在每列可点开信息泡：`2026-10 · 16.83月 · 充足`。
 *
 * 三个实现约束，别按常识改回去：
 *   ① **热区是整列透明 `<rect>`，不是 r=2.5 的圆**。
 *      2.5px 的点鼠标几乎点不中（实测要像素级对准）。整列之后，
 *      鼠标在图的任意横向位置都能读到**最近那一列**。
 *   ② **热区覆盖所有列，含断点列**。断点月此前在界面上只是「线断了」，
 *      既没有点也没有文案 —— 现在点它得到「2026-08 · 无数据」，
 *      至少能区分「缺」与「漏」。⚠️ 但 `RatioTrendPoint` **没有**
 *      `reason` 字段（后端只在点级给 available/vale/level），
 *      故这里**显示不了「为什么缺」**；要补那句得先扩后端契约。
 *   ③ **信息泡是 HTML 浮层，不画进 SVG**。`preserveAspectRatio="none"`
 *      会把 SVG 文本按 x/y 不同比例拉伸 ⇒ 字会变扁。代价是浮层坐标要
 *      按 viewBox 比例换算成像素，见 `tipStyle`。
 *      像素尺寸在**事件触发时**读 `getBoundingClientRect()`、**不缓存** ——
 *      这是「容器 resize 必须重算」那条判据的免维护写法：读的时候一定是最新的。
 *   ④ **仍然不上 ECharts**。加了交互会让人想「是不是该换图表库了」——
 *      但这里要的只是「读到最近一列」，自绘浮层比引一个库小得多，
 *      也继续躲开 `setOption` merge / resize 重算那两个坑（§14）。
 *      sparkline 的交互不该反噬成一次架构变更。
 */
const props = defineProps<{
  trend: RatioTrend | null
  months: number
  items: { key: string; label: string; unit: string }[]
}>()
const emit = defineEmits<{ 'update:months': [months: number] }>()

const MONTH_OPTIONS = [
  { value: 6, label: '近 6 个月' },
  { value: 12, label: '近 12 个月' },
  { value: 24, label: '近 24 个月' },
  { value: 36, label: '近 36 个月' },
]

const W = 240
const H = 56
const PAD = 6
/** 信息泡与点的间距（px，屏幕坐标） */
const TIP_GAP = 6
/** 信息泡宽度上限估算值，只用于左右防溢出（px） */
const TIP_MAX_W = 160
/** 点高于此像素值时，信息泡翻到点下方（否则会盖住卡片标题行） */
const TIP_FLIP_Y = 32

interface SparkDot { x: number; y: number; color: string }
interface SparkHit { x: number; w: number }
interface Spark {
  key: string
  label: string
  unit: string
  paths: string[]
  dots: SparkDot[]
  /** 每列一个命中区（**含断点列**），viewBox 坐标 */
  hits: SparkHit[]
  /** 原始点（含不可用），供信息泡取「年月 / 值 / 档位」 */
  points: RatioTrendPoint[]
  zeroY: number | null
  last: RatioTrendPoint | null
  firstYm: string
  lastYm: string
  /** 值 → viewBox y；全列无可用值时为 null */
  yOf: ((v: number) => number) | null
}

const sparks = computed<Spark[]>(() => {
  const trend = props.trend
  if (!trend) return []
  const series = trend.series ?? {}
  // 顺序以总览给的 items 为准（后端 RATIO_ORDER），再补上 items 里没有的键，
  // 避免「趋势区少了一条线而没人发现」。
  const ordered: { key: string; label: string; unit: string }[] = []
  const seen = new Set<string>()
  for (const it of props.items) {
    if (series[it.key]) { ordered.push(it); seen.add(it.key) }
  }
  for (const key of Object.keys(series)) {
    if (!seen.has(key)) ordered.push({ key, label: key, unit: '' })
  }

  return ordered.map((it) => {
    const points = series[it.key] ?? []
    const nums = points
      .filter((p) => p.available && p.value !== null)
      .map((p) => p.value as number)
    if (!nums.length) {
      return {
        ...it, paths: [], dots: [], hits: [], points, zeroY: null,
        last: null, firstYm: '', lastYm: '', yOf: null,
      }
    }
    let lo = Math.min(...nums)
    let hi = Math.max(...nums)
    if (hi - lo < 1e-9) { lo -= 1; hi += 1 }
    const span = hi - lo
    const yOf = (v: number) => PAD + (1 - (v - lo) / span) * (H - PAD * 2)
    const xOf = (i: number) => (points.length <= 1 ? W / 2 : (i / (points.length - 1)) * W)

    const paths: string[] = []
    const dots: SparkDot[] = []
    let segment: string[] = []
    points.forEach((p: RatioTrendPoint, i: number) => {
      const ok = p.available && p.value !== null
      if (!ok) {
        if (segment.length) { paths.push(segment.join(' ')); segment = [] }
        return
      }
      const x = xOf(i)
      const y = yOf(p.value as number)
      segment.push(`${segment.length ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`)
      dots.push({ x, y, color: levelColor(p.level) })
    })
    if (segment.length) paths.push(segment.join(' '))

    // 命中区：每列占「相邻间隔」那么宽，首尾夹在 [0, W] 内（超出 viewBox
    // 的部分在 `overflow: visible` 下能否收到事件因浏览器而异，夹住最稳）。
    const step = points.length > 1 ? W / (points.length - 1) : W
    const half = step / 2
    const hits: SparkHit[] = points.map((_, i) => {
      const x = xOf(i)
      const left = Math.max(0, x - half)
      const right = Math.min(W, x + half)
      return { x: left, w: Math.max(right - left, 0.5) }
    })

    const last = [...points].reverse().find((p) => p.available) ?? points[points.length - 1] ?? null
    return {
      ...it,
      paths,
      dots,
      hits,
      points,
      zeroY: lo <= 0 && hi >= 0 ? yOf(0) : null,
      last: last ?? null,
      firstYm: points[0]?.ym ?? '',
      lastYm: points[points.length - 1]?.ym ?? '',
      yOf,
    }
  })
})

/** 当前激活的列：`{ s: 第几条线, p: 第几个点 }` */
const active = ref<{ s: number; p: number } | null>(null)
/** svg 的**实际像素**尺寸，事件触发时读；不缓存 ⇒ 不需响应 resize */
const svgW = ref(0)
const svgH = ref(0)

function showPoint(si: number, pi: number, ev: MouseEvent) {
  const el = ev.currentTarget as SVGElement | null
  const svg = el?.ownerSVGElement
  if (svg) {
    const rect = svg.getBoundingClientRect()
    svgW.value = rect.width
    svgH.value = rect.height
  }
  active.value = { s: si, p: pi }
}

function clearPoint() {
  active.value = null
}

// 切月数 / 刷新后列数会变，旧的列索引可能已不存在 ⇒ 直接清掉，
// 避免「浮层显示上一个数据集的某个月」（看着像数据错了）。
watch(() => props.trend, () => { active.value = null })

const activePoint = computed(() => {
  const a = active.value
  if (!a) return null
  const s = sparks.value[a.s]
  const p = s?.points?.[a.p]
  if (!s || !p) return null
  return {
    ym: p.ym,
    value: p.value,
    level: p.level,
    levelLabel: p.level_label,
    available: p.available,
    unit: s.unit,
  }
})

const tipValueClass = computed(() => {
  const a = activePoint.value
  if (!a || !a.available || a.value === null) return 'none'
  return a.level ?? 'normal'
})

const activeX = computed(() => {
  const a = active.value
  if (!a) return null
  const h = sparks.value[a.s]?.hits?.[a.p]
  return h ? h.x + h.w / 2 : null
})

/**
 * 该列在 viewBox 里的 y。断点列没有自己的值 ⇒ 借**最近一个可用点**的高度，
 * 让浮层贴着折线，而不是飘在图正中（那会让人以为断点是个有效值）。
 */
function pointY(s: Spark, pi: number): number {
  const y = s.yOf
  if (!y) return H / 2
  const p = s.points[pi]
  if (p?.available && p.value !== null) return y(p.value)
  for (let d = 1; d < s.points.length; d++) {
    for (const j of [pi - d, pi + d]) {
      const q = s.points[j]
      if (q?.available && q.value !== null) return y(q.value)
    }
  }
  return H / 2
}

const tipStyle = computed<CSSProperties>(() => {
  const a = active.value
  if (!a) return {}
  const s = sparks.value[a.s]
  const h = s?.hits?.[a.p]
  if (!s || !h) return {}
  const pxW = svgW.value || W
  const pxH = svgH.value || H
  const xPx = ((h.x + h.w / 2) / W) * pxW
  const yPx = (pointY(s, a.p) / H) * pxH
  // 左右防溢：浮层中心不得让边缘越出卡片（`Math.max` 兜住 svg 过窄的情况）
  const half = TIP_MAX_W / 2
  const left = Math.min(Math.max(xPx, half), Math.max(pxW - half, half))
  const flip = yPx < TIP_FLIP_Y
  return {
    left: `${left.toFixed(1)}px`,
    top: `${yPx.toFixed(1)}px`,
    transform: flip
      ? `translate(-50%, ${TIP_GAP}px)`
      : `translate(-50%, calc(-100% - ${TIP_GAP}px))`,
  }
})
</script>

<style scoped>
.ratio-trend__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.ratio-trend__title { font-size: 15px; font-weight: 600; }
.ratio-trend__sub {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.ratio-trend__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}
.ratio-trend__item {
  position: relative;   /* 信息泡的定位基准 */
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 10px 12px;
}
/* 信息泡向上溢出时可能落到上一行卡片的地盘，抬一层保证它可见 */
.ratio-trend__item.is-active { z-index: 3; }
.ratio-trend__item-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
}
.ratio-trend__item-label { color: var(--el-text-color-regular); }
.ratio-trend__item-value { font-weight: 600; }
.ratio-trend__item-value.good { color: #52c41a; }
.ratio-trend__item-value.warn { color: #e6a23c; }
.ratio-trend__item-value.danger { color: #f5222d; }
.ratio-trend__item-value.normal { color: var(--el-text-color-primary); }
.ratio-trend__plot {
  position: relative;
  margin-top: 6px;
}
.ratio-trend__svg {
  display: block;
  width: 100%;
  height: 56px;
  overflow: visible;
}
/*
 * 命中层：`fill: transparent` + `pointer-events: all`。
 * ⚠️ 不能用 `fill: none` —— 默认 `pointer-events: visiblePainted` 下
 *    `none` 视为「没画」⇒ 收不到事件，点上去毫无反应且不报错。
 */
.ratio-trend__hit {
  fill: transparent;
  pointer-events: all;
  cursor: crosshair;
}
.ratio-trend__cursor {
  stroke: var(--el-text-color-placeholder);
  stroke-width: 1;
  stroke-dasharray: 2 2;
  pointer-events: none;
}
.ratio-trend__tip {
  position: absolute;
  z-index: 4;
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 4px 8px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  background: var(--el-bg-color-overlay, var(--el-bg-color));
  box-shadow: var(--el-box-shadow-light);
  font-size: 12px;
  line-height: 1.5;
  white-space: nowrap;
  pointer-events: none;   /* 别挡住自己脚下的热区 */
}
.ratio-trend__tip-ym { color: var(--el-text-color-secondary); }
.ratio-trend__tip-sep { color: var(--el-text-color-placeholder); }
.ratio-trend__tip-value { font-weight: 600; }
.ratio-trend__tip-value.good { color: #52c41a; }
.ratio-trend__tip-value.warn { color: #e6a23c; }
.ratio-trend__tip-value.danger { color: #f5222d; }
.ratio-trend__tip-value.normal { color: var(--el-text-color-primary); }
.ratio-trend__tip-value.none {
  font-weight: 400;
  color: var(--el-text-color-placeholder);
}
.ratio-trend__tip-level { color: var(--el-text-color-secondary); }
.ratio-trend__axis {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.ratio-trend__empty {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}
.ratio-trend__excluded {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 14px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
