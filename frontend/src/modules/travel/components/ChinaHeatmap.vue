<template>
  <div ref="chartRef" class="china-heatmap" style="width: 100%; height: 500px"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { CITY_MAP_NAME, registerChinaCitiesMap, resolveRegionName, getProvinceBorderRings } from '../utils/chinaCitiesMap'
import type { HeatmapItem, BubbleItem } from '../types/travelTypes'

const props = defineProps<{
  heatmap: HeatmapItem[]
  bubbles: BubbleItem[]
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

/** 未去过的区域底色 */
const NO_DATA_COLOR = '#E9EDF3'

/** 判断两个地名是否同一处（「宁德」↔「宁德市」），用于过滤来源明细里的自指项 */
const NAME_SUFFIX_RE = /(自治州|自治县|地区|市|州|盟|县|区)$/
function sameName(a: string, b: string): boolean {
  if (a === b) return true
  return a.replace(NAME_SUFFIX_RE, '') === b.replace(NAME_SUFFIX_RE, '')
}

/** 热力四档配色（与页面图例一致），第 5 档「未去过」用 NO_DATA_COLOR */
const HEAT_PIECES = [
  { min: 5, label: '深度游', color: '#0049B3' },
  { min: 3, max: 4, label: '频繁', color: '#3D7EFF' },
  { min: 2, max: 2, label: '多次', color: '#7BB3FF' },
  { min: 1, max: 1, label: '偶尔', color: '#B3D4FF' },
]

function getRatingColor(rating: number | null): string {
  if (!rating) return '#9CA3AF'
  if (rating >= 5) return '#FCD34D'
  if (rating >= 4) return '#60A5FA'
  return '#9CA3AF'
}

function initChart() {
  if (!chartRef.value) return

  // 注册全国地级市底图（493 个可着色区域）
  registerChinaCitiesMap()

  chart = echarts.init(chartRef.value)

  // 后端给的地级市名 → 地图区域名（容错：去后缀/补后缀/旧称别名）
  const regionLevel = new Map<string, HeatmapItem>()
  const missed: string[] = []
  const heatData = props.heatmap.reduce<Array<{ name: string; value: number }>>((acc, h) => {
    const region = resolveRegionName(h.name)
    if (!region) {
      missed.push(h.name)
      return acc
    }
    regionLevel.set(region, h)
    acc.push({ name: region, value: h.count })
    return acc
  }, [])
  if (missed.length) {
    console.warn('[ChinaHeatmap] 以下地级市未能对齐地图区域，未参与热力着色：', missed)
  }

  const option = {
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: any) => {
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
        if (params.seriesType === 'lines') return ''
        const item = regionLevel.get(params.name)
        if (!item) return `${params.name}<br/>未去过`
        // 县级市/区县的到访已并入所属地级市，这里把明细列出来（如「福鼎市×1」）
        const detail = (item.sources || []).filter((s) => !sameName(s.city, params.name))
        const detailText = detail.length
          ? `<br/>明细：${detail.map((s) => `${s.city}×${s.count}`).join('、')}`
          : ''
        return `<strong>${params.name}</strong><br/>到访 ${item.count} 次 · ${item.level ?? ''}${detailText}`
      },
    },
    visualMap: {
      type: 'piecewise' as const,
      show: false,
      // 只作用于热力层（seriesIndex 0），否则会把气泡也一起染色
      seriesIndex: 0,
      pieces: HEAT_PIECES,
    },
    // 显式 geo 组件：既是热力底图，也是气泡层（scatter）的坐标系
    geo: {
      map: CITY_MAP_NAME,
      roam: true,
      selectedMode: false,
      itemStyle: {
        areaColor: NO_DATA_COLOR,
        borderColor: '#FFFFFF',
        borderWidth: 0.6,
      },
      emphasis: {
        label: { show: true, fontSize: 11, color: '#1F2937' },
        itemStyle: { areaColor: '#FFD666' },
      },
    },
    series: [
      {
        name: '城市到访',
        type: 'map' as const,
        map: CITY_MAP_NAME,
        geoIndex: 0,
        data: heatData,
        // 城市名默认不显示（493 个区域全标会糊成一片），悬停/点击时才浮出
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 12, fontWeight: 'bold', color: '#1F2937' },
        },
      },
      {
        name: '省界',
        type: 'lines' as const,
        coordinateSystem: 'geo' as const,
        polyline: true,
        silent: true,
        z: 4,
        data: getProvinceBorderRings().map((ring) => ({ coords: ring })),
        lineStyle: { color: '#8CA0BC', width: 1.1, opacity: 0.95 },
      },
      {
        name: '城市印记',
        type: 'scatter' as const,
        coordinateSystem: 'geo' as const,
        z: 6,
        data: props.bubbles.map((b) => ({
          name: b.city,
          value: [b.longitude, b.latitude, b.value || 0],
          province: b.province,
          size: b.size,
          rating: b.rating,
          years: b.years,
          count: b.count,
        })),
        symbolSize: (_val: number[], params: any) => params?.size || 12,
        itemStyle: {
          color: (params: any) => getRatingColor(params?.data?.rating),
          borderColor: '#fff',
          borderWidth: 1,
          shadowBlur: 4,
          shadowColor: 'rgba(0,0,0,0.2)',
        },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 11, fontWeight: 'bold', color: '#374151', offset: [0, -10] },
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
