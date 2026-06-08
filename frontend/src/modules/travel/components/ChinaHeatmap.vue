<template>
  <div ref="chartRef" class="china-heatmap" style="width: 100%; height: 500px"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import betterEchartsMaps from 'better-echarts-maps/dist/china.js'
import type { HeatmapItem, BubbleItem } from '../types/travelTypes'

const props = defineProps<{
  heatmap: HeatmapItem[]
  bubbles: BubbleItem[]
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function getRatingColor(rating: number | null): string {
  if (!rating) return '#9CA3AF'
  if (rating >= 5) return '#FCD34D'
  if (rating >= 4) return '#60A5FA'
  return '#9CA3AF'
}

function initChart() {
  if (!chartRef.value) return

  // Register China map
  const chinaPkg = (betterEchartsMaps as any)
  const chinaGeoJSON = chinaPkg.China?.[0]?.[1] || chinaPkg
  echarts.registerMap('china', chinaGeoJSON)

  chart = echarts.init(chartRef.value)

  const option = {
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: any) => {
        if (params.seriesType === 'map') {
          const item = props.heatmap.find(h => h.province === params.name)
          return `${params.name}<br/>到访次数：${item?.count || 0}`
        }
        if (params.seriesType === 'scatter') {
          const d = params.data
          const years = d.years?.join(', ') || ''
          return `<strong>${d.name}</strong><br/>
            ${d.province ? `省份：${d.province}<br/>` : ''}
            访问次数：${d.count || 1} 次<br/>
            ${d.value ? `花费：¥${d.value}<br/>` : ''}
            ${d.rating ? `满意度：${'⭐'.repeat(d.rating)}<br/>` : ''}
            ${years ? `年份：${years}` : ''}`
        }
        return ''
      },
    },
    visualMap: {
      min: 0,
      max: 10,
      left: 'left',
      top: 'bottom',
      text: ['高', '低'],
      calculable: true,
      inRange: {
        color: ['#E5E5E5', '#B3D4FF', '#7BB3FF', '#3D7EFF', '#0049B3'],
      },
      textStyle: { color: '#6B7280' },
    },
    series: [
      {
        name: '到访省份',
        type: 'map',
        map: 'china',
        roam: true,
        selectedMode: false,
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold' },
          itemStyle: { areaColor: '#ffd666' },
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 1,
        },
        data: props.heatmap.map(h => ({
          name: h.province,
          value: h.count,
        })),
      },
      {
        name: '城市印记',
        type: 'scatter',
        coordinateSystem: 'geo',
        data: props.bubbles.map(b => ({
          name: b.city,
          value: [b.longitude, b.latitude, b.value || 0],
          province: b.province,
          size: b.size,
          rating: b.rating,
          years: b.years,
          count: b.count,
        })),
        symbolSize: (val: number[], params: any) => params?.size || 12,
        itemStyle: {
          color: (params: any) => getRatingColor(params?.data?.rating),
          borderColor: '#fff',
          borderWidth: 1,
          shadowBlur: 4,
          shadowColor: 'rgba(0,0,0,0.2)',
        },
        label: {
          show: true,
          formatter: (params: any) => params?.data?.name || '',
          fontSize: 10,
          color: '#374151',
          offset: [0, -8],
        },
        emphasis: {
          label: { show: true, fontSize: 12, fontWeight: 'bold' },
          itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.4)' },
        },
      },
    ],
  }

  chart.setOption(option)
}

function handleResize() {
  chart?.resize()
}

watch(() => [props.heatmap, props.bubbles], () => {
  nextTick(initChart)
}, { deep: true })

onMounted(() => {
  nextTick(initChart)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>
