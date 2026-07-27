<template>
  <div class="time-stats-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">⏱️ 时间统计</h1>
        <el-tag type="warning" class="module-tag">时间追踪</el-tag>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedYear" size="default" style="width: 130px" @change="refreshData">
          <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
        </el-select>
        <el-button size="default" @click="importVisible = true">
          <el-icon><Upload /></el-icon>
          导入数据
        </el-button>
        <el-button size="default" @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6f7ff"><el-icon color="#1890ff" :size="22"><Clock /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ store.overview?.total_hours ?? 0 }}</div>
              <div class="stat-label">总时长（小时）</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f6ffed"><el-icon color="#52c41a" :size="22"><Document /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ store.overview?.total_records ?? 0 }}</div>
              <div class="stat-label">记录数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff7e6"><el-icon color="#fa8c16" :size="22"><Calendar /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ store.overview?.active_days ?? 0 }}</div>
              <div class="stat-label">活跃天数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f0f5ff"><el-icon color="#2f54eb" :size="22"><TrendCharts /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ store.overview?.production_percentage ?? 0 }}%</div>
              <div class="stat-label">生产占比</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 🎯 人生平衡轮 + 📈 月度趋势 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>🎯 人生平衡轮</span></template>
          <div ref="balanceRef" class="chart-box"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>📈 月度趋势</span></template>
          <div ref="trendRef" class="chart-box"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 📋 年度统计 -->
    <el-card class="section-card">
      <template #header><span>📋 年度统计</span></template>
      <el-table :data="yearStats" style="width: 100%" size="small" stripe>
        <el-table-column prop="years" label="年份" width="80" />
        <el-table-column label="记录数" prop="count" align="right" min-width="100" />
        <el-table-column label="OneDay 字数" prop="total_oneday" align="right" min-width="120" />
        <el-table-column label="Page 字数" prop="total_page" align="right" min-width="120" />
        <el-table-column label="总字数" prop="total_words" align="right" min-width="120" />
        <el-table-column label="平均字数" prop="avg_words" align="right" min-width="120" />
      </el-table>
    </el-card>

    <!-- 📅 月度统计 -->
    <el-card class="section-card">
      <template #header><span>📅 月度统计</span></template>
      <el-table :data="monthlyStats" style="width: 100%" size="small" stripe>
        <el-table-column prop="month" label="月份" width="100" />
        <el-table-column label="OneDay 字数" prop="oneday_words" align="right" min-width="120" />
        <el-table-column label="Page 字数" prop="page_words" align="right" min-width="120" />
        <el-table-column label="总字数" prop="total_words" align="right" min-width="120" />
        <el-table-column label="记录数" prop="record_count" align="right" min-width="100" />
        <el-table-column label="日均字数" prop="avg_words" align="right" min-width="120" />
      </el-table>
    </el-card>

    <!-- 周度追踪 -->
    <el-divider />

    <div class="weekly-tracking-section">
      <div class="section-header">
        <h3>📊 年度周度时间追踪</h3>
        <div class="section-controls">
          <el-button @click="refreshCache" :loading="refreshing" size="small">
            <el-icon><Refresh /></el-icon> 刷新缓存
          </el-button>
          <span>基准小时/周：</span>
          <el-input-number v-model="benchmark" :min="10" :max="80" :step="5" size="small" @change="fetchWeeklyData" />
        </div>
      </div>

      <!-- 统计卡片 -->
      <el-row :gutter="16" class="weekly-stats">
        <el-col :span="6">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">{{ weeklyYear }}年累计</div>
            <div class="stat-value">{{ weeklyTotal }}h</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">周均投入</div>
            <div class="stat-value">{{ weeklyAvg }}h</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">达标周数</div>
            <div class="stat-value">{{ qualifiedWeeks }}周</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="stat-card">
            <div class="stat-label">达标率</div>
            <div class="stat-value">{{ qualifyRate }}%</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 年度表格 -->
      <el-card shadow="never" class="weekly-table-card">
        <div class="table-wrapper">
          <table class="tracking-table">
            <thead>
              <tr>
                <th class="col-week">周次</th>
                <template v-for="year in weeklyYears" :key="year">
                  <th class="col-value">{{ year }}值</th>
                  <th class="col-pct">{{ year }}达成率</th>
                </template>
              </tr>
            </thead>
            <tbody>
              <tr v-for="week in 52" :key="week">
                <td class="col-week">{{ week }}</td>
                <template v-for="year in weeklyYears" :key="year">
                  <td class="col-value" :class="getWeekCellClass(year, week, 'value')">
                    {{ getWeekValue(year, week) }}
                  </td>
                  <td class="col-pct" :class="getWeekCellClass(year, week, 'pct')">
                    {{ getWeekPct(year, week) }}
                  </td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="legend">
          <span class="legend-item"><span class="legend-color" style="background:#c8e6c9"></span> 达标 ≥80%</span>
          <span class="legend-item"><span class="legend-color" style="background:#fff9c4"></span> 接近 60-80%</span>
          <span class="legend-item"><span class="legend-color" style="background:#fafafa"></span> 有记录 &lt;60%</span>
          <span class="legend-item"><span class="legend-color" style="background:#f5f5f5;border:1px solid #eee"></span> 无数据</span>
        </div>
      </el-card>
    </div>

    <!-- CSV 导入弹窗 -->
    <el-dialog v-model="importVisible" title="📂 导入数据" width="560px" @close="resetImport">
      <div class="import-body">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :show-file-list="true"
          :limit="1"
          accept=".csv"
          @change="handleFileChange"
        >
          <el-button type="primary">
            <el-icon><Upload /></el-icon>
            选择 CSV 文件
          </el-button>
          <template #tip>
            <div class="upload-tip">支持格式：.csv</div>
          </template>
        </el-upload>

        <el-divider />

        <div class="import-rules">
          <h4>📋 导入规则</h4>
          <ul>
            <li>同一天同一任务会自动合并，时长累加</li>
            <li>已存在的记录会更新时长，不会重复</li>
            <li>任务会自动归类到四大类别</li>
          </ul>
        </div>

        <div v-if="importResult" class="import-result">
          <el-alert
            :title="`导入完成：新增 ${importResult.inserted} 条，更新 ${importResult.updated} 条，跳过 ${importResult.skipped} 条`"
            type="success"
            show-icon
            closable
          />
        </div>
        <div v-if="importError" class="import-result">
          <el-alert :title="importError" type="error" show-icon closable />
        </div>
      </div>

      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!selectedFile" @click="handleImport">
          确认导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Upload, Clock, Document, Calendar, TrendCharts } from '@element-plus/icons-vue'
