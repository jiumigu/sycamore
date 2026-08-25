<template>
  <div class="electricity-record">
    <!-- 返回按钮由 ToolDetail 统一提供，勿在此重复添加 -->
    <h2 class="page-title">⚡ 用电记录</h2>
    <p class="subtitle">记下电表读数，自动算出间隔用电、日均用电和本月累计</p>

    <!-- 统计卡 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-label">最新读数</div>
        <div class="stat-value">{{ latest ? fmt1(latest.meter_reading) : '—' }}<span class="unit">度</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">本月累计</div>
        <div class="stat-value highlight">{{ latest ? fmt1(latest.month_usage) : '—' }}<span class="unit">度</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">日均用电</div>
        <div class="stat-value">{{ latest?.daily_avg != null ? fmt2(latest.daily_avg) : '—' }}<span class="unit">度/天</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">记录次数</div>
        <div class="stat-value">{{ history.length }}<span class="unit">次</span></div>
      </div>
    </div>

    <!-- 新增记录 -->
    <el-card class="section-card">
      <template #header><span class="card-title">📝 新增记录</span></template>
      <el-form label-width="90px" class="add-form">
        <el-form-item label="记录日期">
          <el-date-picker
            v-model="form.record_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="电表读数">
          <el-input-number v-model="form.meter_reading" :min="0" :precision="1" :controls="false" style="width: 200px" />
          <span class="field-unit">度</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" placeholder="选填" style="width: 320px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">记录</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 趋势图 -->
    <el-card class="section-card">
      <template #header><span class="card-title">📈 用电趋势</span></template>
      <div v-if="history.length === 0" class="chart-empty">暂无数据，先添加一条记录</div>
      <div v-else ref="chartRef" class="trend-chart" />
    </el-card>

    <!-- 历史记录 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📋 历史记录</span>
          <el-tag size="small">{{ history.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="history" v-loading="loading" stripe size="small" style="width: 100%">
        <el-table-column prop="record_date" label="日期" width="110" />
        <el-table-column label="电表读数" width="110" align="right">
          <template #default="{ row }">{{ fmt1(row.meter_reading) }} 度</template>
        </el-table-column>
        <el-table-column label="间隔用电" width="110" align="right">
          <template #default="{ row }">{{ row.interval_usage != null ? fmt1(row.interval_usage) + ' 度' : '—' }}</template>
        </el-table-column>
        <el-table-column label="间隔天数" width="90" align="right">
          <template #default="{ row }">{{ row.interval_days != null ? row.interval_days + ' 天' : '—' }}</template>
        </el-table-column>
        <el-table-column label="日均用电" width="110" align="right">
          <template #default="{ row }">{{ row.daily_avg != null ? fmt2(row.daily_avg) + ' 度' : '—' }}</template>
        </el-table-column>
        <el-table-column label="本月累计" width="110" align="right">
          <template #default="{ row }">{{ fmt1(row.month_usage) }} 度</template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && history.length === 0" description="暂无用电记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getElectricityRecords, createElectricityRecord, deleteElectricityRecord } from '../../api/toolkitApi'
import type { ElectricityRecord } from '../../types/toolkitTypes'

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const form = reactive({
  record_date: '',
  meter_reading: undefined as number | undefined,
  notes: '',
})

const saving = ref(false)
const loading = ref(false)
const history = ref<ElectricityRecord[]>([])
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

// 列表按 record_date 倒序，latest 即最新记录
const latest = computed(() => history.value[0] || null)

function fmt1(v: number | string | null | undefined): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

function fmt2(v: number | string | null | undefined): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function fetchHistory() {
  loading.value = true
  try {
    const res = await getElectricityRecords({ page_size: 100 })
    history.value = (res.data?.results || []) as ElectricityRecord[]
  } catch {
    history.value = []
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!form.record_date) {
    ElMessage.warning('请选择记录日期')
    return
  }
  if (form.meter_reading == null) {
    ElMessage.warning('请输入电表读数')
    return
  }
  saving.value = true
  try {
    await createElectricityRecord({
      record_date: form.record_date,
      meter_reading: form.meter_reading,
      notes: form.notes,
    })
    ElMessage.success('已记录，自动计算间隔/日均/本月累计')
    form.notes = ''
    form.meter_reading = undefined
    await fetchHistory()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这条记录？删除后将自动重算后续记录。', '确认删除', { type: 'warning' })
    await deleteElectricityRecord(id)
    ElMessage.success('已删除，后续记录已自动重算')
    await fetchHistory()
  } catch { /* cancelled */ }
}

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
}

function updateChart() {
  if (!chart) return
  const asc = [...history.value].reverse()
  const dates = asc.map(r => r.record_date)
  const readings = asc.map(r => Number(r.meter_reading))
  const intervals = asc.map(r => (r.interval_usage != null ? Number(r.interval_usage) : 0))

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['电表读数', '间隔用电'], bottom: 0 },
    grid: { left: 60, right: 60, bottom: 40, top: 20 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
    yAxis: [
      { type: 'value', name: '读数(度)', position: 'left', axisLabel: { fontSize: 11 } },
      { type: 'value', name: '间隔(度)', position: 'right', axisLabel: { fontSize: 11 } },
    ],
    series: [
      {
        name: '电表读数',
        type: 'line',
        yAxisIndex: 0,
        data: readings,
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
        symbol: 'circle', symbolSize: 5,
      },
      {
        name: '间隔用电',
        type: 'bar',
        yAxisIndex: 1,
        data: intervals,
        itemStyle: { color: '#67c23a' },
        barMaxWidth: 24,
      },
    ],
  })
}

onMounted(async () => {
  await fetchHistory()
  nextTick(() => { if (chartRef.value) initChart() })
})

watch(history, async () => {
  await nextTick()
  // 空状态 → 有数据时图表容器晚于 onMounted 挂载，此时需首次 init
  if (chartRef.value && !chart) {
    initChart()
  } else {
    updateChart()
  }
}, { deep: true })
</script>

<style scoped lang="scss">
.electricity-record {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;

  .page-title {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    color: #1F2937;
  }

  .subtitle {
    margin: -8px 0 0;
    font-size: 13px;
    color: #6B7280;
  }

  .stat-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;

    .stat-card {
      background: #fff;
      border-radius: 10px;
      padding: 16px 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      border: 1px solid #f0f0f0;

      .stat-label {
        font-size: 13px;
        color: #6B7280;
        margin-bottom: 8px;
      }

      .stat-value {
        font-size: 26px;
        font-weight: 700;
        color: #1F2937;
        line-height: 1.1;

        .unit {
          font-size: 12px;
          font-weight: 400;
          color: #9CA3AF;
          margin-left: 4px;
        }

        &.highlight { color: var(--el-color-primary); }
      }
    }
  }

  .card-title { font-size: 14px; font-weight: 600; }
  .card-header { display: flex; align-items: center; gap: 10px; }

  .section-card :deep(.el-card__body) { padding: 16px 20px; }

  .add-form {
    .field-unit {
      margin-left: 8px;
      font-size: 13px;
      color: #6B7280;
    }
  }

  .trend-chart {
    width: 100%;
    height: 280px;
  }

  .chart-empty {
    padding: 40px;
    text-align: center;
    color: #9CA3AF;
  }
}
</style>
