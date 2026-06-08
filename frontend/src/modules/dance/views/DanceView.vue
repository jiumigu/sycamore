<template>
  <div class="dance-dashboard">
    <!-- 归档提示 -->
    <el-alert title="此模块已归档，随时可重新启用" type="info" show-icon :closable="false" class="archive-banner" />

    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">💃 舞蹈学习记录</h1>
        <el-tag type="danger" class="module-tag">兴趣爱好</el-tag>
      </div>
      <div class="header-actions">
        <el-select v-model="filterYear" size="default" style="width: 110px" @change="refreshData">
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

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4.8" v-for="card in statCards" :key="card.key">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: card.bg }">
              <el-icon :color="card.color" :size="20"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">
                {{ card.label }}
                <span v-if="card.change !== undefined" :style="{ color: (card.change || 0) >= 0 ? '#52c41a' : '#f5222d' }">
                  {{ (card.change || 0) >= 0 ? '↑' : '↓' }}{{ Math.abs(card.change || 0) }}
                </span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选栏 -->
    <el-card class="section-card filter-card">
      <el-row :gutter="12" align="middle">
        <el-col :span="5">
          <el-select v-model="filterType" placeholder="全部舞种" clearable style="width: 100%" @change="fetchRecords">
            <el-option v-for="t in DANCE_TYPE_OPTIONS" :key="t.value" :label="`${t.icon} ${t.label}`" :value="t.value" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filterTeacher" placeholder="全部老师" clearable filterable style="width: 100%" @change="fetchRecords">
            <el-option v-for="t in teacherOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filterDifficulty" placeholder="全部难度" clearable style="width: 100%" @change="fetchRecords">
            <el-option v-for="d in DIFFICULTY_OPTIONS" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-col>
        <el-col :span="9" class="text-right">
          <el-button size="small" @click="resetFilters">重置筛选</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 图表区 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>📊 每月上课次数</span></template>
          <div ref="trendChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>🎵 舞蹈类型分布</span></template>
          <div ref="typeChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>🏆 老师授课排行</span></template>
          <div ref="teacherChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>📈 自我评分趋势</span></template>
          <div ref="scoreChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 记录列表 -->
    <el-card class="section-card">
      <template #header>
        <div class="section-header">
          <span>📝 最近课程记录</span>
        </div>
      </template>
      <el-table v-loading="store.loading" :data="displayRecords" style="width: 100%" size="small" stripe>
        <el-table-column label="日期" width="100">
          <template #default="{ row }">{{ row.study_time || '-' }}</template>
        </el-table-column>
        <el-table-column label="周几" width="60" prop="weekinfo" />
        <el-table-column label="老师" width="80" prop="teacher_name" />
        <el-table-column label="舞种" width="100">
          <template #default="{ row }">
            <el-tag :color="typeColor(row.dance_type)" effect="dark" size="small" style="color:#fff;border:none">
              {{ row.type_icon }} {{ row.dance_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="难度" width="80" prop="difficulty" />
        <el-table-column label="评分" width="70">
          <template #default="{ row }">
            <span :style="{ color: scoreColor(row.score), fontWeight: 600 }">{{ row.score }}</span>
          </template>
        </el-table-column>
        <el-table-column label="体能" width="60" prop="energy_level" />
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
    <el-dialog v-model="formVisible" :title="isEdit ? '编辑舞蹈记录' : '💃 添加舞蹈记录'" width="480px" @close="resetForm">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="0">
        <div class="form-row">
          <el-form-item prop="study_time" class="form-half">
            <template #label><span style="font-size:13px">学习日期 *</span></template>
            <el-date-picker v-model="formData.study_time" type="date" placeholder="选择日期" format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width:100%" />
          </el-form-item>
          <el-form-item prop="teacher_name" class="form-half">
            <template #label><span style="font-size:13px">授课老师 *</span></template>
            <el-select v-model="formData.teacher_name" placeholder="老师" filterable allow-create style="width:100%">
              <el-option v-for="t in teacherOptions" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item prop="dance_type" class="form-half">
            <template #label><span style="font-size:13px">舞蹈类型 *</span></template>
            <el-select v-model="formData.dance_type" placeholder="选择" style="width:100%">
              <el-option v-for="t in DANCE_TYPE_OPTIONS" :key="t.value" :label="`${t.icon} ${t.label}`" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item prop="difficulty" class="form-half">
            <template #label><span style="font-size:13px">难度等级 *</span></template>
            <el-select v-model="formData.difficulty" placeholder="选择" style="width:100%">
              <el-option v-for="d in DIFFICULTY_OPTIONS" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item>
        </div>

        <el-form-item prop="score" label="自我评分">
          <div class="score-slider-wrap">
            <el-slider v-model="formData.score" :min="1" :max="10" :step="1" :marks="scoreMarks" show-stops />
            <div class="score-label">
              当前选择：<strong :style="{ color: scoreColor(formData.score) }">{{ formData.score }}分</strong>
              — {{ SCORE_LABELS[formData.score] || '' }}
            </div>
          </div>
        </el-form-item>

        <el-form-item label="体能消耗">
          <el-radio-group v-model="formData.energy_level">
            <el-radio-button v-for="i in 5" :key="i" :value="i">{{ i }}</el-radio-button>
          </el-radio-group>
          <span class="energy-hint">{{ formData.energy_level >= 4 ? '🔥 暴汗' : formData.energy_level >= 2 ? '🏃 适中' : '🧘 轻松' }}</span>
        </el-form-item>

        <el-form-item label="学习心得">
          <el-input v-model="formData.remark" type="textarea" :rows="2" maxlength="100" placeholder="记录学习感受..." />
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
import { Plus, Refresh, Edit, Delete } from '@element-plus/icons-vue'
import { useDanceStore } from '../stores/danceStore'
import { DANCE_TYPE_OPTIONS, DIFFICULTY_OPTIONS, SCORE_LABELS } from '../types/danceTypes'
import * as echarts from 'echarts'

const store = useDanceStore()

// Filters
const filterYear = ref(new Date().getFullYear())
const filterType = ref('')
const filterTeacher = ref('')
const filterDifficulty = ref('')
const currentPage = ref(1)
const pageSize = 10

const yearOptions = computed(() => {
  const years: number[] = []
  const y = new Date().getFullYear()
  for (let i = y; i >= y - 5; i--) years.push(i)
  return years
})

const teacherOptions = computed(() => {
  return [...new Set(store.teachers.map(t => t.name))]
})

const statCards = computed(() => {
  const o = store.overview
  if (!o) return []
  return [
    { key: 'count', label: '总上课次数', value: o.total_count, icon: 'Star', bg: '#fff7e6', color: '#fa8c16' },
    { key: 'teachers', label: `合作老师 · ${o.favorite_teacher ? '最爱' + o.favorite_teacher : ''}`, value: o.total_teachers, icon: 'User', bg: '#e6f7ff', color: '#1890ff' },
    { key: 'types', label: '舞种数', value: o.total_types, icon: 'Magnet', bg: '#f6ffed', color: '#52c41a' },
    { key: 'score', label: `平均评分 · 最高${o.max_score}`, value: o.avg_score, icon: 'Star', bg: '#fff0f6', color: '#eb2f96' },
    { key: 'monthly', label: `本月上课`, value: `${o.this_month_count}次`, change: o.monthly_change, icon: 'Calendar', bg: '#f0f5ff', color: '#2f54eb' },
  ]
})

// Chart refs
const trendChartRef = ref<HTMLElement>()
const typeChartRef = ref<HTMLElement>()
const teacherChartRef = ref<HTMLElement>()
const scoreChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let typeChart: echarts.ECharts | null = null
let teacherChart: echarts.ECharts | null = null
let scoreChart: echarts.ECharts | null = null

const displayRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return store.records.slice(start, start + pageSize)
})

