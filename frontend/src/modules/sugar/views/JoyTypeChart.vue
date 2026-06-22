<template>
  <div class="joy-type-page">
    <div class="page-header">
      <div class="header-left">
        <h2>🎨 快乐偏好图谱</h2>
        <el-tag size="small" type="warning" effect="plain">小确幸 · 快乐类型分布</el-tag>
      </div>
      <div class="header-actions">
        <el-select v-model="year" placeholder="年份" clearable @change="fetchData" class="year-select">
          <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
        </el-select>
        <el-button size="small" @click="fetchData">刷新</el-button>
      </div>
    </div>

    <!-- 总览卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">快乐类型记录</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ joyTypesWithData.length }}</div>
          <div class="stat-label">活跃类型数</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ dominantType }}</div>
          <div class="stat-label">最偏好类型</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 饼图 -->
      <el-col :span="12">
        <el-card shadow="hover" class="chart-card">
          <template #header><span class="card-title">类型分布</span></template>
          <div ref="pieChartRef" class="chart-container" />
        </el-card>
      </el-col>

      <!-- 排名列表 -->
      <el-col :span="12">
        <el-card shadow="hover" class="chart-card">
          <template #header><span class="card-title">类型排名</span></template>
          <div class="rank-list">
            <div
              v-for="(item, idx) in sortedTypes"
              :key="item.joy_type"
              class="rank-item"
            >
              <span class="rank-num">{{ idx + 1 }}</span>
              <span class="rank-dot" :style="{ background: typeColor(item.joy_type) }" />
              <span class="rank-name">{{ typeIcon(item.joy_type) }} {{ item.joy_type }}</span>
              <span class="rank-count">{{ item.count }} 次</span>
              <span class="rank-bar-wrapper">
                <span class="rank-bar" :style="{ width: item.percentage + '%', background: typeColor(item.joy_type) }" />
              </span>
              <span class="rank-pct">{{ item.percentage }}%</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 平均快乐度排行 -->
    <el-card shadow="hover" class="chart-card">
      <template #header><span class="card-title">平均快乐度排行</span></template>
      <el-table :data="sortedByHappiness" style="width: 100%" size="small">
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <span class="type-cell">{{ typeIcon(row.joy_type) }} {{ row.joy_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="count" label="次数" width="80" align="center" />
        <el-table-column prop="avg_happiness" label="平均快乐" width="100" align="center">
          <template #default="{ row }">
            <span class="happiness-value">{{ row.avg_happiness }}</span>
          </template>
        </el-table-column>
        <el-table-column label="快乐度趋势" min-width="200">
          <template #default="{ row }">
            <div class="happiness-bar-track">
              <div
                class="happiness-bar-fill"
                :style="{ width: (row.avg_happiness / 10) * 100 + '%', background: typeColor(row.joy_type) }"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="total_happiness" label="快乐总值" width="100" align="center" />
      </el-table>
    </el-card>

    <!-- 洞察 -->
    <el-card v-if="insightText" shadow="hover" class="insight-card">
      <template #header><span class="card-title">💡 洞察</span></template>
      <p class="insight-text">{{ insightText }}</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import * as sugarApi from '../api/sugarApi'
import { JOY_TYPE_OPTIONS, JOY_TYPE_COLORS } from '../types/sugarTypes'
import type { JoyTypeStat } from '../types/sugarTypes'

const year = ref<number | undefined>()
const stats = ref<{ joy_types: JoyTypeStat[]; total: number }>({ joy_types: [], total: 0 })
const pieChartRef = ref<HTMLDivElement>()
let pieChart: echarts.ECharts | null = null

const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return [y, y - 1, y - 2, y - 3]
})

const joyTypesWithData = computed(() => stats.value.joy_types.filter(j => j.count > 0))

const sortedTypes = computed(() => [...joyTypesWithData.value].sort((a, b) => b.count - a.count))

const sortedByHappiness = computed(() => [...joyTypesWithData.value].sort((a, b) => b.avg_happiness - a.avg_happiness))

const dominantType = computed(() => {
  if (!sortedTypes.value.length) return '—'
  return `${typeIcon(sortedTypes.value[0].joy_type)} ${sortedTypes.value[0].joy_type}`
})

