<template>
  <div class="trend-chart">
    <div class="trend-chart__title">收支趋势（近{{ months }}个月）</div>
    <div ref="chartRef" class="trend-chart__canvas" />
    <div v-if="!data.length" class="trend-chart__empty">暂无趋势数据</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { TrendItem } from '../../types/wealthTypes'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  data: TrendItem[]
  months?: number
}>(), { months: 12 })

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
}

function updateChart() {
  if (!chart) return
  const months = props.data.map(d => d.yearmon.slice(5))
  const income = props.data.map(d => d.income)
  const expense = props.data.map(d => d.expense)
  const balance = props.data.map(d => d.balance)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      valueFormatter: (v: number) => '¥' + v.toLocaleString(),
    },
    legend: { data: ['收入', '支出', '结余'], bottom: 0 },
    grid: { left: 60, right: 20, bottom: 40, top: 20 },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitNumber: 5,
      axisLabel: {
        formatter: (v: number) => v.toFixed(0),
      },
    },
    series: [
      {
        name: '收入', type: 'bar', data: income,
        itemStyle: { color: '#52c41a', borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 20,
      },
      {
        name: '支出', type: 'bar', data: expense,
        itemStyle: { color: '#f5222d', borderRadius: [2, 2, 0, 0] },
        barMaxWidth: 20,
      },
      {
        name: '结余', type: 'line', data: balance,
        lineStyle: { color: '#1890ff', width: 2 },
        itemStyle: { color: '#1890ff' },
        symbol: 'circle', symbolSize: 6,
      },
    ],
  })
}

onMounted(() => { nextTick(initChart) })
watch(() => props.data, () => { nextTick(updateChart) }, { deep: true })
</script>

<style scoped>
.trend-chart {
  position: relative;
}
.trend-chart__title {
  font-size: 15px; font-weight: 600; margin-bottom: 12px;
}
.trend-chart__canvas {
  width: 100%; height: 280px;
}
.trend-chart__empty {
  position: absolute;
  inset: 0; display: flex;
  align-items: center; justify-content: center;
  color: var(--el-text-color-placeholder);
  font-size: 14px;
}
</style>
