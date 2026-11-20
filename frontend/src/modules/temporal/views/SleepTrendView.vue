<template>
  <div class="sleep-trend">
    <div class="page-header">
      <h2 class="page-title">😴 睡眠趋势</h2>
      <div class="header-actions">
        <el-radio-group v-model="days" size="small" :disabled="loading" @change="load">
          <el-radio-button :value="7">近 7 天</el-radio-button>
          <el-radio-button :value="30">近 30 天</el-radio-button>
          <el-radio-button :value="90">近 90 天</el-radio-button>
        </el-radio-group>
        <!-- 不用 router.back()：从别处进来时「返回」会退到不相干的地方 -->
        <el-button size="small" @click="goTasks">📋 返回任务清单</el-button>
      </div>
    </div>

    <el-alert
      v-if="data && !data.configured"
      type="warning"
      :closable="false"
      show-icon
      title="还没有任务名标「夜间睡眠」角色"
      description="去「映射编辑器」把记录睡眠的那个任务名标成夜间睡眠，这条线才有数。"
      class="cfg-alert"
    />

    <template v-if="data">
      <!-- 结论条：先给一句人话，再给数字。光看图很难判断「这几周到底行不行」 -->
      <div class="verdict" :class="`is-${verdict.tone}`">
        <span class="verdict-main">{{ verdict.text }}</span>
        <span class="verdict-sub">{{ verdict.sub }}</span>
      </div>

      <div class="stat-row">
        <div class="stat">
          <div class="k">平均</div>
          <div class="v">{{ hoursText(data.summary.avg_hours) }}</div>
        </div>
        <div class="stat">
          <div class="k">最短</div>
          <div class="v">{{ hoursText(data.summary.min_hours) }}</div>
        </div>
        <div class="stat">
          <div class="k">最长</div>
          <div class="v">{{ hoursText(data.summary.max_hours) }}</div>
        </div>
        <div class="stat">
          <div class="k">没记录</div>
          <div class="v">{{ data.summary.unrecorded_days }}<span class="u"> 天</span></div>
        </div>
        <div class="stat">
          <div class="k">判定线</div>
          <div class="v small">{{ data.threshold_text }}</div>
        </div>
      </div>

      <el-card shadow="never" class="chart-card" v-loading="loading">
        <div ref="chartRef" class="chart"></div>
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="还没有数据" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { apiErrorText } from '@/shared/utils/apiError'
import * as api from '../api/temporalApi'
import type { SleepSeriesData } from '../types/temporalTypes'

const router = useRouter()
const days = ref(30)
const loading = ref(false)
const data = ref<SleepSeriesData | null>(null)

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const OK_COLOR = '#3D6B8E'
const OFF_LOW_COLOR = '#D97706'
const OFF_HIGH_COLOR = '#B4553F'
const GAP_COLOR = '#CBD5E1'

function hoursText(v: number | null) {
  return v === null ? '—' : `${v} 小时`
}

/** 一句结论 + 一行数字。阈值/状态词都来自后端，这里只负责组织句子。 */
const verdict = computed(() => {
  const d = data.value
  if (!d) return { tone: 'muted', text: '', sub: '' }
  const s = d.summary
  if (!d.configured) {
    return { tone: 'muted', text: '睡眠这条线还没配', sub: '去映射编辑器标一下「夜间睡眠」角色' }
  }
  if (s.recorded_days === 0) {
    return {
      tone: 'muted',
      text: `近 ${s.total_days} 天一条睡眠记录都没有`,
      sub: '不是「睡得正常」，是没记 —— 这段的判断缺依据',
    }
  }
  const ratio = s.ok_days / s.recorded_days
  const tone = ratio >= 0.8 ? 'good' : 'warn'
  const gapPart = s.unrecorded_days ? `，另有 ${s.unrecorded_days} 天没记录` : ''
  return {
    tone,
    text: `记录到的 ${s.recorded_days} 天里，${s.ok_days} 天在 ${d.threshold_text}`,
    sub: `偏离 ${s.off_days} 天${gapPart}；平均 ${s.avg_hours ?? '—'} 小时，最短 ${s.min_hours ?? '—'}、最长 ${s.max_hours ?? '—'}`,
  }
})

function pointColor(hours: number | null, status: string, over: boolean) {
  if (hours === null || status === 'unrecorded') return GAP_COLOR
  if (status === 'ok') return OK_COLOR
  return over ? OFF_HIGH_COLOR : OFF_LOW_COLOR
}

