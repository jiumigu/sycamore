<template>
  <el-card shadow="hover" class="body-mind-chart">
    <template #header>
      <div class="card-header">
        <span class="card-title">🩺 身体-状态（按周）</span>
        <el-radio-group v-model="weeks" size="small" @change="fetchData">
          <el-radio-button :value="12">12 周</el-radio-button>
          <el-radio-button :value="26">26 周</el-radio-button>
          <el-radio-button :value="52">52 周</el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <div v-if="loading" class="chart-loading">
      <el-skeleton :rows="4" animated />
    </div>

    <template v-else>
      <!--
        数据够不够，先说出来。
        🔴 v3.64.62 之前这里画的是三条线 + 一句自动结论，
           而「睡眠分」是 `100 − 延迟×1.5 − 夜醒×15` 手算出来的：
           12 周里一条自检都没有 ⇒ 延迟 0、夜醒 0 ⇒ 每周都是 100 分。
           一张满分图比空态更糟 —— 空态你至少知道没数据。
      -->
      <el-alert
        v-if="nightsTotal === 0"
        type="info"
        show-icon
        :closable="false"
        title="这段时间没有做过身体自检"
        :description="`身体自检 ${weeks} 周里 0 条 —— 入睡耗时、夜醒次数都没有来源，这里不画线。`"
      />
      <el-alert
        v-else-if="nightsTotal < MIN_FOR_TREND"
        type="warning"
        show-icon
        :closable="false"
        :title="`这 ${weeks} 周只有 ${nightsTotal} 天做过身体自检`"
        :description="`少于 ${MIN_FOR_TREND} 天的孤立记录串不成趋势。下面的点是真实值，但请不要把它读成规律；把时间窗拉长可以看到更多。`"
      />

      <div v-show="nightsTotal > 0" ref="chartRef" class="bmc__chart" />

      <el-empty
        v-if="nightsTotal === 0"
        description="去「工具 › 身体自查」记一条，这里就有数了"
        :image-size="60"
      >
        <el-button size="small" type="primary" @click="goSelfCheck">去记一条</el-button>
      </el-empty>

      <div v-else class="bmc__foot">
        三条线各用各的纵轴，<strong>不要横向比高低</strong> ——
        分钟、百分比、快乐等级不是同一种刻度。
        空白处是那几周没有对应记录（<strong>不是 0</strong>）。
      </div>
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getBodyMindData } from '../api/summaryApi'

/** 少于这么多天自检就不把线当趋势看（3 个点连起来太容易读成规律） */
const MIN_FOR_TREND = 5

interface WeekData {
  week: string
  week_label: string
  week_start: string
  /** 平均入睡耗时（分钟）；null = 该周没有自检 */
  sleep_latency: number | null
  /** 平均夜醒次数；null = 该周没有自检 */
  awakenings: number | null
  /** 该周做了几天自检 */
  nights: number
  /** 良品率（%）；null = 该周没有产出记录 */
  output_rate: number | null
  output_count: number
  /** 快乐程度均值（5–20）；null = 该周没有小确幸 */
  mood: number | null
}

const router = useRouter()
const chartRef = ref<HTMLDivElement>()
const data = ref<WeekData[]>([])
const loading = ref(true)
const weeks = ref(12)
let chart: echarts.ECharts | null = null

const nightsTotal = computed(() => data.value.reduce((s, d) => s + d.nights, 0))

function goSelfCheck() {
  router.push('/toolkit/health-self-check')
}

/**
 * 三行小图，共享 x 轴
 *
 * 🔴 不把三个量叠进一张图：入睡耗时（分钟）、良品率（%）、快乐程度（5–20）
 *    量纲完全不同，叠在一起必然要「双 y 轴」，而双轴的两条线交叉点毫无含义，
 *    却最容易被读成「这里出问题了」。
 */
