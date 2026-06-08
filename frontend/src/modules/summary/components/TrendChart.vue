<template>
  <div ref="chartRef" class="trend-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useSummaryStore } from '../stores/summaryStore'
import { MONTHLY_TARGET } from '../types/summaryTypes'

const store = useSummaryStore()
const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (!chartRef.value || !store.trendData.length) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const months = store.trendData.map(d => `${d.month}月`)
  const modules = ['wealth', 'health', 'times', 'words', 'sugar', 'travel', 'book'] as const
  const colorMap: Record<string, string> = {
    wealth: '#F59E0B', health: '#10B981', times: '#6366F1',
    words: '#EC4899', sugar: '#F97316', travel: '#06B6D4', book: '#3B82F6',
  }
  const labelMap: Record<string, string> = {
    wealth: '财富', health: '健康', times: '时间投入',
    words: '文字记录', sugar: '小确幸', travel: '旅行', book: '阅读',
  }

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: { seriesName: string; value: number; color: string }[][]) => {
        if (!params?.[0]) return ''
        const p = params[0]
        let html = `<div style="font-weight:600;margin-bottom:4px">${p[0].axisValue}</div>`
        const sorted = [...p].filter(x => x.value > 0).sort((a, b) => b.value - a.value)
        for (const s of sorted) {
          html += `<div style="display:flex;justify-content:space-between;gap:12px">
            <span>${s.marker} ${s.seriesName}</span>
            <span style="font-weight:600">${s.value} 点</span>
          </div>`
        }
        return html
      },
    },
    legend: {
      data: Object.values(labelMap),
      bottom: 0,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 10,
    },
    grid: { left: 50, right: 16, top: 20, bottom: 48 },
    xAxis: {
      type: 'category',
      data: months,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '进度点',
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 },
    },
    series: [
      ...modules.map(k => ({
        name: labelMap[k],
        type: 'bar' as const,
        stack: 'total',
        barMaxWidth: 18,
        itemStyle: { color: colorMap[k], borderRadius: [0, 0, 0, 0] as unknown as number },
        data: store.trendData.map(d => d[k]),
      })),
      {
        name: '月目标',
        type: 'line' as const,
        data: store.trendData.map(() => MONTHLY_TARGET),
        lineStyle: { color: '#EF4444', width: 2, type: 'dashed' as const },
        itemStyle: { color: '#EF4444' },
        symbol: 'none',
        z: 10,
      },
    ],
  }, true) // true = 不合并，完全替换
}

watch([() => store.trendData, () => store.currentYear], () => nextTick(render), { deep: true })
onMounted(() => nextTick(render))

// 不再监听窗口resize（由外层组件处理）
</script>

<style scoped>
.trend-chart {
  width: 100%;
  height: 300px;
}
</style>
