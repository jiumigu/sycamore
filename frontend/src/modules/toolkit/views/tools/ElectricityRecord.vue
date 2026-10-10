<template>
  <div class="electricity-record">
    <!-- 返回按钮由 ToolDetail 统一提供，勿在此重复添加 -->
    <div class="page-head">
      <div class="head-text">
        <h2 class="page-title">⚡ 用电记录</h2>
        <p class="subtitle">记下电表读数，自动算出间隔用电、日均用电和本月累计</p>
      </div>
      <el-button
        class="monthly-entry"
        @click="$router.push('/toolkit/electricity-record/monthly')"
      >
        <el-icon><Calendar /></el-icon> 月度用电
      </el-button>
    </div>

    <!-- 统计卡：数据源为 overview，与下方分页解耦（翻页不会改这里） -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-label">最新读数</div>
        <div class="stat-value">{{ overview.latest ? fmt1(overview.latest.meter_reading) : '—' }}<span class="unit">度</span></div>
        <div class="stat-foot">{{ overview.latest ? overview.latest.record_date : '暂无记录' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">本月累计</div>
        <div class="stat-value highlight">{{ overview.latest && overview.latest.month_usage != null ? fmt1(overview.latest.month_usage) : '—' }}<span class="unit">度</span></div>
        <div class="stat-foot">最新读数 − 月初基准</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">日均用电</div>
        <div class="stat-value">{{ overview.latest?.daily_avg != null ? fmt2(overview.latest.daily_avg) : '—' }}<span class="unit">度/天</span></div>
        <div class="stat-foot">最近一次间隔</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">记录次数</div>
        <div class="stat-value">{{ overview.total_records }}<span class="unit">次</span></div>
        <div class="stat-foot">全部历史</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">月度估算</div>
        <div class="stat-value highlight">{{ pert.ready ? fmt1(pert.expected) : '—' }}<span class="unit">度</span></div>
        <div class="stat-foot">
          {{ pert.ready ? `PERT 期望值 · 样本 ${pert.samples} 个完整月` : `已积累 ${pert.samples}/${pert.required} 个月` }}
        </div>
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

    <!-- 用电趋势 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📈 用电趋势</span>
          <el-tag size="small" type="info">当前页 {{ history.length }} 条</el-tag>
        </div>
      </template>
      <div v-if="history.length === 0" class="chart-empty">暂无数据，先添加一条记录</div>
      <div v-else ref="chartRef" class="trend-chart" />
    </el-card>

    <!-- 历史记录 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📋 历史记录</span>
          <el-tag size="small">{{ total }} 条</el-tag>
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
          <template #default="{ row }">{{ row.month_usage != null ? fmt1(row.month_usage) + ' 度' : '—' }}</template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="danger" @click.stop="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && history.length === 0" description="暂无用电记录" />

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        small
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="fetchHistory"
        @size-change="onSizeChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Calendar } from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  getElectricityRecords,
  createElectricityRecord,
  deleteElectricityRecord,
  getElectricityOverview,
} from '../../api/toolkitApi'
import type {
  ElectricityRecord,
  ElectricityOverview,
  ElectricityPert,
} from '../../types/toolkitTypes'

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const EMPTY_PERT: ElectricityPert = {
  samples: 0, required: 3, ready: false,
  optimistic: null, most_likely: null, pessimistic: null,
  expected: null, sigma: null, low: null, high: null,
  mean: null, issues: [],
}

const form = reactive({
  record_date: '',
  meter_reading: undefined as number | undefined,
  notes: '',
})

const saving = ref(false)
const loading = ref(false)
const history = ref<ElectricityRecord[]>([])
const overview = ref<ElectricityOverview>({
  months: [], pert: { ...EMPTY_PERT }, latest: null, total_records: 0,
})

// 分页（历史表用；统计卡由 overview 驱动，不受翻页影响）
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const pert = computed(() => overview.value.pert)

/** null / 空串一律显示「—」，**不要**被 Number(null)===0 骗成 0.0 */
function fmt1(v: number | string | null | undefined): string {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

function fmt2(v: number | string | null | undefined): string {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function fetchHistory() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    const res = await getElectricityRecords(params)
    const data = res.data
    // 后端走 DRF 全局分页 ⇒ {count, results}；防御一次裸数组的情形
    if (Array.isArray(data)) {
      history.value = data as ElectricityRecord[]
      total.value = data.length
    } else {
      history.value = (data?.results || []) as ElectricityRecord[]
      total.value = data?.count ?? 0
    }
  } catch {
    history.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function fetchOverview() {
  try {
    const res = await getElectricityOverview({ months: 12 })
    const data = res.data as ElectricityOverview | undefined
    if (data && Array.isArray(data.months)) overview.value = data
  } catch {
    /* 保留上一次的值，别把卡片清空 */
  }
}

async function refreshAll() {
  await Promise.all([fetchHistory(), fetchOverview()])
  await nextTick()
  updateChart()
}

function onSizeChange() {
  page.value = 1
  fetchHistory()
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
    await refreshAll()
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
    await refreshAll()
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
  }, true)
}

onMounted(async () => {
  await refreshAll()
  nextTick(() => {
    if (chartRef.value) initChart()
  })
})

onBeforeUnmount(() => {
  chart?.dispose()
  chart = null
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

  /* 标题 + 右侧「月度用电」入口按钮（月度卡与估算详情已移到独立子页面） */
  .page-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;

    .head-text { min-width: 0; }

    .page-title {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      color: #1F2937;
    }

    .subtitle {
      margin: 4px 0 0;
      font-size: 13px;
      color: #6B7280;
    }

    .monthly-entry { flex: none; }
  }

  /* 5 张统计卡一行：最新读数 / 本月累计 / 日均用电 / 记录次数 / 月度估算 */
  .stat-cards {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 16px;

    @media (max-width: 1200px) {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

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

      .stat-foot {
        margin-top: 6px;
        font-size: 12px;
        color: #9CA3AF;
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

  /* ── 图表 ── */

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
