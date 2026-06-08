<template>
  <div class="health-dashboard">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">🏃 生命步数目标</h1>
        <el-tag type="success" class="module-tag">身心健康</el-tag>
      </div>
      <div class="header-actions">
        <el-select v-model="filterYear" size="default" style="width: 110px" placeholder="全部年份" clearable @change="refreshData">
          <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 添加记录
        </el-button>
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- 超大进度条 -->
    <el-card class="section-card progress-card">
      <div class="progress-header">
        <div class="progress-title">目标：在有限生命中走完 <strong>10,000 万步</strong>（1亿步）</div>
        <div class="progress-subtitle" v-if="store.summary">
          已完成 <strong>{{ formatNumber(store.summary.total_steps) }}</strong> 步 /
          <strong>{{ formatNumber(store.summary.target_steps) }}</strong> 步
          （{{ store.summary.progress_percent }}%）
        </div>
      </div>
      <div class="progress-bar-wrap">
        <div class="progress-bar" v-if="store.summary">
          <div class="progress-fill" :style="{ width: Math.min(store.summary.progress_percent, 100) + '%' }">
            <div class="progress-glow"></div>
          </div>
          <div class="progress-milestone-dots">
            <div
              v-for="i in 50"
              :key="i"
              class="milestone-dot"
              :class="{
                completed: store.summary && i <= store.summary.completed_milestones,
                current: store.summary && i === store.summary.completed_milestones + 1,
              }"
              :style="{ left: (i / 50 * 100) + '%' }"
              :title="`第${i}个里程碑 (${formatNumber((i-1)*2)}万 - ${formatNumber(i*2)}万步)`"
            ></div>
          </div>
        </div>
      </div>
      <div class="progress-info" v-if="store.summary && store.summary.current_milestone">
        当前里程碑：第{{ store.summary.current_milestone.number }}个
        （{{ formatNumber(store.summary.current_milestone.start / 10000) }}万 -
        {{ formatNumber(store.summary.current_milestone.end / 10000) }}万步）
        · 还需 <strong>{{ formatNumber(store.summary.next_milestone_distance) }}</strong> 步达成
        · 里程碑内进度 {{ store.summary.current_milestone.progress_in_milestone }}%
      </div>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6" v-for="card in statCards" :key="card.key">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: card.bg }">
              <el-icon :color="card.color" :size="20"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 里程碑地图 + 年度步数对比 -->
    <el-row :gutter="16" class="chart-row equal-height-row">
      <el-col :span="12">
        <el-card class="section-card equal-height-card">
          <template #header>
            <div class="section-header">
              <span>🎯 里程碑地图</span>
              <router-link to="/health/milestones">
                <el-button size="small" text>查看全部 →</el-button>
              </router-link>
            </div>
          </template>
          <div class="milestone-grid">
            <div
              v-for="m in milestonePreview"
              :key="m.number"
              class="milestone-cell"
              :class="{
                completed: m.is_completed,
                current: m.is_current,
              }"
              :title="`第${m.number}个里程碑 (${formatNumber(m.start/10000)}万-${formatNumber(m.end/10000)}万步)`"
            >
              <div class="cell-number">{{ m.number }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="section-card equal-height-card">
          <template #header><span>📊 年度步数对比</span></template>
          <div ref="yearlyChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 记录列表 -->
    <el-card class="section-card">
      <template #header>
        <div class="section-header">
          <span>📝 运动记录</span>
        </div>
      </template>
      <el-table v-loading="store.loading" :data="displayRecords" style="width: 100%" size="small" stripe>
        <el-table-column label="日期" width="110">
          <template #default="{ row }">{{ formatTime(row.time) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="80">
          <template #default="{ row }">{{ row.htype_label }}</template>
        </el-table-column>
        <el-table-column label="原始量" width="80" prop="steps" />
        <el-table-column label="折算步数" width="110" prop="total" />
        <el-table-column label="备注" min-width="160" prop="remark" show-overflow-tooltip />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)"><el-icon><Edit /></el-icon></el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)"><el-icon><Delete /></el-icon></el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="store.totalCount > pageSize"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="store.totalCount"
        layout="prev, pager, next"
        small
        class="pagination"
        @current-change="handlePageChange"
      />
    </el-card>

    <!-- 添加/编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="isEdit ? '编辑运动记录' : '🏃 添加运动记录'" width="480px" @close="resetForm">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="80px">
        <el-form-item label="运动类型" prop="htype">
          <el-select v-model="formData.htype" placeholder="选择类型" style="width:100%">
            <el-option v-for="t in HTYPE_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="运动量" prop="steps">
          <el-input-number v-model="formData.steps" :min="0" :max="100000" style="width:100%"
            :placeholder="formData.htype === 1 ? '输入步数' : formData.htype === 2 ? '输入跳绳个数' : formData.htype === 3 ? '输入跑步公里数(可小数)' : '输入骑行公里数(可小数)'" />
        </el-form-item>

        <el-form-item v-if="formData.htype !== 1" label="说明">
          <div class="convert-hint">
            {{
              formData.htype === 2 ? '1个跳绳 ≈ 0.5步 · 系统自动转换' :
              formData.htype === 3 ? '1公里跑步 ≈ 1300步 · 系统自动转换' :
              formData.htype === 4 ? '1公里骑行 ≈ 400步 · 系统自动转换' : ''
            }}
          </div>
        </el-form-item>

        <el-form-item label="日期" prop="time">
          <el-date-picker v-model="formData.time" type="datetime" placeholder="选择日期"
            format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" :rows="2" maxlength="255" placeholder="可选备注..." />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Edit, Delete, Star, TrendCharts, Calendar, Medal } from '@element-plus/icons-vue'