import { useTemporalStore } from '../stores/temporalStore'
import * as temporalApi from '@/modules/temporal/api/temporalApi'
import * as echarts from 'echarts'

const store = useTemporalStore()

// ─── 年份 ───
const selectedYear = ref(new Date().getFullYear())
const yearOptions = computed(() => {
  const years: number[] = []
  const y = new Date().getFullYear()
  for (let i = y; i >= y - 5; i--) years.push(i)
  return years
})

// ─── 图表 refs ───
const balanceRef = ref<HTMLElement>()
const trendRef = ref<HTMLElement>()

let balanceChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

// ─── 年度统计（来自日记流 stats） ───
const yearStats = computed(() => {
  return (store.stats?.year_stats || []).map(s => ({
    ...s,
    total_oneday: s.total_oneday || 0,
    total_page: s.total_page || 0,
    total_words: s.total_words || 0,
    avg_words: Math.round(s.avg_words || 0),
  }))
})

// ─── 每月字数（来自日记流 stats） ───
const monthlyStats = computed(() => {
  return (store.stats?.month_stats || []).map(m => ({
    month: m.month,
    oneday_words: m.total_oneday || 0,
    page_words: m.total_page || 0,
    total_words: m.total_words || 0,
    record_count: m.count || 0,
    avg_words: m.count ? Math.round((m.total_words || 0) / m.count) : 0,
  }))
})

// ─── 导入 ───
const importVisible = ref(false)
const selectedFile = ref<File | null>(null)
const importing = ref(false)
const importResult = ref<{ inserted: number; updated: number; skipped: number } | null>(null)
const importError = ref('')

function resetImport() {
  selectedFile.value = null
  importResult.value = null
  importError.value = ''
  importing.value = false
}

function handleFileChange(file: any) {
  selectedFile.value = file.raw || null
}

async function handleImport() {
  if (!selectedFile.value) return
  importing.value = true
  importError.value = ''
  importResult.value = null
  try {
    const result = await store.importCsv(selectedFile.value)
    if (result.error) {
      importError.value = result.error
    } else {
      importResult.value = result
      await refreshData()
      // 自动刷新周度缓存
      try { await temporalApi.refreshWeeklyCache() } catch { /* ignore */ }
      ElMessage.success(`导入完成：新增 ${result.inserted} 条，更新 ${result.updated} 条，跳过 ${result.skipped ?? 0} 条`)
    }
  } catch (e: any) {
    importError.value = e?.response?.data?.error || '导入失败'
  } finally {
    importing.value = false
  }
}

