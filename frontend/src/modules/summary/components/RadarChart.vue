<template>
  <div class="radar-wrapper">
    <div
      ref="chartRef"
      class="radar-chart"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
    ></div>
    <div
      v-if="tip"
      class="radar-tip"
      :style="{ left: tip.x + 'px', top: tip.y + 'px' }"
    >
      <div class="radar-tip-title">{{ tip.name }}</div>
      <div class="radar-tip-line">{{ tip.headline }}</div>
      <div v-if="tip.sub" class="radar-tip-sub">{{ tip.sub }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useSummaryStore } from '../stores/summaryStore'
import { formatSignedAmount } from '@/shared/utils/format'
import type { RadarAxis, RadarBasis } from '../types/summaryTypes'

/**
 * 七维雷达
 *
 * 🔴 两种镜片，同一份数据：
 *   coverage    = 覆盖率（默认）—— 无量纲、不依赖任何封顶，"哪根轴塌了"最准
 *   achievement = 对目标达成率 —— 保留封顶配置的意义（否则那个配置就是死开关）
 *
 * 两种口径都按 **0–100%** 画，轴的 max 恒为 100：
 * 之前把「点数」直接当值、把封顶当 max，时间投入 98 点 > 封顶 80 ⇒
 * 顶点画到了圈外。现在只在展示层截到 100，真实值在 tooltip 里如实写。
 */
const props = withDefaults(defineProps<{ basis?: RadarBasis }>(), {
  basis: 'coverage',
})

interface TipInfo {
  x: number
  y: number
  name: string
  headline: string
  sub: string
}

const store = useSummaryStore()
const chartRef = ref<HTMLElement>()
const tip = ref<TipInfo | null>(null)
let chart: echarts.ECharts | null = null
let resizeTimer: number | undefined

function axisValue(a: RadarAxis): number {
  const v = props.basis === 'coverage' ? a.coverage : a.achievement
  return v === null ? 0 : Math.min(Math.max(v, 0), 100)
}

function render() {
  const el = chartRef.value
  if (!el || !store.radarData) return
  if (!el.isConnected) return

  try {
    if (!chart || echarts.getInstanceByDom(el) !== chart) {
      try { chart?.dispose() } catch { /* noop */ }
      chart = echarts.init(el)
    }
    const axes = store.radarData.axes
    chart.setOption({
      tooltip: { show: false },
      radar: {
        indicator: axes.map(a => ({ name: a.name, max: 100 })),
        center: ['50%', '50%'],
        radius: '65%',
        shape: 'circle',
        name: { textStyle: { fontSize: 11, color: '#4B5563' } },
        splitArea: {
          areaStyle: {
            color: ['rgba(16,185,129,0.03)', 'rgba(16,185,129,0.06)'],
          },
        },
        axisLine: { lineStyle: { color: 'rgba(0,0,0,0.1)' } },
      },
      series: [{
        type: 'radar',
        data: [{
          value: axes.map(axisValue),
          name: `${store.radarData.year}年`,
          areaStyle: { color: 'rgba(16,185,129,0.15)' },
          lineStyle: { color: '#10B981', width: 2 },
          itemStyle: { color: '#10B981' },
        }],
      }],
    }, true)
    chart.resize()
  } catch (e) {
    console.warn('[RadarChart] render 失败，已重建实例:', e)
    try { chart?.dispose() } catch { /* noop */ }
    chart = null
  }
}

function money(value: number | null): string {
  return value === null ? '—' : formatSignedAmount(value, 2)
}

function tipFor(a: RadarAxis): { headline: string; sub: string } {
  if (props.basis === 'coverage') {
    const pct = a.coverage === null ? '—' : `${a.coverage}%`
    const intensity = a.intensity === null
      ? '—'
      : `${a.module === 'wealth' ? money(a.intensity) : a.intensity} ${a.intensity_unit}`
    return {
      headline: `${a.coverage_label}：${a.covered}/${a.periods} ${a.period_word}（${pct}）`,
      sub: `${a.intensity_label} ${intensity} · 总量 ${a.module === 'wealth' ? money(a.total_display) : `${a.total_display ?? '—'} ${a.total_unit}`}`,
    }
  }
  const ach = a.achievement === null ? '—' : `${a.achievement}%`
  // 财富是「净额 ÷ 目标」：负达成率必须连同分子分母一起给，否则只是一个看不懂的负数
  if (a.module === 'wealth') {
    const target = a.achievement_target === null ? '—' : money(a.achievement_target)
    const net = a.net_amount === null ? '—' : money(a.net_amount)
    return {
      headline: `净额 ${net} ÷ 目标 ${target} = ${ach}`,
      sub: a.achievement_negative
        ? '净流出：雷达只能画 0–100%，这一轴被压到圆心'
        : '净额对目标达成率',
    }
  }
  return {
    headline: `对目标达成 ${ach}（封顶 ${a.axis_max ?? '—'} 点）`,
    sub: `总量 ${a.module === 'wealth' ? money(a.total_display) : `${a.total_display ?? '—'} ${a.total_unit}`}`,
  }
}

function onMouseMove(e: MouseEvent) {
  const el = chartRef.value
  if (!el || !el.isConnected || !store.radarData) return
  const axes = store.radarData.axes
  const w = el.clientWidth
  const h = el.clientHeight
  if (!w || !h) return

  // 雷达几何：center ['50%','50%'] + radius 65%，从正上方(startAngle=90)起均分
  const cx = w * 0.5
  const cy = h * 0.5
  const r = Math.min(w, h) * 0.65
  const x = e.offsetX
  const y = e.offsetY
  const dist = Math.hypot(x - cx, y - cy)

  if (dist < r * 0.55 || dist > r * 1.15) {
    tip.value = null
    return
  }

  let angle = (Math.atan2(y - cy, x - cx) * 180) / Math.PI + 90
  if (angle < 0) angle += 360
  if (angle >= 360) angle -= 360
  const n = axes.length
  const idx = (n - Math.round((angle / 360) * n)) % n
  const axis = axes[idx]
  const { headline, sub } = tipFor(axis)

  tip.value = { x, y, name: axis.name, headline, sub }
}

function onMouseLeave() {
  tip.value = null
}

function onResize() {
  clearTimeout(resizeTimer)
  resizeTimer = window.setTimeout(() => {
    try { chart?.resize() } catch { /* noop */ }
  }, 150)
}

// radarData 变化 / 年份切换 / 换镜片时重画
watch(
  [() => store.radarData, () => store.currentYear, () => props.basis],
  () => nextTick(render),
)

onMounted(() => {
  nextTick(render)
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  clearTimeout(resizeTimer)
  try { chart?.dispose() } catch { /* noop */ }
  chart = null
})
</script>

<style scoped>
.radar-wrapper {
  position: relative;
  width: 100%;
  height: 300px;
}
.radar-chart {
  width: 100%;
  height: 100%;
}
.radar-tip {
  position: absolute;
  pointer-events: none;
  z-index: 10;
  transform: translate(12px, 12px);
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  color: #1F2937;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  white-space: nowrap;
}
.radar-tip-title {
  font-weight: 600;
  margin-bottom: 2px;
}
.radar-tip-line {
  font-variant-numeric: tabular-nums;
}
.radar-tip-sub {
  margin-top: 2px;
  font-size: 11px;
  color: #6B7280;
}
</style>