import { useHealthStore } from '../stores/healthStore'
import { HTYPE_OPTIONS, MILESTONE_SIZE, TOTAL_MILESTONES, TARGET_STEPS, HTYPE_LABELS } from '../types/healthTypes'
import * as echarts from 'echarts'
import * as healthApi from '../api/healthApi'

const store = useHealthStore()

// Filters
const filterYear = ref<number | undefined>(undefined)
const currentPage = ref(1)
const pageSize = 10

const yearOptions = computed(() => {
  const years: number[] = []
  const y = new Date().getFullYear()
  for (let i = y; i >= y - 5; i--) years.push(i)
  return years
})

const displayRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return store.records.slice(start, start + pageSize)
})

// Stat cards
const statCards = computed(() => {
  const s = store.summary
  if (!s) return []
  return [
    { key: 'total', label: '累计步数', value: formatNumber(s.total_steps), icon: 'Star', bg: '#fff7e6', color: '#fa8c16' },
    { key: 'milestone', label: '里程碑', value: `${s.completed_milestones}/${s.total_milestones}`, icon: 'Medal', bg: '#f0fff0', color: '#52c41a' },
    { key: 'daily', label: '日均步数', value: formatNumber(s.daily_avg), icon: 'TrendCharts', bg: '#e6f7ff', color: '#1890ff' },
    { key: 'predict', label: s.prediction ? '预估完成' : '运动天数', value: s.prediction ? s.prediction.target_date : `${s.days_active}天`, icon: 'Calendar', bg: '#fff0f6', color: '#eb2f96' },
  ]
})

// Milestone preview
const milestonePreview = computed(() => {
  return (store.milestones?.milestones || []).slice(0, 50)
})

// Chart refs
const yearlyChartRef = ref<HTMLElement>()
let yearlyChart: echarts.ECharts | null = null

// Form state
const formVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()
const formData = ref({
  steps: 0,
  htype: 1,
  time: '',
  remark: '',
})

const formRules = {
  steps: [{ required: true, message: '请输入运动量', trigger: 'blur' }],
  htype: [{ required: true, message: '请选择运动类型', trigger: 'change' }],
  time: [{ required: true, message: '请选择日期', trigger: 'change' }],
}

