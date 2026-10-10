<template>
  <div class="electricity-monthly">
    <div class="head-bar">
      <el-button text @click="$router.push('/toolkit/electricity-record')">
        <el-icon><ArrowLeft /></el-icon> 返回用电记录
      </el-button>
    </div>

    <h2 class="page-title">📅 月度用电</h2>
    <p class="subtitle">按月汇总的用电量：柱状图 + 最近 12 个月明细；点某一行可查看该月明细记录</p>

    <!-- 月度用电 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📅 月度用电</span>
          <el-tag size="small" type="info">最近 12 个月</el-tag>
          <el-button v-if="selectedMonth" size="small" link type="primary" @click="clearMonthFilter">
            清除筛选（{{ selectedMonth }}）
          </el-button>
        </div>
      </template>

      <div v-if="overview.months.length === 0" class="chart-empty">暂无数据，先回上一页添加一条用电记录</div>
      <template v-else>
        <div ref="monthChartRef" class="month-chart" />
        <el-table
          :data="overview.months"
          size="small"
          style="width: 100%"
          highlight-current-row
          :row-class-name="monthRowClass"
          @row-click="onMonthClick"
        >
          <el-table-column prop="month" label="月份" width="100" />
          <el-table-column label="用电量" width="110" align="right">
            <template #default="{ row }">{{ row.usage != null ? fmt1(row.usage) + ' 度' : '—' }}</template>
          </el-table-column>
          <el-table-column label="覆盖天数" width="100" align="right">
            <template #default="{ row }">{{ row.days != null ? row.days + ' 天' : '—' }}</template>
          </el-table-column>
          <el-table-column label="日均" width="100" align="right">
            <template #default="{ row }">{{ row.daily_avg != null ? fmt2(row.daily_avg) + ' 度' : '—' }}</template>
          </el-table-column>
          <el-table-column label="记录数" width="90" align="right">
            <template #default="{ row }">{{ row.records }}</template>
          </el-table-column>
          <el-table-column label="状态" min-width="120">
            <template #default="{ row }">
              <el-tag v-if="row.partial" size="small" type="warning">进行中</el-tag>
              <el-tag v-else-if="row.in_pert_sample" size="small" type="success">已入样本</el-tag>
              <span v-else>—</span>
            </template>
          </el-table-column>
        </el-table>
        <p class="table-hint">
          用电量 = 该月最后一条读数 − 上月最后一条读数。「覆盖天数」是这两条读数之间的实际天数，
          读数不一定是整月 —— 跨月读数间隔越短，这个数越贴近整月用量。点某一行可展开该月明细记录。
        </p>
      </template>
    </el-card>

    <!-- 选中月份的明细记录 -->
    <el-card v-if="selectedMonth" class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📋 {{ selectedMonth }} 明细记录</span>
          <el-tag size="small">{{ monthTotal }} 条</el-tag>
        </div>
      </template>
      <el-table :data="monthRecords" v-loading="monthLoading" stripe size="small" style="width: 100%">
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
      </el-table>
      <el-empty v-if="!monthLoading && monthRecords.length === 0" description="该月没有记录" />
    </el-card>

    <!-- 月度估算（PERT） -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">🔮 月度估算</span>
          <el-tag size="small" :type="pert.ready ? 'success' : 'info'">
            {{ pert.ready ? `基于最近 ${pert.samples} 个完整月` : `已积累 ${pert.samples}/${pert.required} 个月` }}
          </el-tag>
        </div>
      </template>

      <div v-if="pert.ready" class="pert-body">
        <div class="pert-main">
          <div class="pert-main-label">期望月度用电量</div>
          <div class="pert-main-value">{{ fmt1(pert.expected) }}<span class="unit">度</span></div>
          <div class="pert-main-sub">
            ±1σ 区间 {{ fmt1(pert.low) }} ~ {{ fmt1(pert.high) }} 度
          </div>
          <div class="pert-formula">
            E =（O + 4M + P）÷ 6 ＝ {{ fmt1(pert.expected) }}
          </div>
        </div>
        <div class="pert-points">
          <div class="point">
            <div class="p-label">乐观 O</div>
            <div class="p-value">{{ fmt1(pert.optimistic) }}<span class="p-unit">度</span></div>
          </div>
          <div class="point">
            <div class="p-label">最可能 M</div>
            <div class="p-value">{{ fmt1(pert.most_likely) }}<span class="p-unit">度</span></div>
          </div>
          <div class="point">
            <div class="p-label">悲观 P</div>
            <div class="p-value">{{ fmt1(pert.pessimistic) }}<span class="p-unit">度</span></div>
          </div>
          <div class="point">
            <div class="p-label">标准差 σ</div>
            <div class="p-value">{{ fmt2(pert.sigma) }}<span class="p-unit">度</span></div>
          </div>
        </div>
      </div>

      <div v-else class="pert-progress">
        <el-progress
          :percentage="pertProgress"
          :stroke-width="10"
          :show-text="false"
          :color="pertProgress >= 100 ? '#67c23a' : '#409eff'"
        />
        <p class="pert-progress-text">
          还差 <b>{{ Math.max(0, pert.required - pert.samples) }}</b> 个完整月才能估算（需 {{ pert.required }} 个）
        </p>
        <p v-if="pert.mean != null" class="pert-mean-ref">
          当前样本均值 <b>{{ fmt1(pert.mean) }} 度</b>
          <span class="muted">（仅供参考，<b>不是</b> PERT 估算）</span>
        </p>
      </div>

      <div v-if="pert.issues.length" class="pert-issues">
        <div v-for="(s, i) in pert.issues" :key="i" class="issue-line">{{ s }}</div>
      </div>

      <p class="pert-footnote">
        PERT 给的是<b>期望值</b>（O/M/P 加权平均），不是「最可能值」（那是 M）。
        样本只取<b>已结束</b>的完整月 —— 进行中的当月不计入。
      </p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getElectricityRecords, getElectricityOverview } from '../../api/toolkitApi'
