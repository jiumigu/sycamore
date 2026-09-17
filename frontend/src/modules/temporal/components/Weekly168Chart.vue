<template>
  <div ref="chartRef" class="weekly-168-chart" :style="{ height: height + 'px' }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { WeeklyStructure, WeeklyStructureWeek } from '../types/temporalTypes'
import { ACTIVITY_TYPE_COLOR_MAP, ATTRIBUTION_COLOR_MAP } from '../types/temporalTypes'

const props = withDefaults(defineProps<{
  data: WeeklyStructure | null
  byKey?: 'by_l1' | 'by_l2'
  height?: number
}>(), { height: 340, byKey: 'by_l1' })

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

// 取色：L1 归因用固定配色，L2 活动类型用其主色，其余回退调色板
const PALETTE = ['#6366F1', '#10B981', '#0EA5E9', '#F59E0B', '#EC4899', '#A855F7', '#14B8A6', '#F87171', '#94A3B8', '#CBD5E1']
function colorFor(name: string, idx: number) {
  return ATTRIBUTION_COLOR_MAP[name] || ACTIVITY_TYPE_COLOR_MAP[name] || PALETTE[idx % PALETTE.length]
}

function buildOption() {
  const weeks: WeeklyStructureWeek[] = props.data?.weeks || []
  const xLabels = weeks.map((w) => `${w.year}-W${String(w.week).padStart(2, '0')}`)
  // 收集所有 L1 键并稳定排序
  const l1Keys: string[] = []
  weeks.forEach((w) => {
    Object.keys((w as any)[props.byKey] || {}).forEach((k) => { if (!l1Keys.includes(k)) l1Keys.push(k) })
  })

  const series: any[] = l1Keys.map((k, i) => ({
    name: k,
    type: 'bar' as const,
    stack: 'l1',
    barWidth: '60%',
    itemStyle: { color: colorFor(k, i) },
    data: weeks.map((w) => +((((w as any)[props.byKey] || {})[k]) || 0).toFixed(2)),
  }))

  // 完整度折线（右轴）
  series.push({
    name: '完整度',
    type: 'line',
    yAxisIndex: 1,
    smooth: true,
    symbol: 'circle',
    symbolSize: 5,
    itemStyle: { color: '#F43F5E' },
    lineStyle: { color: '#F43F5E', width: 2 },
    data: weeks.map((w) => +(w.completeness * 100).toFixed(1)),
  })

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { type: 'scroll', bottom: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
    grid: { left: '3%', right: '4%', bottom: '16%', top: '6%', containLabel: true },
    xAxis: { type: 'category', data: xLabels, axisLabel: { rotate: 40, fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '小时' },
      { type: 'value', name: '完整度%', min: 0, max: 100, position: 'right', axisLabel: { formatter: '{value}%' } },
    ],
    series,
  }
}

function render() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption(buildOption(), true)
  chart.resize()
}

watch(() => props.data, () => nextTick(render), { deep: true })

onMounted(() => nextTick(render))
onBeforeUnmount(() => { chart?.dispose(); chart = null })

window.addEventListener('resize', () => chart?.resize())
</script>

<style scoped>
.weekly-168-chart { width: 100%; }
</style>
