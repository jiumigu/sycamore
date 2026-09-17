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
        <el-button type="primary" size="default" @click="$router.push('/temporal/tasks')">
          📋 任务清单
        </el-button>
        <el-button size="default" @click="$router.push('/temporal/mapping')">
          🧩 映射编辑器
        </el-button>
        <el-button size="default" @click="$router.push('/temporal/contrib')">
          📊 贡献图
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
              <div class="stat-value">{{ (store.completeness?.completeness ?? 0) * 100 }}%</div>
              <div class="stat-label">记录完整度（已归类 / 16h·天）</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 🌞 旭日图（L1/L2） + 📈 月度趋势（L1） -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>🌞 时间结构（L1 归因 › L2 类型 › L3 任务）</span></template>
          <SunburstChart :data="store.sunburst" :height="400" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>📈 月度趋势（按 L1 归因）</span></template>
          <div ref="trendRef" class="chart-box"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 📅 168h 周结构 + 💎 赎回 mini 仪表 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="16">
        <el-card class="chart-card">
          <template #header><span>📅 近 12 周 168h 结构（按 L1 归因）</span></template>
          <Weekly168Chart :data="store.weeklyStructure" :height="320" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header><span>💎 赎回时间面</span></template>
          <div v-loading="redemptionLoading" class="redemption-mini">
            <template v-if="redemption">
              <div class="rm-item">
                <span class="rm-label">窗口剩余</span>
                <span class="rm-value">{{ redemption.window?.remaining_days ?? '—' }} 天</span>
              </div>
              <div class="rm-item">
                <span class="rm-label">赎回池余额</span>
                <span class="rm-value">¥{{ Math.round(redemption.pool?.balance ?? 0).toLocaleString() }}</span>
              </div>
              <div class="rm-item">
                <span class="rm-label">当前档位</span>
                <span class="rm-value">{{ tierText }}</span>
              </div>
              <el-divider />
              <div class="rm-4color">
                <div v-for="(h, k) in (redemption.time?.breakdown || {})" :key="k" class="rm-bar-row">
                  <span class="rm-bar-label" :style="{ color: attrColor(k) }">{{ k }}</span>
                  <span class="rm-bar-val">{{ Math.round(h) }}h</span>
                </div>
                <div v-if="!redemption.time?.breakdown" class="muted">暂停追踪中</div>
              </div>
            </template>
            <el-empty v-else description="暂无赎回数据" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>

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
            <li>任务自动映射到 L2 活动类型；未命中请到映射编辑器完善</li>
          </ul>
        </div>

        <div v-if="importResult" class="import-result">
          <el-alert
            :title="`导入完成：新增 ${importResult.inserted} 条，更新 ${importResult.updated} 条，跳过 ${importResult.skipped} 条` + (importResult.unclassified ? `；${importResult.unclassified} 个任务待归类` : '')"
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
import * as redemptionApi from '@/modules/redemption/api/redemptionApi'
import * as echarts from 'echarts'
import SunburstChart from '../components/SunburstChart.vue'
import Weekly168Chart from '../components/Weekly168Chart.vue'

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
const trendRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null

function attrColor(name: string | number) {
  return { 投向: '#10B981', 维持: '#6366F1', 外部: '#0EA5E9', 流失: '#F87171' }[String(name)] || '#94A3B8'
}

// ─── 导入 ───
const importVisible = ref(false)
const selectedFile = ref<File | null>(null)
const importing = ref(false)
const importResult = ref<{ inserted: number; updated: number; skipped: number; unclassified?: number } | null>(null)
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
      ElMessage.success(`导入完成：新增 ${result.inserted} 条，更新 ${result.updated} 条，跳过 ${result.skipped ?? 0} 条`)
    }
  } catch (e: any) {
    importError.value = e?.response?.data?.error || '导入失败'
  } finally {
    importing.value = false
  }
}

// ─── 赎回 mini 仪表 ───
const redemption = ref<any>(null)
const redemptionLoading = ref(false)
const tierText = computed(() => {
  const t = redemption.value?.tier
  if (!t) return '—'
  return t.current_tier || t.tier_name || t.name || '—'
})

async function loadRedemption() {
  redemptionLoading.value = true
  try {
    const res = await redemptionApi.getRedemptionStats()
    redemption.value = res.data
  } catch { redemption.value = null } finally { redemptionLoading.value = false }
}

// ─── 月度趋势（L1 堆叠）───
function initTrendChart() {
  if (!trendRef.value) return
  if (!trendChart) trendChart = echarts.init(trendRef.value)

  const data = store.trendData || []
  const allKeys = new Set<string>()
  data.forEach((d: any) => Object.keys(d).forEach((k) => { if (k !== 'period') allKeys.add(k) }))
  const keys = Array.from(allKeys).sort()
  const chartData = data.slice(-12)

  trendChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: keys, bottom: 0, type: 'scroll', icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
    grid: { left: '3%', right: '4%', bottom: '22%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: chartData.map((d: any) => d.period), axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', name: '小时' },
    series: keys.map((name) => ({
      name,
      type: 'bar' as const,
      stack: 'total',
      barWidth: '65%',
      data: chartData.map((d: any) => +(d[name] || 0).toFixed(2)),
      itemStyle: { color: attrColor(name) },
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
    store.fetchTrend(year, 'month'),
    store.fetchSunburst(year),
    store.fetchWeeklyStructure(year, 12),
    store.fetchCompleteness(year),
    loadRedemption(),
    store.fetchStats(),
  ])
  nextTick(initTrendChart)
}

window.addEventListener('resize', () => { trendChart?.resize() })

onMounted(async () => { await refreshData() })
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

  .chart-row { margin-bottom: 18px; display: flex; flex-wrap: wrap;
    .el-col { display: flex; }
    .chart-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); width: 100%; display: flex; flex-direction: column;
      :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
      :deep(.el-card__body) { flex: 1; display: flex; padding: 16px; }
      .chart-box { flex: 1; width: 100%; min-height: 280px; }
    }
  }

  .redemption-mini { padding: 4px 8px; width: 100%;
    .rm-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed #f0f0f0;
      .rm-label { font-size: 13px; color: #6B7280; }
      .rm-value { font-size: 16px; font-weight: 700; color: #1F2937; } }
    .rm-4color { margin-top: 8px;
      .rm-bar-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }
      .rm-bar-label { font-weight: 600; }
      .rm-bar-val { color: #4B5563; } }
    .muted { color: #b8bcc4; font-size: 13px; }
  }

  .import-body {
    .upload-tip { font-size: 12px; color: #909399; margin-top: 4px; }
    .import-rules { background: #f9fafb; border-radius: 8px; padding: 12px 16px; margin: 8px 0 12px;
      h4 { margin: 0 0 6px; font-size: 13px; color: #1F2937; }
      ul { margin: 0; padding-left: 18px; font-size: 12px; color: #6B7280; line-height: 1.8; } }
    .import-result { margin-top: 12px; }
  }
}
</style>
