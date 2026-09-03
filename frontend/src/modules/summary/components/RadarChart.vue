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
      <div>{{ tip.value }} / {{ tip.max }} 点</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useSummaryStore } from '../stores/summaryStore'

interface TipInfo {
  x: number
  y: number
  name: string
  value: number
  max: number
}

const store = useSummaryStore()
const chartRef = ref<HTMLElement>()
const tip = ref<TipInfo | null>(null)
let chart: echarts.ECharts | null = null
let resizeTimer: number | undefined

function render() {
  const el = chartRef.value
  if (!el || !store.radarData) return
  // DOM 已脱离文档（组件被卸载瞬间）——直接放弃，避免操作空容器
  if (!el.isConnected) return

  try {
    // 实例缺失，或 DOM 元素已被 Vue 重建（实例与元素失联）→ 重建
    if (!chart || echarts.getInstanceByDom(el) !== chart) {
      try { chart?.dispose() } catch { /* noop */ }
      chart = echarts.init(el)
    }
    const { indicators, values } = store.radarData
    chart.setOption({
      // 关闭 ECharts 自带 tooltip（radar 不支持 axis trigger，会崩），改用自定义几何提示
      tooltip: { show: false },
      radar: {
        indicator: indicators.map(i => ({ name: i.name, max: i.max })),
        center: ['50%', '50%'],
        radius: '65%',
        shape: 'circle',
        name: { textStyle: { fontSize: 11, color: '#4B5563' } },
        splitArea: {
          areaStyle: {
            color: ['rgba(16,185,129,0.03)', 'rgba(16,185,129,0.06)']
          }
        },
        axisLine: { lineStyle: { color: 'rgba(0,0,0,0.1)' } },
      },
      series: [{
        type: 'radar',
        data: [{
          value: values,
          name: `${store.radarData.year}年`,
          areaStyle: { color: 'rgba(16,185,129,0.15)' },
          lineStyle: { color: '#10B981', width: 2 },
          itemStyle: { color: '#10B981' },
        }],
      }],
    })
    // 容器可能刚从 display:none 恢复（v-show），同步尺寸
    chart.resize()
  } catch (e) {
    console.warn('[RadarChart] render 失败，已重建实例:', e)
    try { chart?.dispose() } catch { /* noop */ }
    chart = null
  }
}

function onMouseMove(e: MouseEvent) {
  const el = chartRef.value
  if (!el || !el.isConnected || !store.radarData) return
  const { indicators, values } = store.radarData
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

  // 只在顶点附近（半径 0.55~1.15 环形带）显示提示；中心/外部不显示
  if (dist < r * 0.55 || dist > r * 1.15) {
    tip.value = null
    return
  }

  // 角度 → 最近顶点 index
  // 我的公式（atan2 + 90）在屏幕坐标系是顺时针；ECharts 顶点为逆时针排列（startAngle=90 顶部起）
  // 所以取反：(n - idx) % n
  let angle = (Math.atan2(y - cy, x - cx) * 180) / Math.PI + 90
  if (angle < 0) angle += 360
  if (angle >= 360) angle -= 360
  const n = indicators.length
  const idx = (n - Math.round((angle / 360) * n)) % n
  const indicator = indicators[idx]

  tip.value = {
    x: x,
    y: y,
    name: indicator.name,
    value: values[idx],
    max: indicator.max,
  }
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

// 组件常驻（父组件 v-show），radarData 变化/年份切换时刷新
watch([() => store.radarData, () => store.currentYear], () => nextTick(render))

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
</style>