// ─── 图表初始化 ───
function initCharts() {
  nextTick(() => {
    initBalanceChart()
    initTrendChart()
  })
}

function initBalanceChart() {
  if (!balanceRef.value) return
  if (!balanceChart) balanceChart = echarts.init(balanceRef.value)

  const data = store.balanceData
  const categories = data?.categories || []
  const maxVal = Math.max(...categories.map(c => c.hours), 1)
  const axisData = categories.map(c => c.name)
  const values = categories.map(c => c.hours)
  const colors = categories.map(c => c.color)

  balanceChart.setOption({
    tooltip: { trigger: 'item', formatter: (p: any) => `${p.name}<br/>${p.value.toFixed(2)}小时 (${data ? categories[p.dataIndex]?.percentage : 0}%)` },
    radar: {
      indicator: axisData.map((name, i) => ({ name, max: maxVal * 1.3 })),
      shape: 'circle',
      splitNumber: 4,
      axisName: { color: '#606266', fontSize: 12 },
      splitLine: { lineStyle: { color: '#e8e8e8' } },
      splitArea: { areaStyle: { color: ['rgba(59,130,246,0.02)', 'rgba(59,130,246,0.05)'] } },
      axisLine: { lineStyle: { color: '#e8e8e8' } },
    },
    series: [{
      type: 'radar',
      data: [{ value: values, name: '时间分配' }],
      areaStyle: { color: 'rgba(59,130,246,0.2)' },
      lineStyle: { color: '#3B82F6', width: 2 },
      itemStyle: { color: colors[0] || '#3B82F6' },
      symbol: 'circle',
      symbolSize: 6,
      label: { show: true, formatter: (p: any) => `${p.value.toFixed(1)}h`, fontSize: 11, color: '#606266' },
    }],
  })
  balanceChart.resize()
}

function initTrendChart() {
  if (!trendRef.value) return
  if (!trendChart) trendChart = echarts.init(trendRef.value)

  const data = store.trendData || []
  const categories = ['生产与创造', '维护与秩序', '滋养与成长', '连接与记录']
  const colorMap = ['#10B981', '#9CA3AF', '#F59E0B', '#3B82F6']

  trendChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: categories, bottom: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
    grid: { left: '3%', right: '4%', bottom: '22%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: data.map(d => d.period).slice(-12), axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', name: '小时' },
    series: categories.map((name, i) => ({
      name,
      type: 'bar' as const,
      stack: 'total',
      barWidth: '65%',
      data: data.map(d => ((d[name] as number) || 0)).slice(-12),
      itemStyle: { color: colorMap[i], borderRadius: [0, 0, 0, 0] },
      label: { show: false },
      emphasis: { focus: 'series' as const },
    })),
  })
  trendChart.resize()
}


// ─── 数据加载 ───
async function refreshData() {
  const year = selectedYear.value
  await Promise.all([
    store.fetchOverview(year),
    store.fetchTrend(year),
    store.fetchBalance(year),
    store.fetchStats(),
  ])
  initCharts()
}

// ─── 周度追踪 ───

const benchmark = ref(30)
const refreshing = ref(false)
const weeklyData = ref<Record<number, Record<number, { hours: number; percentage: number }>>>({})
const weeklyYear = new Date().getFullYear()

const weeklyYears = computed(() => {
  return Object.keys(weeklyData.value).map(Number).sort()
})

const fetchWeeklyData = async () => {
  const res = await temporalApi.getWeeklyTracking({
    start_year: weeklyYear - 5,
    end_year: weeklyYear + 4,
    benchmark: benchmark.value,
  })
  weeklyData.value = res.data.data
}

const refreshCache = async () => {
  refreshing.value = true
  try {
    await temporalApi.refreshWeeklyCache()
    await fetchWeeklyData()
    ElMessage.success('缓存已刷新')
  } catch {
    ElMessage.error('刷新失败')
  } finally {
    refreshing.value = false
  }
}

const getWeekValue = (year: number, week: number): string => {
  const d = weeklyData.value[year]?.[week]
  if (!d || d.hours === 0) return ''
  return d.hours.toFixed(1)
}

const getWeekPct = (year: number, week: number): string => {
  const d = weeklyData.value[year]?.[week]
  if (!d) return ''
  return d.percentage > 0 ? d.percentage.toFixed(0) + '%' : ''
}

