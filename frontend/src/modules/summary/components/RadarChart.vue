<template>
  <div ref="chartRef" class="radar-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useSummaryStore } from '../stores/summaryStore'

const store = useSummaryStore()
const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (!chartRef.value || !store.radarData) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const { indicators, values } = store.radarData

  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (params: { value?: number; name?: string; seriesName?: string }) => {
        if (!params) return ''
        // 鼠标悬停在雷达图区域时，params 是 series 层级
        if (params.value !== undefined) {
          const idx = indicators.findIndex(i => i.name === params.name)
          const indicator = indicators[idx]
          return `<div style="font-weight:600">${params.name}</div>
            <div>${params.value} / ${indicator?.max ?? 100} 点</div>`
        }
        return `${params.seriesName || ''}`
      },
    },
    radar: {
      indicator: indicators.map(i => ({
        name: i.name,
        max: i.max,
      })),
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
}

watch([() => store.radarData, () => store.currentYear], () => nextTick(render), { deep: true })
onMounted(() => nextTick(render))
</script>

<style scoped>
.radar-chart {
  width: 100%;
  height: 300px;
}
</style>
