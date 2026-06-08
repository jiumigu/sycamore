<template>
  <div class="asset-trend">
    <div class="asset-trend__header">
      <span class="asset-trend__title">资产趋势</span>
      <el-radio-group v-model="months" size="small" @change="$emit('update:months', $event)">
        <el-radio-button :value="3">3月</el-radio-button>
        <el-radio-button :value="6">6月</el-radio-button>
        <el-radio-button :value="12">1年</el-radio-button>
        <el-radio-button :value="0">全部</el-radio-button>
      </el-radio-group>
    </div>
    <div ref="chartRef" class="asset-trend__canvas" />
    <div v-if="!data.length" class="asset-trend__empty">暂无趋势数据</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { AssetTrendItem } from '../../types/wealthTypes'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  data: AssetTrendItem[]
  months?: number
}>()

const emit = defineEmits<{
  'update:months': [val: number]
}>()

const months = ref(props.months ?? 12)
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
}

function updateChart() {
  if (!chart) return
  const labels = props.data.map(d => d.yearmon)
  const series = [
    { name: '总资产', key: 'total', color: '#1890ff' },
    { name: '现金流', key: 'flow_total', color: '#52c41a' },
    { name: '公积金', key: 'accumulationfund', color: '#fa8c16' },
  ]

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v: number) => '¥' + v.toLocaleString(),
    },
    legend: { data: series.map(s => s.name), bottom: 0 },
    grid: { left: 60, right: 20, bottom: 40, top: 20 },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => (v / 10000).toFixed(0) + 'w' },
    },
    series: series.map(s => ({
      name: s.name,
      type: 'line',
      data: props.data.map(d => d[s.key as keyof AssetTrendItem] as number),
      lineStyle: { color: s.color, width: 2 },
      itemStyle: { color: s.color },
      symbol: 'circle', symbolSize: 5,
    })),
  })
}

onMounted(() => { nextTick(initChart) })
watch(() => props.data, () => { nextTick(updateChart) }, { deep: true })
</script>

<style scoped>
.asset-trend__header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
}
.asset-trend__title {
  font-size: 15px; font-weight: 600;
}
.asset-trend__canvas {
  width: 100%; height: 280px;
}
.asset-trend__empty {
  padding: 40px; text-align: center; color: var(--el-text-color-placeholder);
}
</style>