const getWeekCellClass = (year: number, week: number, type: string) => {
  const d = weeklyData.value[year]?.[week]
  if (!d || d.hours === 0) return 'cell-empty'
  if (type === 'pct') {
    if (d.percentage >= 80) return 'cell-high'
    if (d.percentage >= 60) return 'cell-mid'
    if (d.percentage > 0) return 'cell-low'
  }
  return ''
}

const weeklyTotal = computed(() => {
  const data = weeklyData.value[weeklyYear] || {}
  return Object.values(data).reduce((sum: number, d: any) => sum + d.hours, 0).toFixed(1)
})

const weeklyAvg = computed(() => {
  const data = weeklyData.value[weeklyYear] || {}
  const weeks = Object.keys(data).length || 1
  const total = Object.values(data).reduce((sum: number, d: any) => sum + d.hours, 0)
  return (total / weeks).toFixed(1)
})

const qualifiedWeeks = computed(() => {
  const data = weeklyData.value[weeklyYear] || {}
  return Object.values(data).filter((d: any) => d.percentage >= 80).length
})

const qualifyRate = computed(() => {
  const data = weeklyData.value[weeklyYear] || {}
  const total = Object.keys(data).length || 1
  return ((qualifiedWeeks.value / total) * 100).toFixed(1)
})

// Resize handler
window.addEventListener('resize', () => {
  balanceChart?.resize()
  trendChart?.resize()
})

onMounted(async () => {
  await refreshData()
  await fetchWeeklyData()
})
</script>

<style scoped lang="scss">
.time-stats-view {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    }

    .header-actions { display: flex; gap: 8px; align-items: center; }
  }

  .stats-row { margin-bottom: 18px;

    .stat-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      .stat-content { display: flex; align-items: center; gap: 14px; padding: 6px 4px;
        .stat-icon { width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .stat-info {
          .stat-value { font-size: 22px; font-weight: 700; color: #1F2937; line-height: 1.3; }
          .stat-label { font-size: 13px; color: #6B7280; }
        }
      }
    }
  }

  .chart-row { margin-bottom: 18px;
    display: flex;
    flex-wrap: wrap;

    .el-col { display: flex; }
    .chart-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); width: 100%; display: flex; flex-direction: column;
      :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
      :deep(.el-card__body) { flex: 1; display: flex; padding: 16px; }
      .chart-box { flex: 1; width: 100%; min-height: 280px; }
    }
  }

  .section-card {
    border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    margin-bottom: 18px;

    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }

    .chart-box { height: 360px; width: 100%; }
  }

  .import-body {
    .upload-tip { font-size: 12px; color: #909399; margin-top: 4px; }

    .import-rules {
      background: #f9fafb; border-radius: 8px; padding: 12px 16px; margin: 8px 0 12px;
      h4 { margin: 0 0 6px; font-size: 13px; color: #1F2937; }
      ul { margin: 0; padding-left: 18px; font-size: 12px; color: #6B7280; line-height: 1.8; }
    }

    .import-result { margin-top: 12px; }
  }

  /* 周度追踪 */
  .weekly-tracking-section {
    margin-top: 8px;

    .section-header {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 16px;
      h3 { margin: 0; font-size: 16px; }
    }
    .section-controls {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .weekly-stats { margin-bottom: 16px; }
    .weekly-table-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .table-wrapper { overflow: auto; max-height: calc(100vh - 300px); }

    .tracking-table {
      border-collapse: collapse; font-size: 12px; white-space: nowrap; width: 100%;
      th, td { padding: 3px 6px; border: 1px solid #eee; text-align: center; min-width: 50px; }
      th { background: #f5f7fa; position: sticky; top: 0; z-index: 1; }
      .col-week { position: sticky; left: 0; background: #f5f7fa; z-index: 2; font-weight: 600; min-width: 40px; }
      .col-value { font-weight: 500; }
      .col-pct { font-size: 11px; color: #666; }
      .cell-high { background: #c8e6c9 !important; font-weight: 700; }
      .cell-mid { background: #fff9c4 !important; }
      .cell-low { background: #fafafa; }
      .cell-empty { background: #f5f5f5; color: #ddd; }
    }
    .legend {
      display: flex; gap: 16px; margin-top: 12px; font-size: 12px; color: #666;
      .legend-color { display: inline-block; width: 16px; height: 16px; border-radius: 2px; vertical-align: middle; margin-right: 4px; }
    }
  }
}
</style>
