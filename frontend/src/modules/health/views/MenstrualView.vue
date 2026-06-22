<template>
  <div class="menstrual-page">
    <div class="page-header">
      <div class="header-left">
        <h2>🩷 好朋友跟踪</h2>
        <el-tag size="small" type="danger" effect="plain">周期管理 · 趋势分析 · 预测</el-tag>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="store.fetchData">刷新</el-button>
        <el-button type="primary" size="small" @click="openForm()">+ 新增记录</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-icon" style="background:#FCE4EC;color:#E91E63">📊</div>
            <div>
              <div class="stat-value">{{ stats?.total_records ?? '--' }}</div>
              <div class="stat-label">总记录数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-icon" style="background:#F3E5F5;color:#9C27B0">📏</div>
            <div>
              <div class="stat-value">{{ stats?.avg_cycle ?? '--' }}天</div>
              <div class="stat-label">平均周期</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-icon" style="background:#E8F5E9;color:#4CAF50">📐</div>
            <div>
              <div class="stat-value">{{ stats?.avg_offset ?? '--' }}天</div>
              <div class="stat-label">平均偏移</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-body">
            <div class="stat-icon" style="background:#FFF3E0;color:#FF9800">🔮</div>
            <div>
              <div class="stat-value">{{ predictedLabel }}</div>
              <div class="stat-label">下次预测</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 周期趋势图 -->
    <el-card shadow="hover" class="chart-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📈 周期跨度趋势</span>
          <span class="card-hint">{{ stats?.min_cycle ?? '-' }}~{{ stats?.max_cycle ?? '-' }}天，共{{ stats?.total_records ?? 0 }}条</span>
        </div>
      </template>
      <div ref="chartRef" style="height:240px" />
      <div v-if="sortedRecords.length > chartSegmentSize" class="chart-nav">
        <el-button size="small" link :disabled="!canGoPrev" @click="prevSegment">← 更早</el-button>
        <el-button size="small" link :disabled="!canGoNext" @click="nextSegment">更新 →</el-button>
        <el-button v-if="currentChartStart > 0" size="small" link @click="resetToLatest">最新</el-button>
      </div>
    </el-card>

    <!-- 历史列表 -->
    <el-card shadow="hover" class="list-card">
      <template #header>
        <span class="card-title">📋 历史记录</span>
      </template>
      <el-table :data="store.records" v-loading="store.loading" stripe size="small" style="width:100%">
        <el-table-column label="开始日期" width="100" prop="start_date" />
        <el-table-column label="月份" width="70" prop="month" />
        <el-table-column label="偏移" width="60" prop="offset" />
        <el-table-column label="周期" width="60" prop="cycle_days" />
        <el-table-column label="备注" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.notes || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link @click="openForm(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        small
        style="margin-top:12px;justify-content:center"
        @current-change="loadRecords"
      />
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="editingId ? '编辑记录' : '新增记录'" width="420px" @closed="handleFormClose">
      <el-form :model="form" label-width="80px" size="small">
        <el-form-item label="开始日期" required>
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
        <el-form-item label="偏移量">
          <el-input-number v-model="form.offset" :min="-30" :max="60" style="width:100%" />
        </el-form-item>
        <el-form-item label="周期跨度">
          <el-input-number v-model="form.cycle_days" :min="0" :max="90" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="饮食、压力、运动等影响因素" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="formVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  getMenstrualRecords,
  getMenstrualStats,
  getMenstrualTrend,
  createMenstrualRecord,
  updateMenstrualRecord,
  deleteMenstrualRecord,
} from '../api/healthApi'
import type { MenstrualRecord, MenstrualStats, MenstrualTrendItem } from '../types/healthTypes'

const store = reactive({
  records: [] as MenstrualRecord[],
  loading: false,
  async fetchData() {
    this.loading = true
    try {
      const [statsRes, trendRes] = await Promise.all([
        getMenstrualStats(),
        getMenstrualTrend(),
      ])
      stats.value = statsRes.data as MenstrualStats
      trendData.value = (trendRes.data || []) as MenstrualTrendItem[]
      currentChartStart.value = 0
      await loadRecords()
    } catch {
      this.records = []
      stats.value = null
      trendData.value = []
    } finally {
      this.loading = false
    }
  },
})

async function loadRecords() {
  try {
    const res = await getMenstrualRecords({ page: currentPage.value, page_size: pageSize.value })
    store.records = (res.data?.results || []) as MenstrualRecord[]
    total.value = res.data?.count ?? 0
  } catch {
    store.records = []
  }
}

