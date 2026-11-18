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

  /**
   * 🔴 画 `daily` 而不是 `records`：一天记两条时，category 轴会出现两个同名日期，
   * 折线在同一天折返一段 —— 看起来像「当天暴跌又涨回」，其实是两次称重。
   * 也不在 `daily` 缺失时回退 `records`：那会把「后端没给这个字段」伪装成能画。
   */
  const points = props.trend.daily ?? []
  const dates = points.map(p => p.date)
  const weights_jin = points.map(p => p.weight_jin)

  // 当前阶段目标：第一个未达成的里程碑，或最后一个
  const currentMilestone = props.trend.milestones?.find(m => !m.is_achieved)
    ?? props.trend.milestones?.[props.trend.milestones.length - 1]
  const monthlyTarget = currentMilestone ? currentMilestone.target_weight_kg * 2 : null
  const finalTarget = ((props.trend?.target_weight_kg ?? props.stats?.target_weight_kg ?? 0) as number) * 2

  const minWeight = weights_jin.length > 0 ? Math.min(...weights_jin) : (finalTarget ?? 100)
  const maxWeight = weights_jin.length > 0 ? Math.max(...weights_jin) : (finalTarget ?? 100) + 10

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
      ...(monthlyTarget ? {
        markLine: {
          silent: true,
          symbol: 'none',
          label: {
            formatter: `本月目标 ${monthlyTarget}斤`,
            position: 'start',
            fontSize: 11,
            color: '#EF4444',
          },
          lineStyle: { color: '#EF4444', width: 2, type: 'dashed' },
          data: [{ yAxis: monthlyTarget }],
        },
      } : {}),
    },
  ]

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const items = params as Array<Record<string, unknown>>
        const day = points[Number(items[0]?.dataIndex ?? -1)]
        let html = `<div style="font-weight:600;margin-bottom:4px">${items[0]?.axisValue || ''}</div>`
        for (const p of items) {
          if (p.value === null || p.value === undefined) continue
          html += `<div style="display:flex;justify-content:space-between;gap:12px">
            <span>${p.marker as string} ${p.seriesName as string}</span>
            <b>${Number(p.value).toFixed(1)} 斤</b>
          </div>`
        }
        // 一天称了多次：把每一声都列出来，说清画的是哪一条。
        // 只说「2 次」不说数值，用户会怀疑另一次没存进去；只说数值不说「取最后一次」，又会问这是哪次。
        if (day && day.count > 1) {
          const each = day.readings
            .map(r => `${r.weight_jin}${r.measure_time_display ? `（${r.measure_time_display}）` : ''}`)
            .join(' / ')
          html += `<div style="margin-top:4px;color:#909399;font-size:11px;line-height:1.5">
            当天记了 ${day.count} 次：${each}<br/>图上这一点取最后一次
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
      min: Math.floor(Math.min(finalTarget ?? minWeight, minWeight) - 5),
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
