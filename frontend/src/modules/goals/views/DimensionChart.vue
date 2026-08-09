<template>
  <div class="dimension-chart">
    <div class="page-header">
      <h2>🎯 人生维度分布</h2>
      <el-button size="small" @click="$router.push('/goals')">← 目标管理</el-button>
    </div>

    <!-- 雷达图 -->
    <el-card shadow="never">
      <div ref="radarRef" style="height:400px" />
      <el-empty v-if="!loading && allZero" description="还没有设置人生维度的目标" :image-size="80" />
    </el-card>

    <!-- 维度明细 -->
    <el-card shadow="never" style="margin-top:16px">
      <template #header>📋 各维度目标明细</template>
      <div v-loading="loading">
        <div v-for="dim in dimensionData" :key="dim.key" class="dimension-group">
          <h4 class="dim-heading">{{ dim.label }}（{{ dim.count }}）</h4>
          <div v-for="goal in dim.goals" :key="goal.id" class="goal-mini">
            <span class="goal-title">{{ goal.title }}</span>
            <el-progress :percentage="goal.progress_percentage || 0" :stroke-width="4" />
          </div>
        </div>
        <el-empty v-if="!loading && allZero" description="还没有设置人生维度的目标" :image-size="80" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { getGoalList } from '../api/goalApi'
import type { Goal } from '../types/goalTypes'

const DIMENSIONS = [
  { key: '身体健康', label: '🏃 身体健康' },
  { key: '财富积累', label: '💰 财富积累' },
  { key: '学习成长', label: '📚 学习成长' },
  { key: '事业发展', label: '💼 事业发展' },
  { key: '休闲放松', label: '🌿 休闲放松' },
  { key: '系统建设', label: '🧰 系统建设' },
  { key: '创作输出', label: '🎨 创作输出' },
  { key: '生活空间', label: '🏠 生活空间' },
  { key: '其他事项', label: '✨ 其他事项' },
]

const goals = ref<Goal[]>([])
const radarRef = ref<HTMLDivElement>()
const loading = ref(true)
let chartInstance: echarts.ECharts | null = null

const dimensionData = computed(() =>
  DIMENSIONS.map(d => {
    const matched = goals.value.filter(g => g.life_dimension === d.key)
    const totalProgress = matched.length > 0
      ? Math.round(matched.reduce((s, g) => s + (g.progress_percentage || 0), 0) / matched.length)
      : 0
    return { ...d, count: matched.length, goals: matched, totalProgress }
  })
)

const allZero = computed(() => dimensionData.value.every(d => d.count === 0))

function renderRadar() {
  if (!radarRef.value || allZero.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(radarRef.value)

  const data = dimensionData.value

  chartInstance.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, data: ['平均完成率%'] },
    radar: {
      indicator: data.map(d => ({ name: d.label, max: 100 })),
      center: ['50%', '55%'],
      radius: '65%',
      name: { textStyle: { fontSize: 11, color: '#4B5563' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: data.map(d => d.totalProgress),
        name: '平均完成率%',
        areaStyle: { opacity: 0.2, color: '#409eff' },
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
      }],
    }],
  })
}

onMounted(async () => {
  try {
    const res = await getGoalList({ page_size: 999 })
    goals.value = Array.isArray(res.data) ? res.data : res.data?.results ?? []
  } catch {
    goals.value = []
  } finally {
    loading.value = false
  }
  await nextTick()
  setTimeout(renderRadar, 100)
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
})
</script>

<style scoped>
.dimension-chart {
  padding: 24px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 { margin: 0; font-size: 22px; font-weight: 600; }

.dimension-group {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.dimension-group:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }

.dim-heading {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.goal-mini {
  margin-bottom: 8px;
}

.goal-mini:last-child { margin-bottom: 0; }

.goal-title {
  display: block;
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-bottom: 2px;
}
</style>