// Form state
const formVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()
const formData = ref({
  study_time: '',
  teacher_name: '',
  dance_type: 'jazz',
  difficulty: '入门',
  score: 5,
  energy_level: 3,
  remark: '',
})

const formRules = {
  study_time: [{ required: true, message: '请选择日期', trigger: 'change' }],
  teacher_name: [{ required: true, message: '请输入老师', trigger: 'change' }],
  dance_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  difficulty: [{ required: true, message: '请选择难度', trigger: 'change' }],
}

const scoreMarks = { 1: '1', 5: '5', 10: '10' }

function scoreColor(s: number): string {
  if (s >= 8) return '#f5222d'
  if (s >= 5) return '#fa8c16'
  if (s >= 3) return '#1890ff'
  return '#8c8c8c'
}

function typeColor(type: string): string {
  return DANCE_TYPE_OPTIONS.find(t => t.value === type)?.color || '#909399'
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  formData.value = { study_time: '', teacher_name: '', dance_type: 'jazz', difficulty: '入门', score: 5, energy_level: 3, remark: '' }
  formVisible.value = true
}

function openEdit(row: any) {
  isEdit.value = true
  editingId.value = row.id
  formData.value = {
    study_time: row.study_time || '',
    teacher_name: row.teacher_name || '',
    dance_type: row.dance_type || 'jazz',
    difficulty: row.difficulty || '入门',
    score: row.score || 5,
    energy_level: row.energy_level || 3,
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
      await store.records.find(r => r.id === editingId.value)
        ? await danceApi.updateDance(editingId.value, payload)
        : null
    } else {
      await danceApi.createDance(payload)
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
    await ElMessageBox.confirm(`确定删除 ${row.study_time} ${row.dance_type}？`, '提示', { type: 'warning' })
    await danceApi.deleteDance(row.id)
    ElMessage.success('已删除')
    await refreshData()
  } catch { /* cancelled */ }
}