import type {
  ElectricityRecord,
  ElectricityOverview,
  ElectricityMonthUsage,
  ElectricityPert,
} from '../../types/toolkitTypes'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const EMPTY_PERT: ElectricityPert = {
  samples: 0, required: 3, ready: false,
  optimistic: null, most_likely: null, pessimistic: null,
  expected: null, sigma: null, low: null, high: null,
  mean: null, issues: [],
}

const overview = ref<ElectricityOverview>({
  months: [], pert: { ...EMPTY_PERT }, latest: null, total_records: 0,
})

const selectedMonth = ref('')
const monthRecords = ref<ElectricityRecord[]>([])
const monthTotal = ref(0)
const monthLoading = ref(false)

const monthChartRef = ref<HTMLElement | null>(null)
let monthChart: echarts.ECharts | null = null

const pert = computed(() => overview.value.pert)

const pertProgress = computed(() => {
  const p = overview.value.pert
  if (!p.required) return 0
  return Math.min(100, Math.round((p.samples / p.required) * 100))
})

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

async function fetchOverview() {
  try {
    const res = await getElectricityOverview({ months: 12 })
    const data = res.data as ElectricityOverview | undefined
    if (data && Array.isArray(data.months)) overview.value = data
  } catch {
    /* 保留上一次的值，别把卡片清空 */
  }
}

async function fetchMonthRecords() {
  if (!selectedMonth.value) {
    monthRecords.value = []
    monthTotal.value = 0
    return
  }
  monthLoading.value = true
  try {
    const res = await getElectricityRecords({ month: selectedMonth.value, page: 1, page_size: 200 })
    const data = res.data
    // DRF 全局分页 ⇒ {count, results}；防御一次裸数组的情形
    if (Array.isArray(data)) {
      monthRecords.value = data as ElectricityRecord[]
      monthTotal.value = data.length
    } else {
      monthRecords.value = (data?.results || []) as ElectricityRecord[]
      monthTotal.value = data?.count ?? 0
    }
  } catch {
    monthRecords.value = []
    monthTotal.value = 0
  } finally {
    monthLoading.value = false
  }
}

function onMonthClick(row: ElectricityMonthUsage) {
  if (!row.records) {
    ElMessage.info(`${row.month} 没有记录`)
    return
  }
  selectedMonth.value = row.month
  fetchMonthRecords()
}

function clearMonthFilter() {
  selectedMonth.value = ''
  fetchMonthRecords()
}

function monthRowClass({ row }: { row: ElectricityMonthUsage }) {
  return row.records === 0 ? 'month-row-empty' : 'month-row-clickable'
}

function initMonthChart() {
  if (!monthChartRef.value) return
  monthChart = echarts.init(monthChartRef.value)
  updateMonthChart()
}