// Helpers
function formatNumber(n: number | undefined | null): string {
  if (n === undefined || n === null) return '0'
  if (n >= 100000000) return (n / 100000000).toFixed(2) + '亿'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function formatTime(t: string | undefined | null): string {
  if (!t) return '-'
  return t.slice(0, 10)
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  formData.value = { steps: 0, htype: 1, time: '', remark: '' }
  formVisible.value = true
}

function openEdit(row: any) {
  isEdit.value = true
  editingId.value = row.hid
  formData.value = {
    steps: row.steps ?? 0,
    htype: row.htype ?? 1,
    time: row.time || '',
    remark: row.remark || '',
  }
  formVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const payload = { ...formData.value }
    if (isEdit.value && editingId.value) {
      await healthApi.updateHealth(editingId.value, payload)
    } else {
      await healthApi.createHealth(payload)
    }
    ElMessage.success(isEdit.value ? '已更新' : '已添加')
    formVisible.value = false
    await refreshData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除 ${formatTime(row.time)} ${HTYPE_LABELS[row.htype] || ''}？`, '提示', { type: 'warning' })
    await healthApi.deleteHealth(row.hid)
    ElMessage.success('已删除')
    await refreshData()
  } catch { /* cancelled */ }
}

function resetForm() {
  formRef.value?.resetFields()
}

function handlePageChange(p: number) {
  currentPage.value = p
}

// Charts
function initCharts() {
  nextTick(() => {
    initYearlyChart()
  })
}

function initYearlyChart() {
  if (!yearlyChartRef.value) return
  if (!yearlyChart) yearlyChart = echarts.init(yearlyChartRef.value)
  const data = (store.yearlyComparison || []).slice(-10)
  const years = data.map(d => d.year)
  const steps = data.map(d => d.total_steps)
  yearlyChart.setOption({
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => formatNumber(v) + '步' },
    grid: { left: '3%', right: '4%', bottom: '8%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: years, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '步数', axisLabel: { formatter: (v: number) => v >= 100000000 ? (v / 100000000).toFixed(1) + '亿' : v >= 10000 ? (v / 10000).toFixed(0) + '万' : v } },
    series: [{
      type: 'bar', data: steps, barWidth: '50%',
      itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] },
      label: { show: true, position: 'top', formatter: (p: any) => p.value >= 100000000 ? (p.value / 100000000).toFixed(1) + '亿' : p.value >= 10000 ? (p.value / 10000).toFixed(0) + '万' : p.value, fontSize: 10 },
    }],
  })
  yearlyChart.resize()
}

async function refreshData() {
  currentPage.value = 1
  const params: Record<string, unknown> = {}
  if (filterYear.value) params.year = filterYear.value
  await Promise.all([
    store.fetchSummary(),
    store.fetchMilestones(),
    store.fetchYearlyComparison(),
    store.fetchRecords(Object.keys(params).length ? params : undefined),
  ])
  initCharts()
}

watch(() => store.yearlyComparison, initCharts, { deep: true })
window.addEventListener('resize', () => {
  yearlyChart?.resize()
})

onMounted(async () => {
  await store.fetchAll()
  initCharts()
})
</script>

<style scoped lang="scss">
.health-dashboard {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    .header-left { display: flex; align-items: center; gap: 12px;
      .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    }
    .header-actions { display: flex; gap: 8px; align-items: center; }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
    .pagination { margin-top: 12px; justify-content: flex-end; }
    .section-header { display: flex; justify-content: space-between; align-items: center; }
  }

  .progress-card {
    .progress-header {
      text-align: center; margin-bottom: 20px;
      .progress-title { font-size: 15px; color: #606266; margin-bottom: 4px; }
      .progress-subtitle { font-size: 13px; color: #909399; }
    }

    .progress-bar-wrap {
      padding: 0 4px; margin-bottom: 8px;
      .progress-bar {
        position: relative; height: 32px; background: #f0f0f0; border-radius: 16px; overflow: visible;
        .progress-fill {
          position: absolute; left: 0; top: 0; height: 100%; background: linear-gradient(90deg, #52c41a, #1890ff, #fa8c16);
          border-radius: 16px; transition: width 0.8s ease; min-width: 32px;
          .progress-glow { position: absolute; right: 0; top: -2px; width: 8px; height: 36px; background: rgba(255,255,255,0.4); border-radius: 4px; filter: blur(2px); }
        }
        .progress-milestone-dots {
          position: absolute; top: 0; left: 0; width: 100%; height: 100%;
          .milestone-dot {
            position: absolute; top: 50%; transform: translate(-50%, -50%);
            width: 6px; height: 6px; border-radius: 50%; background: #d9d9d9; transition: all 0.3s;
            &.completed { background: #52c41a; width: 8px; height: 8px; }
            &.current { background: #fa8c16; width: 12px; height: 12px; box-shadow: 0 0 6px rgba(250,140,22,0.6); animation: pulse 1.5s infinite; }
          }
        }
      }
    }

    .progress-info { text-align: center; font-size: 12px; color: #909399; }
  }

  .stats-row { margin-bottom: 18px;
    .stat-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      .stat-content { display: flex; align-items: center; gap: 14px; padding: 6px 4px;
        .stat-icon { width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .stat-info {
          .stat-value { font-size: 20px; font-weight: 700; color: #1F2937; line-height: 1.3; }
          .stat-label { font-size: 12px; color: #6B7280; }
        }
      }
    }
  }

  .chart-row { margin-bottom: 18px;
    .chart-box { height: 280px; width: 100%; }
    &.equal-height-row {
      .el-col { display: flex; }
      .equal-height-card { flex: 1; }
    }
  }

  .milestone-grid {
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: 4px;
    padding: 4px;

    .milestone-cell {
      aspect-ratio: 1;
      display: flex; align-items: center; justify-content: center;
      border-radius: 6px; font-size: 11px; font-weight: 600; color: #bfbfbf;
      background: #f5f5f5; cursor: pointer; transition: all 0.2s;
      &.completed { background: #52c41a; color: #fff; }
      &.current { background: #fff7e6; color: #fa8c16; border: 2px solid #fa8c16; box-shadow: 0 0 6px rgba(250,140,22,0.3); }
      &:hover { transform: scale(1.1); }
    }
  }

  .convert-hint { font-size: 12px; color: #909399; line-height: 1.5; }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 6px rgba(250,140,22,0.4); }
  50% { box-shadow: 0 0 12px rgba(250,140,22,0.8); }
}
</style>