const stats = ref<MenstrualStats | null>(null)
const trendData = ref<MenstrualTrendItem[]>([])
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// ─── 图表分段 ───
const chartSegmentSize = 12
const currentChartStart = ref(0)
const sortedRecords = computed(() =>
  [...trendData.value].sort((a, b) =>
    new Date(a.date).getTime() - new Date(b.date).getTime()
  )
)
const segmentRecords = computed(() => {
  const total = sortedRecords.value.length
  const end = total - currentChartStart.value
  const start = Math.max(0, end - chartSegmentSize)
  return sortedRecords.value.slice(start, end)
})
const canGoPrev = computed(() =>
  currentChartStart.value + chartSegmentSize < sortedRecords.value.length
)
const canGoNext = computed(() => currentChartStart.value > 0)
function prevSegment() { currentChartStart.value += chartSegmentSize }
function nextSegment() { currentChartStart.value = Math.max(0, currentChartStart.value - chartSegmentSize) }
function resetToLatest() { currentChartStart.value = 0 }

const predictedLabel = computed(() => {
  if (!stats.value?.predicted_next) return '暂无数据'
  const d = new Date(stats.value.predicted_next)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.ceil((d.getTime() - today.getTime()) / 86400000)
  if (diff === 0) return '今天'
  if (diff === 1) return '明天'
  if (diff === 2) return '后天'
  return `${d.getMonth() + 1}/${d.getDate()}`
})

function renderChart() {
  if (!chartRef.value || !segmentRecords.value.length) return
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 16, bottom: 32 },
    xAxis: {
      type: 'category',
      data: segmentRecords.value.map(d => d.date.slice(5)),
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: { type: 'value', name: '周期(天)', min: 0 },
    series: [{
      type: 'line',
      data: segmentRecords.value.map(d => d.cycle_days),
      smooth: true,
      areaStyle: { opacity: 0.15 },
      lineStyle: { color: '#E91E63', width: 2 },
      itemStyle: { color: '#E91E63' },
      markLine: {
        silent: true,
        data: [{ yAxis: stats.value?.avg_cycle ?? 30 }],
        label: { formatter: `平均 {c}天`, fontSize: 11 },
        lineStyle: { color: '#9C27B0', type: 'dashed' },
      },
    }],
  })
}

// ─── 表单 ───

watch(segmentRecords, () => nextTick(renderChart), { deep: true })

const formVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = reactive({
  start_date: '',
  offset: 0,
  cycle_days: 30,
  notes: '',
})

function openForm(row?: MenstrualRecord) {
  if (row) {
    editingId.value = row.id
    form.start_date = row.start_date
    form.offset = row.offset
    form.cycle_days = row.cycle_days
    form.notes = row.notes
  } else {
    editingId.value = null
    form.start_date = ''
    form.offset = 0
    form.cycle_days = store.records.length ? 30 : 30
    form.notes = ''
  }
  formVisible.value = true
}

watch(() => form.start_date, (date) => {
  if (!date || editingId.value) return
  const sorted = [...store.records].sort(
    (a, b) => new Date(b.start_date).getTime() - new Date(a.start_date).getTime()
  )
  const last = sorted[0]
  if (!last) return
  const diff = Math.round(
    (new Date(date).getTime() - new Date(last.start_date).getTime()) / 86400000
  )
  if (diff > 0) {
    form.cycle_days = diff
    form.offset = diff - (last.cycle_days || 30)
  }
})

function handleFormClose() {
  form.start_date = ''
  form.offset = 0
  form.cycle_days = 30
  form.notes = ''
  editingId.value = null
}

async function handleSave() {
  if (!form.start_date) {
    ElMessage.warning('请选择开始日期')
    return
  }
  saving.value = true
  const d = new Date(form.start_date)
  const payload = {
    ...form,
    year: d.getFullYear(),
    month: `${d.getMonth() + 1}月`,
    user_id: 1,
  }
  try {
    if (editingId.value) {
      await updateMenstrualRecord(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await createMenstrualRecord(payload)
      ElMessage.success('已添加')
    }
    formVisible.value = false
    loadRecords()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: MenstrualRecord) {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.start_date} 的记录？`, '确认删除', { type: 'warning' })
    await deleteMenstrualRecord(row.id)
    ElMessage.success('已删除')
    loadRecords()
  } catch { /* cancelled */ }
}

onMounted(() => {
  store.fetchData()
})
</script>

<style scoped>
.menstrual-page { padding: 20px; background: var(--el-bg-color-page); min-height: 100vh; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 18px; font-weight: 600; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.stats-row { margin-bottom: 16px; }
.stat-card { border: none; border-radius: 10px; }
.stat-card :deep(.el-card__body) { padding: 16px; }
.stat-body { display: flex; align-items: center; gap: 12px; }
.stat-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
.stat-value { font-size: 20px; font-weight: 700; color: var(--el-text-color-primary); line-height: 1.2; }
.stat-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.chart-card { border: none; border-radius: 10px; margin-bottom: 16px; }
.chart-card :deep(.el-card__body) { padding: 12px 16px 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-title { font-size: 14px; font-weight: 600; }
.card-hint { font-size: 11px; color: var(--el-text-color-secondary); }
.list-card { border: none; border-radius: 10px; }
.list-card :deep(.el-card__body) { padding: 12px 16px 16px; }
</style>