const insightText = computed(() => {
  const items = sortedTypes.value
  if (items.length === 0) return ''

  const top = items[0]
  const parts: string[] = []

  parts.push(`你最常感受到的快乐来自「${top.joy_type}」，共 ${top.count} 次，占比 ${top.percentage}%。`)

  if (items.length >= 2) {
    const second = items[1]
    parts.push(`其次是「${second.joy_type}」(${second.count} 次)。`)
  }

  const mostHappy = [...items].sort((a, b) => b.avg_happiness - a.avg_happiness)[0]
  if (mostHappy && mostHappy.joy_type !== top.joy_type) {
    parts.push(`虽然「${mostHappy.joy_type}」次数不是最多，但平均快乐度最高（${mostHappy.avg_happiness} 分），说明这类体验质量很高。`)
  }

  return parts.join(' ')
})

function typeColor(t: string): string {
  return JOY_TYPE_COLORS[t] || '#9CA3AF'
}

function typeIcon(t: string): string {
  const found = JOY_TYPE_OPTIONS.find(o => o.value === t)
  return found?.icon || '✨'
}

async function fetchData() {
  try {
    const params: Record<string, unknown> = {}
    if (year.value) params.year = year.value
    const resp = await sugarApi.getJoyTypeStats(params)
    stats.value = resp.data as { joy_types: JoyTypeStat[]; total: number }
    await nextTick()
    renderPieChart()
  } catch {
    stats.value = { joy_types: [], total: 0 }
  }
}

function renderPieChart() {
  if (!pieChartRef.value) return
  if (!pieChart) {
    pieChart = echarts.init(pieChartRef.value)
  }
  const data = sortedTypes.value.map(item => ({
    name: `${typeIcon(item.joy_type)} ${item.joy_type}`,
    value: item.count,
    itemStyle: { color: typeColor(item.joy_type) },
  }))
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie',
      radius: ['35%', '60%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' },
      },
      data,
    }],
  })
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped lang="scss">
.joy-type-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
    h2 { margin: 0; font-size: 20px; font-weight: 600; color: #1F2937; }
  }

  .header-actions {
    display: flex;
    gap: 8px;
    align-items: center;
    .year-select { width: 120px; }
  }
}

.stats-row { margin-bottom: 16px; }

.stat-card {
  border: 1px solid #E5E7EB;
  border-radius: 10px;
  text-align: center;
  padding: 16px;
  :deep(.el-card__body) { padding: 0; }
  .stat-value { font-size: 28px; font-weight: 700; color: #1F2937; line-height: 1.2; }
  .stat-label { font-size: 12px; color: #6B7280; margin-top: 4px; }
}

.chart-card {
  border-radius: 10px;
  margin-bottom: 16px;
  .card-title { font-size: 14px; font-weight: 600; color: #1F2937; }
}

.chart-container {
  height: 320px;
}

.rank-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;

  .rank-num {
    width: 20px;
    font-weight: 600;
    color: #9CA3AF;
    text-align: center;
  }

  .rank-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .rank-name {
    width: 80px;
    font-weight: 500;
    color: #374151;
  }

  .rank-count {
    width: 40px;
    color: #6B7280;
    text-align: right;
  }

  .rank-bar-wrapper {
    flex: 1;
    height: 8px;
    background: #F3F4F6;
    border-radius: 4px;
    overflow: hidden;
  }

  .rank-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s;
  }

  .rank-pct {
    width: 40px;
    text-align: right;
    color: #6B7280;
    font-size: 12px;
  }
}

.type-cell { font-weight: 500; }

.happiness-value {
  font-weight: 600;
  color: #F59E0B;
}

.happiness-bar-track {
  height: 8px;
  background: #F3F4F6;
  border-radius: 4px;
  overflow: hidden;
}

.happiness-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s;
}

.insight-card {
  border-radius: 10px;
  margin-bottom: 16px;
  .card-title { font-size: 14px; font-weight: 600; }
  .insight-text {
    margin: 0;
    font-size: 14px;
    color: #6B7280;
    line-height: 1.8;
  }
}
</style>
