<template>
  <el-card shadow="hover" class="body-mind-chart">
    <template #header>
      <div class="card-header">
        <span class="card-title">🔗 身体-状态关联（近12周）</span>
        <el-tag size="small" type="info">睡眠 vs 良品率 vs 情绪</el-tag>
      </div>
    </template>

    <div v-if="loading" class="chart-loading">
      <el-skeleton :rows="4" animated />
    </div>

    <template v-else>
      <div ref="chartRef" style="height: 350px" />

      <el-alert
        v-if="correlationInsight"
        :title="correlationInsight"
        type="info"
        show-icon
        :closable="false"
        style="margin-top: 12px"
      />

      <el-empty v-if="!data.length && !loading" description="暂无身体检查数据" :image-size="60" />
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { getBodyMindData } from '../api/summaryApi'

interface WeekData {
  week: string
  week_label: string
  sleep_score: number
  output_rate: number | null
  mood: number
}

const chartRef = ref<HTMLDivElement>()
const data = ref<WeekData[]>([])
const loading = ref(true)
let chart: echarts.ECharts | null = null

const correlationInsight = computed(() => {
  const items = data.value
  if (items.length < 2) return ''

  // 排除 output_rate 为 null 的周
  const withOutput = items.filter(d => d.output_rate !== null)
  if (withOutput.length < 2) return '数据积累中，暂无明显关联模式。'

  const sorted = [...withOutput].sort((a, b) => a.sleep_score - b.sleep_score)
  const worst = sorted[0]
  const best = sorted[sorted.length - 1]

  const parts: string[] = []

  if (worst.output_rate !== null && best.output_rate !== null) {
    const diff = best.output_rate - worst.output_rate
    if (diff > 10) {
      parts.push(`睡眠最好的周比最差的周良品率高 ${diff.toFixed(0)}%`)
    }
  }

  const moodValues = items.map(d => d.mood).filter(m => m > 0)
  if (moodValues.length >= 4) {
    const avg = moodValues.reduce((a, b) => a + b, 0) / moodValues.length
    const highs = moodValues.filter(m => m > avg + 1).length
    const lows = moodValues.filter(m => m < avg - 1).length
    if (highs > 0 || lows > 0) {
      parts.push(`情绪波动：${highs} 周高于均值，${lows} 周低于均值`)
    }
  }

  return parts.length > 0 ? '💡 ' + parts.join('；') : '数据积累中，暂无明显关联模式。'
})

function renderChart() {
  if (!chartRef.value || !data.value.length) return

  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const items = data.value

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['睡眠分', '良品率%', '情绪分'],
      bottom: 0,
      textStyle: { fontSize: 12 },
    },
    grid: {
      left: 50,
      right: 50,
      top: 20,
      bottom: 40,
    },
    xAxis: {
      type: 'category',
      data: items.map(d => d.week_label),
      axisLabel: { fontSize: 11 },
    },
    yAxis: [
      {
        type: 'value',
        name: '分数',
        min: 0,
        max: 100,
        nameTextStyle: { fontSize: 11 },
        splitLine: { lineStyle: { type: 'dashed', color: '#E5E7EB' } },
      },
      {
        type: 'value',
        name: '情绪',
        min: 1,
        max: 10,
        nameTextStyle: { fontSize: 11 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '睡眠分',
        type: 'bar',
        data: items.map(d => d.sleep_score),
        itemStyle: { color: '#6366F1', borderRadius: [4, 4, 0, 0] },
        barWidth: 20,
      },
      {
        name: '良品率%',
        type: 'line',
        data: items.map(d => d.output_rate),
        lineStyle: { color: '#10B981', width: 2 },
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: '#10B981' },
        connectNulls: false,
      },
      {
        name: '情绪分',
        type: 'line',
        yAxisIndex: 1,
        data: items.map(d => d.mood),
        lineStyle: { color: '#F59E0B', width: 2, type: 'dashed' },
        symbol: 'diamond',
        symbolSize: 6,
        itemStyle: { color: '#F59E0B' },
      },
    ],
  })
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getBodyMindData({ weeks: 12 })
    data.value = res.data as WeekData[]
    await nextTick()
    renderChart()
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

onBeforeUnmount(() => {
  chart?.dispose()
})
</script>

<style scoped>
.body-mind-chart {
  border-radius: 10px;
  margin-bottom: 16px;
  border: none;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.chart-loading {
  padding: 20px;
}
</style>
