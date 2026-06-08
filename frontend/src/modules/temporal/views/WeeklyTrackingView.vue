<template>
  <div class="weekly-tracking">
    <div class="page-header">
      <h2>📊 年度周度时间追踪</h2>
      <div class="controls">
        <el-button @click="refreshCache" :loading="refreshing" size="small">
          <el-icon><Refresh /></el-icon>
          刷新缓存
        </el-button>
        <span>基准小时/周：</span>
        <el-input-number v-model="benchmark" :min="10" :max="80" :step="5" @change="fetchData" />
        <span class="hint">百分比 = 实际小时 / 基准小时 × 100%</span>
      </div>
    </div>

    <!-- 统计概览卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">{{ currentYear }}年累计</div>
          <div class="stat-value">{{ currentYearTotal }}h</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">周均投入</div>
          <div class="stat-value">{{ currentYearAvg }}h</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">达标周数</div>
          <div class="stat-value">{{ currentYearQualified }}周</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">达标率</div>
          <div class="stat-value">{{ currentYearQualifyRate }}%</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主表格 -->
    <el-card class="table-card">
      <div class="table-wrapper">
        <table class="tracking-table">
          <thead>
            <tr>
              <th class="col-week">周次</th>
              <template v-for="year in years" :key="year">
                <th class="col-value">{{ year }}值</th>
                <th class="col-pct">{{ year }}达成率</th>
              </template>
            </tr>
          </thead>
          <tbody>
            <tr v-for="week in 52" :key="week">
              <td class="col-week">{{ week }}</td>
              <template v-for="year in years" :key="year">
                <td class="col-value" :class="getCellClass(year, week, 'value')">
                  {{ getValue(year, week) }}
                </td>
                <td class="col-pct" :class="getCellClass(year, week, 'pct')">
                  {{ getPercentage(year, week) }}
                </td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 图例 -->
      <div class="legend">
        <span class="legend-item"><span class="legend-color" style="background:#e8f5e9"></span> 达标 ≥80%</span>
        <span class="legend-item"><span class="legend-color" style="background:#fff9c4"></span> 接近 60-80%</span>
        <span class="legend-item"><span class="legend-color" style="background:#fafafa"></span> 有记录 &lt;60%</span>
        <span class="legend-item"><span class="legend-color" style="background:#f5f5f5;border:1px solid #eee"></span> 无数据</span>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as temporalApi from '@/modules/temporal/api/temporalApi'

const benchmark = ref(30)
const trackingData = ref<Record<number, Record<number, { hours: number; percentage: number }>>>({})
const years = ref<number[]>([])

const refreshing = ref(false)

const refreshCache = async () => {
  refreshing.value = true
  try {
    await temporalApi.refreshWeeklyCache()
    await fetchData()
    ElMessage.success('缓存已刷新')
  } catch {
    ElMessage.error('刷新失败')
  } finally {
    refreshing.value = false
  }
}

const currentYear = new Date().getFullYear()

const fetchData = async () => {
  const res = await temporalApi.getWeeklyTracking({
    start_year: currentYear - 5,
    end_year: currentYear + 4,
    benchmark: benchmark.value,
  })
  trackingData.value = res.data.data
  years.value = Object.keys(res.data.data).map(Number).sort()
}

const getValue = (year: number, week: number): string => {
  const d = trackingData.value[year]?.[week]
  if (!d || d.hours === 0) return ''
  return d.hours.toFixed(1)
}

const getPercentage = (year: number, week: number): string => {
  const d = trackingData.value[year]?.[week]
  if (!d) return ''
  return d.percentage > 0 ? d.percentage.toFixed(0) + '%' : ''
}

const getCellClass = (year: number, week: number, type: string) => {
  const d = trackingData.value[year]?.[week]
  if (!d || d.hours === 0) return 'cell-empty'
  if (type === 'pct') {
    if (d.percentage >= 80) return 'cell-high'
    if (d.percentage >= 60) return 'cell-mid'
    if (d.percentage > 0) return 'cell-low'
  }
  return ''
}

// 当前年统计
const currentYearTotal = computed(() => {
  const data = trackingData.value[currentYear] || {}
  return Object.values(data).reduce((sum: number, d: any) => sum + d.hours, 0).toFixed(1)
})

const currentYearAvg = computed(() => {
  const data = trackingData.value[currentYear] || {}
  const weeks = Object.keys(data).length || 1
  const total = Object.values(data).reduce((sum: number, d: any) => sum + d.hours, 0)
  return (total / weeks).toFixed(1)
})

const currentYearQualified = computed(() => {
  const data = trackingData.value[currentYear] || {}
  return Object.values(data).filter((d: any) => d.percentage >= 80).length
})

const currentYearQualifyRate = computed(() => {
  const data = trackingData.value[currentYear] || {}
  const total = Object.keys(data).length || 1
  return ((currentYearQualified.value / total) * 100).toFixed(1)
})

onMounted(fetchData)
</script>

<style scoped lang="scss">
.weekly-tracking {
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;

  h2 { margin: 0; font-size: 18px; }

  .controls {
    display: flex;
    align-items: center;
    gap: 8px;
    .hint { font-size: 12px; color: #999; }
  }
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  .stat-label { font-size: 12px; color: #999; }
  .stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
}

.table-wrapper {
  overflow: auto;
  max-height: calc(100vh - 300px);
}

.tracking-table {
  border-collapse: collapse;
  font-size: 12px;
  white-space: nowrap;

  th, td {
    padding: 3px 6px;
    border: 1px solid #eee;
    text-align: center;
    min-width: 50px;
  }

  th {
    background: #f5f7fa;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .col-week {
    position: sticky;
    left: 0;
    background: #f5f7fa;
    z-index: 2;
    font-weight: 600;
    min-width: 40px;
  }

  .col-value { font-weight: 500; }
  .col-pct { font-size: 11px; color: #666; }

  .cell-high { background: #c8e6c9 !important; font-weight: 700; }
  .cell-mid { background: #fff9c4 !important; }
  .cell-low { background: #fafafa; }
  .cell-empty { background: #f5f5f5; color: #ddd; }
}

.legend {
  display: flex;
  gap: 16px;
  margin-top: 12px;
  font-size: 12px;
  color: #666;

  .legend-color {
    display: inline-block;
    width: 16px;
    height: 16px;
    border-radius: 2px;
    vertical-align: middle;
    margin-right: 4px;
  }
}
</style>