function resetForm() {
  formRef.value?.resetFields()
}

function resetFilters() {
  filterType.value = ''
  filterTeacher.value = ''
  filterDifficulty.value = ''
  currentPage.value = 1
  fetchRecords()
}

function handlePageChange(p: number) {
  currentPage.value = p
}

// Charts
function initCharts() {
  nextTick(() => {
    initTrendChart()
    initTypeChart()
    initTeacherChart()
    initScoreChart()
  })
}

function initTrendChart() {
  if (!trendChartRef.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)
  const data = store.trendData?.monthly || []
  const months = data.map(d => `${d.month}月`)
  const counts = data.map(d => d.count)
  const scores = data.map(d => d.avg_score)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['上课次数', '平均评分'], bottom: 0, icon: 'circle', itemWidth: 10 },
    grid: { left: '3%', right: '4%', bottom: '20%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: months },
    yAxis: [{ type: 'value', name: '次数' }, { type: 'value', name: '评分', min: 0, max: 10 }],
    series: [
      { name: '上课次数', type: 'bar', data: counts, barWidth: '50%', itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] } },
      { name: '平均评分', type: 'line', yAxisIndex: 1, data: scores, smooth: true, symbol: 'circle', lineStyle: { color: '#eb2f96' }, itemStyle: { color: '#eb2f96' } },
    ],
  })
  trendChart.resize()
}

function initTypeChart() {
  if (!typeChartRef.value) return
  if (!typeChart) typeChart = echarts.init(typeChartRef.value)
  const data = (store.typeStats || []).map(d => ({
    name: d.name,
    value: d.count,
    itemStyle: { color: typeColor(d.name) },
  }))
  typeChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}次 ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'center', data: data.map(d => d.name) },
    series: [{
      type: 'pie', radius: ['45%', '65%'], center: ['55%', '50%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
      data,
    }],
  })
  typeChart.resize()
}

