<template>
  <div class="location-bubble-chart">
    <div class="chart-header">
      <h3>📍 认识地点分析图</h3>
      <div class="legend">
        <span><span class="dot" style="background:#10B981" /> 滋养率 ≥60%</span>
        <span><span class="dot" style="background:#34D399" /> 滋养率 40–60%</span>
        <span><span class="dot" style="background:#FBBF24" /> 滋养率 20–40%</span>
        <span><span class="dot" style="background:#F87171" /> 滋养率 &lt;20%</span>
        <span class="legend-circle"><svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="6" fill="none" stroke="#9CA3AF" stroke-width="1" /></svg> 圆圈大小 = 人数</span>
      </div>
    </div>
    <div ref="chartRef" class="chart-container" v-loading="loading"></div>
    <div v-if="!locations.length && !loading" class="empty-state">
      <el-empty description="暂无认识地点数据，添加关系时填写「认识地点」即可" />
    </div>
    <div class="chart-footer" v-if="locations.length">
      <span>💡 提示：点击圆圈可查看该地点的关系详情</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { LocationStatsItem } from '../types/relationshipTypes'

const props = defineProps<{
  locations: LocationStatsItem[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'locationClick', name: string): void
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function getColorByRate(rate: number): string {
  if (rate >= 60) return '#10B981'
  if (rate >= 40) return '#34D399'
  if (rate >= 20) return '#FBBF24'
  return '#F87171'
}

function calcPositions(count: number, w: number, h: number): { x: number; y: number }[] {
  const cols = Math.ceil(Math.sqrt(count))
  const rows = Math.ceil(count / cols)
  const cw = w / cols
  const ch = h / rows
  return Array.from({ length: count }, (_, i) => ({
    x: (i % cols) * cw + cw / 2,
    y: Math.floor(i / cols) * ch + ch / 2,
  }))
}

function renderChart() {
  if (!chartRef.value || !props.locations.length) return
  if (!chart) chart = echarts.init(chartRef.value)

  const w = chartRef.value.clientWidth
  const h = chartRef.value.clientHeight || 400
  const maxTotal = Math.max(...props.locations.map(l => l.total), 1)
  const positions = calcPositions(props.locations.length, w, h)

  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const d = params.data
        return `<strong>📍 ${d.name}</strong><br/>
          总人数：${d.total}<br/>
          🟢 滋养型：${d.nourishing}<br/>
          ⚪ 中性：${d.neutral}<br/>
          🟡 消耗型：${d.draining}<br/>
          🔴 有害型：${d.toxic}<hr/>
          滋养率：${d.nourishing_rate}%`
      },
    },
    xAxis: { show: false, min: 0, max: w },
    yAxis: { show: false, min: 0, max: h },
    series: [{
      type: 'scatter',
      symbolSize: (val: number[]) => 20 + (val[2] / maxTotal) * 60,
      data: props.locations.map((loc, i) => ({
        name: loc.name,
        value: [positions[i].x, positions[i].y, loc.total],
        total: loc.total,
        nourishing: loc.nourishing,
        neutral: loc.neutral,
        draining: loc.draining,
        toxic: loc.toxic,
        nourishing_rate: loc.nourishing_rate,
        itemStyle: { color: getColorByRate(loc.nourishing_rate) },
      })),
      label: {
        show: true,
        formatter: '{b}',
        position: 'bottom',
        offset: [0, 12],
        fontSize: 12,
      },
      emphasis: { scale: 1.2 },
    }],
    grid: { show: false, left: 0, top: 0, right: 0, bottom: 0 },
  })
  chart.resize()
}

function handleResize() {
  chart?.resize()
}

watch(() => props.locations, () => nextTick(renderChart), { deep: true })

onMounted(() => {
  nextTick(renderChart)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<style scoped lang="scss">
.location-bubble-chart {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;

  h3 { margin: 0; font-size: 15px; font-weight: 600; }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 12px;
    color: #6B7280;

    .dot {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 4px;
    }

    .legend-circle {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
  }
}

.chart-container {
  width: 100%;
  height: 420px;
}

.empty-state {
  padding: 60px 0;
}

.chart-footer {
  margin-top: 8px;
  font-size: 12px;
  color: #9CA3AF;
  text-align: center;
}
</style>
