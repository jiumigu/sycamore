<template>
  <div class="chart-section">
    <div class="section-title">📈 体重趋势图</div>
    <div ref="chartRef" class="chart-container" v-loading="loading" />
    <div v-if="!loading && !trend" class="chart-empty">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { WeightTrend, WeightStats } from '../../types/healthTypes'

const props = defineProps<{
  trend: WeightTrend | null
  stats: WeightStats | null
  loading?: boolean
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const option = computed(() => {
  if (!props.trend) return {}

  const records = props.trend.records || []
  const dates = records.map(r => r.date)
  const weights = records.map(r => (r.weight_kg * 2))  // kg → 斤
  const targetLine = (props.trend.target_weight_kg ?? props.stats?.target_weight_kg) * 2

  const weights_jin = weights  // 斤
  const minWeight = weights_jin.length > 0 ? Math.min(...weights_jin) : (targetLine ?? 100)
  const maxWeight = weights_jin.length > 0 ? Math.max(...weights_jin) : (targetLine ?? 100) + 10

  const series: echarts.EChartsOption['series'] = [
    {
      name: '实际体重',
      type: 'line',
      data: weights_jin,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#3B82F6', width: 2 },
      itemStyle: { color: '#3B82F6' },
      areaStyle: { color: 'rgba(59,130,246,0.08)' },
      ...(targetLine ? {
        markLine: {
          silent: true,
          symbol: 'none',
          label: {
            formatter: '目标 {c}斤',
            position: 'start',
            fontSize: 11,
            color: '#EF4444',
          },
          lineStyle: { color: '#EF4444', width: 2, type: 'dashed' },
          data: [{ yAxis: targetLine }],
        },
      } : {}),
    },
  ]

  // 里程碑标记
  if (props.trend.milestones?.length) {
    const milestoneMark = props.trend.milestones.map(m => ({
      name: `第${m.month}月`,
      value: m.target_weight_kg * 2,
      xAxis: dates.length > 0 ? dates[Math.min(m.month * 30, dates.length - 1)] : '',
    }))
    series.push({
      name: '月度目标',
      type: 'scatter',
      data: dates.map((d, i) => {
        const ms = props.trend?.milestones?.find(m => {
          const idx = Math.min(m.month * 30, dates.length - 1)
          return i === idx
        })
        return ms ? ms.target_weight_kg * 2 : null
      }),
      symbol: 'diamond',
      symbolSize: 12,
      itemStyle: { color: '#F59E0B' },
      label: {
        show: true,
        formatter: (p: any) => {
          const idx = (p as any).dataIndex as number
          const ms = props.trend?.milestones?.find((_, i) => {
            const mi = Math.min((i + 1) * 30, dates.length - 1)
            return idx === mi
          })
          return ms ? `第${ms.month}月目标` : ''
        },
        position: 'top',
        fontSize: 11,
        color: '#F59E0B',
      },
    })
  }

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const items = params as Array<Record<string, unknown>>
        let html = `<div style="font-weight:600;margin-bottom:4px">${items[0]?.axisValue || ''}</div>`
        for (const p of items) {
          if (p.value === null || p.value === undefined) continue
          html += `<div style="display:flex;justify-content:space-between;gap:12px">
            <span>${p.marker as string} ${p.seriesName as string}</span>
            <b>${Number(p.value).toFixed(1)} 斤</b>
          </div>`
        }
        return html
      },
    },
    legend: { data: ['实际体重'], bottom: 0, icon: 'circle', itemWidth: 8 },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#E5E7EB' } },
      axisLabel: { color: '#6B7280', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: Math.floor(Math.min(targetLine ?? minWeight, minWeight) - 5),
      max: Math.ceil(maxWeight + 5),
      name: '斤',
      nameTextStyle: { color: '#9CA3AF', fontSize: 11 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#F3F4F6' } },
      axisLabel: {
        color: '#6B7280',
        fontSize: 11,
        formatter: (v: number) => v + ' 斤',
      },
    },
    series,
  }
})

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption(option.value, true)
}

watch(() => [props.trend, props.stats], () => nextTick(renderChart), { deep: true })

onMounted(() => {
  nextTick(renderChart)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

function handleResize() { chart?.resize() }
</script>

<style scoped>
.chart-section { background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 20px; }
.section-title { font-size: 16px; font-weight: 600; color: #1F2937; margin-bottom: 16px; }
.chart-container { height: 320px; }
.chart-empty { text-align: center; padding: 60px 0; color: #9CA3AF; font-size: 14px; }
</style>