function initTeacherChart() {
  if (!teacherChartRef.value) return
  if (!teacherChart) teacherChart = echarts.init(teacherChartRef.value)
  const data = (store.teachers || []).slice(0, 10)
  const names = data.map(d => d.name).reverse()
  const counts = data.map(d => d.count).reverse()
  const scores = data.map(d => d.avg_score).reverse()
  teacherChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (p: any) => {
      const i = p[0].dataIndex
      return `${names[i]}<br/>授课 ${counts[i]} 次<br/>平均评分 ${scores[i]}`
    } },
    grid: { left: '3%', right: '15%', bottom: '3%', top: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar',
      data: counts.map((v, i) => ({
        value: v,
        itemStyle: { color: scores[i] >= 4 ? '#eb2f96' : scores[i] >= 2 ? '#1890ff' : '#8c8c8c', borderRadius: [0, 4, 4, 0] },
      })),
      barWidth: '55%',
      label: { show: true, position: 'right', formatter: (p: any) => `${p.value}次`, fontSize: 11 },
    }],
  })
  teacherChart.resize()
}

function initScoreChart() {
  if (!scoreChartRef.value) return
  if (!scoreChart) scoreChart = echarts.init(scoreChartRef.value)
  const data = store.scoreTrend || []
  const periods = data.map(d => d.period)
  const scores = data.map(d => d.avg_score)
  scoreChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '5%', containLabel: true },
    xAxis: { type: 'category', data: periods, axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 10, name: '评分' },
    series: [{
      type: 'line', data: scores, smooth: true,
      symbol: 'circle', symbolSize: 8,
      lineStyle: { color: '#eb2f96', width: 2 },
      itemStyle: { color: '#eb2f96' },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(235,47,150,0.2)' }, { offset: 1, color: 'rgba(235,47,150,0.02)' }] } },
      label: { show: true, position: 'top', formatter: (p: any) => p.value.toFixed(1), fontSize: 10, color: '#606266' },
    }],
  })
  scoreChart.resize()
}

async function fetchRecords() {
  const params: Record<string, unknown> = { year: filterYear.value }
  if (filterType.value) params.dance_type = filterType.value
  if (filterTeacher.value) params.teacher = filterTeacher.value
  if (filterDifficulty.value) params.difficulty = filterDifficulty.value
  await store.fetchRecords(params)
}

async function refreshData() {
  await Promise.all([
    store.fetchOverview(),
    store.fetchTrend(filterYear.value),
    store.fetchTeachers(),
    store.fetchTypes(),
    store.fetchScoreTrend(),
    fetchRecords(),
  ])
  initCharts()
}

watch(() => store.typeStats, initCharts, { deep: true })
window.addEventListener('resize', () => {
  trendChart?.resize()
  typeChart?.resize()
  teacherChart?.resize()
  scoreChart?.resize()
})

onMounted(() => {
  store.fetchAll(filterYear.value).then(initCharts)
})
</script>

<script lang="ts">
import * as danceApi from '../api/danceApi'
export { danceApi }
</script>

<style scoped lang="scss">
.dance-dashboard {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .archive-banner { margin-bottom: 16px; }

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    .header-left { display: flex; align-items: center; gap: 12px;
      .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    }
    .header-actions { display: flex; gap: 8px; align-items: center; }
  }

  .stats-row { margin-bottom: 18px;
    :deep(.el-col-4_8) { width: 20%; }
    .stat-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      .stat-content { display: flex; align-items: center; gap: 14px; padding: 6px 4px;
        .stat-icon { width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .stat-info {
          .stat-value { font-size: 22px; font-weight: 700; color: #1F2937; line-height: 1.3; }
          .stat-label { font-size: 12px; color: #6B7280; }
        }
      }
    }
  }

  .filter-card { margin-bottom: 18px; border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

  .chart-row { margin-bottom: 18px;
    .chart-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
      .chart-box { height: 300px; width: 100%; }
    }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
    .pagination { margin-top: 12px; justify-content: flex-end; }
  }

  .text-right { text-align: right; }

  .form-row { display: flex; gap: 12px;
    .form-half { flex: 1; }
  }

  .score-slider-wrap {
    width: 100%; padding: 0 8px;
    .score-label { margin-top: 8px; font-size: 13px; color: #606266; text-align: center; }
  }

  .energy-hint { margin-left: 10px; font-size: 12px; color: #909399; }
}
</style>