function renderChart() {
  if (!chartRef.value || !data.value.length || nightsTotal.value === 0) return

  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const items = data.value
  const labels = items.map((d) => d.week_label)

  const grid = [
    { left: 62, right: 24, top: 30, height: 64 },
    { left: 62, right: 24, top: 142, height: 64 },
    { left: 62, right: 24, top: 254, height: 64 },
  ]
  const axisCommon = { type: 'category' as const, data: labels, boundaryGap: true }

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params: unknown) => {
        const arr = params as { dataIndex: number }[]
        if (!arr?.length) return ''
        const d = items[arr[0].dataIndex]
        return [
          `${d.week_label}`,
          `自检 ${d.nights} 天`,
          `入睡 ${d.sleep_latency == null ? '—' : d.sleep_latency + ' 分'}`,
          `夜醒 ${d.awakenings == null ? '—' : d.awakenings + ' 次'}`,
          `产出 ${d.output_rate == null ? '—' : d.output_rate + '%'}（${d.output_count} 条）`,
          `快乐 ${d.mood == null ? '—' : d.mood}`,
        ].join('<br/>')
      },
    },
    grid,
    xAxis: [
      { ...axisCommon, gridIndex: 0, axisLabel: { show: false }, axisTick: { show: false } },
      { ...axisCommon, gridIndex: 1, axisLabel: { show: false }, axisTick: { show: false } },
      { ...axisCommon, gridIndex: 2, axisLabel: { fontSize: 10, interval: 'auto' } },
    ],
    yAxis: [
      {
        type: 'value', gridIndex: 0, name: '入睡(分)', nameTextStyle: { fontSize: 10 },
        min: 0, axisLabel: { fontSize: 10 },
        splitLine: { lineStyle: { type: 'dashed', color: '#E5E7EB' } },
      },
      {
        type: 'value', gridIndex: 1, name: '良品率%', nameTextStyle: { fontSize: 10 },
        min: 0, max: 100, axisLabel: { fontSize: 10 },
        splitLine: { lineStyle: { type: 'dashed', color: '#E5E7EB' } },
      },
      {
        // 🔴 量程是 5–20（SugarRecord.level_of_happiness），不是 1–10。
        //    旧版写死 max:10，所有点都顶在天花板上。
        type: 'value', gridIndex: 2, name: '快乐(5–20)', nameTextStyle: { fontSize: 10 },
        min: 5, max: 20, axisLabel: { fontSize: 10 },
        splitLine: { lineStyle: { type: 'dashed', color: '#E5E7EB' } },
      },
    ],
    series: [
      {
        name: '入睡耗时', type: 'bar', xAxisIndex: 0, yAxisIndex: 0,
        data: items.map((d) => d.sleep_latency),
        itemStyle: { color: '#6366F1', borderRadius: [3, 3, 0, 0] },
        barWidth: 14,
      },
      {
        name: '良品率', type: 'line', xAxisIndex: 1, yAxisIndex: 1,
        data: items.map((d) => d.output_rate),
        lineStyle: { color: '#10B981', width: 2 },
        symbol: 'circle', symbolSize: 6,
        itemStyle: { color: '#10B981' },
        // 空周必须断开：连起来会让人以为「那周测过了」
        connectNulls: false,
      },
      {
        name: '快乐程度', type: 'line', xAxisIndex: 2, yAxisIndex: 2,
        data: items.map((d) => d.mood),
        lineStyle: { color: '#F59E0B', width: 2 },
        symbol: 'diamond', symbolSize: 6,
        itemStyle: { color: '#F59E0B' },
        connectNulls: false,
      },
    ],
  })
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getBodyMindData({ weeks: weeks.value })
    data.value = res.data as WeekData[]
  } catch {
    data.value = []
  } finally {
    loading.value = false
  }
  // 🔴 必须**先关 loading 再等 nextTick**：模板在 `v-if="loading"` 为真时
  //    渲染的是 skeleton，`v-else` 里的图表容器根本不存在 ⇒ `chartRef.value`
  //    是 undefined，`renderChart` 静默 return，卡片上留一块 340px 的空白。
  //    （老坑：图表容器必须先渲染出来，echarts 才量得到尺寸。）
  await nextTick()
  renderChart()
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
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

.bmc__chart {
  height: 340px;
  margin-top: 10px;
}

.bmc__foot {
  margin-top: 8px;
  font-size: 11px;
  line-height: 1.7;
  color: var(--el-text-color-placeholder);
}
.bmc__foot strong {
  font-weight: 600;
  color: var(--el-text-color-secondary);
}
</style>