function updateMonthChart() {
  if (!monthChart) return
  const rows = overview.value.months
  if (rows.length === 0) {
    monthChart.clear()
    return
  }

  monthChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (ps: any) => {
        const r = rows[ps[0].dataIndex]
        if (!r || r.usage == null) return `${r?.month ?? ''}<br/>无记录`
        const lines = [
          `${r.month}`,
          `用电量 ${fmt1(r.usage)} 度`,
          `覆盖 ${r.days} 天（${r.base_date} → ${r.end_date}）`,
          `${r.records} 条记录`,
        ]
        if (r.base_source === 'own_first') lines.push('基准：本月初条读数（无上月数据）')
        if (r.partial) lines.push('⚠ 本月尚未结束')
        return lines.join('<br/>')
      },
    },
    grid: { left: 54, right: 20, bottom: 30, top: 26 },
    xAxis: {
      type: 'category',
      data: rows.map(r => `${Number(r.month.slice(5))}月`),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', name: '度', axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar',
      name: '月度用电',
      data: rows.map(r => r.usage),
      barMaxWidth: 28,
      label: {
        show: true,
        position: 'top',
        fontSize: 10,
        formatter: (p: any) => (p.value == null ? '' : fmt1(p.value)),
      },
      itemStyle: {
        color: (p: any) => {
          const r = rows[p.dataIndex]
          if (r.usage == null) return '#E5E7EB'
          if (r.partial) return '#E6A23C'
          return '#409eff'
        },
      },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#F56C6C', width: 1 },
        label: { formatter: '期望 {c}', fontSize: 10, position: 'insideEndTop' },
        data: overview.value.pert.ready && overview.value.pert.expected != null
          ? [{ yAxis: overview.value.pert.expected }]
          : [],
      },
    }],
  }, true)
}

onMounted(async () => {
  await fetchOverview()
  await nextTick()
  initMonthChart()
  updateMonthChart()
})

onBeforeUnmount(() => {
  monthChart?.dispose()
  monthChart = null
})

// 空状态 → 有数据时图表容器晚于 onMounted 挂载，此时需首次 init
watch(() => overview.value.months.length, async () => {
  await nextTick()
  if (monthChartRef.value && !monthChart) {
    initMonthChart()
  } else {
    updateMonthChart()
  }
})
</script>

<style scoped lang="scss">
.electricity-monthly {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;

  .head-bar {
    margin-bottom: -8px;
  }

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

  .card-title { font-size: 14px; font-weight: 600; }
  .card-header { display: flex; align-items: center; gap: 10px; }

  .section-card :deep(.el-card__body) { padding: 16px 20px; }

  /* ── PERT 卡片 ── */
  .pert-body {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.6fr);
    gap: 24px;
    align-items: center;

    .pert-main {
      .pert-main-label {
        font-size: 13px;
        color: #6B7280;
        margin-bottom: 6px;
      }
      .pert-main-value {
        font-size: 34px;
        font-weight: 700;
        color: var(--el-color-primary);
        line-height: 1.1;

        .unit {
          font-size: 13px;
          font-weight: 400;
          color: #9CA3AF;
          margin-left: 6px;
        }
      }
      .pert-main-sub {
        margin-top: 6px;
        font-size: 13px;
        color: #6B7280;
      }
      .pert-formula {
        margin-top: 4px;
        font-size: 12px;
        color: #9CA3AF;
      }
    }

    .pert-points {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;

      .point {
        background: #F9FAFB;
        border-radius: 8px;
        padding: 10px 12px;

        .p-label {
          font-size: 12px;
          color: #6B7280;
          margin-bottom: 4px;
        }
        .p-value {
          font-size: 18px;
          font-weight: 600;
          color: #1F2937;

          .p-unit {
            font-size: 11px;
            font-weight: 400;
            color: #9CA3AF;
            margin-left: 3px;
          }
        }
      }
    }
  }

  .pert-progress {
    padding: 4px 0 0;

    .pert-progress-text {
      margin: 12px 0 0;
      font-size: 13px;
      color: #6B7280;

      b { color: #1F2937; font-size: 15px; }
    }

    .pert-mean-ref {
      margin: 6px 0 0;
      font-size: 13px;
      color: #6B7280;

      b { color: #1F2937; }
      .muted { color: #9CA3AF; }
    }
  }

  .pert-issues {
    margin-top: 12px;
    padding: 10px 12px;
    background: #FDF6EC;
    border-radius: 8px;

    .issue-line {
      font-size: 12px;
      color: #B88230;
      line-height: 1.7;
    }
  }

  .pert-footnote {
    margin: 12px 0 0;
    font-size: 12px;
    color: #9CA3AF;
    line-height: 1.7;

    b { color: #6B7280; }
  }

  /* ── 图表 ── */
  .month-chart {
    width: 100%;
    height: 240px;
  }

  .chart-empty {
    padding: 40px;
    text-align: center;
    color: #9CA3AF;
  }

  .table-hint {
    margin: 12px 0 0;
    font-size: 12px;
    color: #9CA3AF;
    line-height: 1.7;
  }

  :deep(.month-row-empty) {
    color: #C0C4CC;
  }

  :deep(.month-row-clickable) {
    cursor: pointer;
  }
}
</style>