function buildOption(d: SleepSeriesData) {
  const xs = d.days.map((x) => x.date.slice(5))
  const series = d.days.map((x) => ({
    value: x.hours,
    itemStyle: { color: pointColor(x.hours, x.status, x.over) },
  }))

  // 没记录的天：折线本身断开（connectNulls=false），再在底部点一个小灰点，
  // 否则「断开」和「图本来就这么长」看起来一样。
  const gapPoints = d.days
    .map((x, i) => (x.hours === null ? [i, 0] : null))
    .filter((p): p is [number, number] => p !== null)

  const markLines = [
    {
      yAxis: d.threshold_hours,
      lineStyle: { color: '#10B981', type: 'dashed', width: 1 },
      // 下限标签放线的**下方**：线以上基本都被折线占着，标签压上去就看不清了
      label: { formatter: `下限 ${d.threshold_hours}h`, position: 'insideEndBottom', fontSize: 10, color: '#10B981' },
    },
  ]
  if (d.upper_hours !== null) {
    markLines.push({
      yAxis: d.upper_hours,
      lineStyle: { color: '#F59E0B', type: 'dashed', width: 1 },
      label: { formatter: `上限 ${d.upper_hours}h`, position: 'insideEndTop', fontSize: 10, color: '#F59E0B' },
    })
  }

  // 第一条有记录的位置：90 天视图默认缩到这里，否则前面几十天空白把主线挤到右边
  const firstRec = d.days.findIndex((x) => x.hours !== null)
  const zoomStart = firstRec > 0 ? Math.max(0, firstRec - 1) : 0
  const zoomEnd = d.days.length - 1

  return {
    // 左右各留 26：首尾那两个日期标签居中在点上，留窄了会被画布切掉半个
    grid: { left: 26, right: 26, top: 26, bottom: d.days.length > 30 ? 46 : 26, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const idx = params?.[0]?.dataIndex
        const day = d.days[idx]
        if (!day) return ''
        const head = `${day.date}`
        if (day.hours === null) return `${head}<br/>没有记录`
        const tail = day.status === 'ok' ? '在判定线内' : day.over ? `超上限 ${day.gap_hours} 小时` : `低于下限 ${day.gap_hours} 小时`
        return `${head}<br/>${day.hours} 小时 · ${tail}${day.count > 1 ? `<br/>（${day.count} 条记录合计）` : ''}`
      },
    },
    xAxis: {
      type: 'category',
      data: xs,
      axisLabel: { fontSize: 10, color: '#9CA3AF' },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#E5E7EB' } },
    },
    yAxis: {
      type: 'value',
      name: '小时',
      nameTextStyle: { fontSize: 10, color: '#9CA3AF' },
      min: 0,
      // 留 0.5 小时的顶部余量就够；再多一格（13）会把折线压成一条扁带
      max: Math.max(10, Math.ceil((d.summary.max_hours ?? 9) + 0.5)),
      splitLine: { lineStyle: { color: '#F3F4F6' } },
      axisLabel: { fontSize: 10, color: '#9CA3AF' },
    },
    series: [
      {
        name: '睡眠',
        type: 'line',
        data: series,
        connectNulls: false,
        symbolSize: 7,
        lineStyle: { color: OK_COLOR, width: 2 },
        areaStyle: { color: 'rgba(61,107,142,0.08)' },
        markLine: { silent: true, symbol: 'none', data: markLines },
      },
      {
        name: '没记录',
        type: 'scatter',
        data: gapPoints,
        symbolSize: 6,
        itemStyle: { color: GAP_COLOR },
        tooltip: { show: false },
      },
    ],
    ...(d.days.length > 30
      ? {
        dataZoom: [
          { type: 'inside', startValue: zoomStart, endValue: zoomEnd },
          { type: 'slider', height: 14, bottom: 8, startValue: zoomStart, endValue: zoomEnd },
        ],
      }
      : {}),
  }
}

function render() {
  if (!data.value || !chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption(buildOption(data.value), true)
  chart.resize()
}

async function load() {
  loading.value = true
  try {
    const res = await api.getSleepSeries({ days: days.value })
    data.value = res.data
    await nextTick()
    render()
  } catch (e) {
    ElMessage.error(apiErrorText(e, '睡眠数据加载失败'))
  } finally {
    loading.value = false
  }
}

function goTasks() {
  router.push('/temporal/tasks')
}

function onResize() {
  chart?.resize()
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  await load()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped lang="scss">
.sleep-trend {
  padding: 4px 2px 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 12px;
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  white-space: nowrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.cfg-alert {
  margin-bottom: 12px;
}

.verdict {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 12px;
  border-left: 3px solid transparent;

  &.is-good {
    background: #f0f7f2;
    border-left-color: #4a6f4e;
  }
  &.is-warn {
    background: #fdf6ec;
    border-left-color: #d97706;
  }
  &.is-muted {
    background: #f5f6f7;
    border-left-color: #9ca3af;
  }

  .verdict-main {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
  .verdict-sub {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.stat {
  background: #fafafa;
  border-radius: 8px;
  padding: 10px 12px;

  .k {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-bottom: 3px;
  }
  .v {
    font-size: 17px;
    font-weight: 700;
    color: var(--el-text-color-primary);

    &.small {
      font-size: 13px;
      font-weight: 600;
      padding-top: 3px;
    }
  }
  .u {
    font-size: 12px;
    font-weight: 400;
    color: var(--el-text-color-secondary);
  }
}

.chart-card {
  :deep(.el-card__body) {
    padding: 8px 6px;
  }
}

.chart {
  width: 100%;
  height: 360px;
}
</style>
