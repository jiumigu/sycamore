<template>
  <div class="weekly-tracking">
    <div class="page-header">
      <h2>📅 168h 周结构（时间面）</h2>
      <div class="controls">
        <el-radio-group v-model="level" size="small" @change="renderView">
          <el-radio-button value="by_l1">按 L1 归因</el-radio-button>
          <el-radio-button value="by_l2">按 L2 类型</el-radio-button>
        </el-radio-group>
        <el-button @click="loadData" :loading="loading" size="small">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-button type="primary" size="small" @click="$router.push('/temporal/tasks')">📋 任务清单</el-button>
      </div>
    </div>

    <!-- 统计概览卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">近 {{ weeks.length }} 周累计</div>
          <div class="stat-value">{{ totalHours }}h</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">周均投入</div>
          <div class="stat-value">{{ avgHours }}h</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">平均记录完整度</div>
          <div class="stat-value">{{ avgCompleteness }}%</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">赎回·成长占比</div>
          <div class="stat-value">{{ towardRatio }}%</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主图表 -->
    <el-card class="chart-card" v-loading="loading">
      <template #header><span>近 {{ weeks.length }} 周堆叠结构</span></template>
      <Weekly168Chart :data="{ weeks }" :by-key="level" :height="340" />
    </el-card>

    <!-- 赎回四色块 -->
    <el-card class="four-color-card">
      <template #header><span>💎 赎回四色时间面（近 {{ weeks.length }} 周累计）</span></template>
      <div class="four-color-grid">
        <div v-for="c in fourColor" :key="c.key" class="fc-item" :style="{ borderColor: c.color }">
          <span class="fc-dot" :style="{ background: c.color }"></span>
          <span class="fc-label">{{ c.label }}</span>
          <span class="fc-value">{{ c.hours }}h</span>
          <span class="fc-pct">{{ c.pct }}%</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import * as temporalApi from '@/modules/temporal/api/temporalApi'
import Weekly168Chart from '../components/Weekly168Chart.vue'
import type { WeeklyStructureWeek } from '../types/temporalTypes'
import { ATTRIBUTION_COLOR_MAP } from '../types/temporalTypes'

const weeks = ref<WeeklyStructureWeek[]>([])
const level = ref<'by_l1' | 'by_l2'>('by_l1')
const loading = ref(false)

const totalHours = computed(() => {
  const all = weeks.value.flatMap((w) => Object.values(w.by_l1 as Record<string, number>))
  return all.reduce((s, h) => s + h, 0).toFixed(1)
})
const avgHours = computed(() => {
  if (!weeks.value.length) return '0.0'
  return (parseFloat(totalHours.value) / weeks.value.length).toFixed(1)
})
const avgCompleteness = computed(() => {
  if (!weeks.value.length) return 0
  const avg = weeks.value.reduce((s, w) => s + w.completeness, 0) / weeks.value.length
  return (avg * 100).toFixed(2)
})

const fourColor = computed(() => {
  const agg: Record<string, number> = {}
  weeks.value.forEach((w) => {
    Object.entries(w.by_l1 || {}).forEach(([k, v]) => { agg[k] = (agg[k] || 0) + v })
  })
  const total = Object.values(agg).reduce((s, v) => s + v, 0) || 1
  const order = ['成长', '关系', '维持', '谋生', '流失']
  return order
    .filter((k) => k in agg)
    .map((k) => ({
      key: k, label: k, color: ATTRIBUTION_COLOR_MAP[k] || '#94A3B8',
      hours: Math.round(agg[k]), pct: ((agg[k] / total) * 100).toFixed(1),
    }))
})
const towardRatio = computed(() => {
  const t = fourColor.value.find((c) => c.key === '成长')
  return t ? t.pct : '0.0'
})

async function loadData() {
  loading.value = true
  try {
    const res = await temporalApi.getWeeklyStructure({ weeks: 12 })
    weeks.value = (res.data.weeks || []).slice(-12)
  } catch { weeks.value = [] } finally { loading.value = false }
}
function renderView() { /* 图表由 byKey prop 响应式切换，无需重新请求 */ }

onMounted(loadData)
</script>

<style scoped lang="scss">
.weekly-tracking { padding: 24px;
  .page-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px;
    h2 { margin: 0; font-size: 18px; }
    .controls { display: flex; align-items: center; gap: 8px; margin-left: auto; } }
  .stats-row { margin-bottom: 16px; }
  .stat-card { text-align: center; border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    .stat-label { font-size: 12px; color: #999; }
    .stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; } }
  .chart-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 16px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; } }
  .four-color-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; } }
  .four-color-grid { display: flex; gap: 12px; flex-wrap: wrap;
    .fc-item { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border: 1px solid #eee; border-radius: 8px; min-width: 150px;
      .fc-dot { width: 12px; height: 12px; border-radius: 3px; }
      .fc-label { font-size: 13px; color: #4b5563; }
      .fc-value { font-size: 16px; font-weight: 700; }
      .fc-pct { font-size: 12px; color: #9ca3af; } } }
}
</style>
