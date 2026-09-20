<template>
  <div class="travel-dashboard">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1><span class="header-icon">🗺️</span> 旅行足迹</h1>
        <p class="header-desc">走过的每一座城市，都值得被记住</p>
      </div>
      <div class="header-actions">
        <el-radio-group v-model="viewMode">
          <el-radio-button value="map">🗺️ 足迹地图</el-radio-button>
          <el-radio-button value="log">📔 行程日志</el-radio-button>
        </el-radio-group>
        <el-button type="primary" @click="showForm = true">
          <el-icon><Plus /></el-icon> 添加记录
        </el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="viewMode === 'map'" v-loading="store.loading" class="loading-wrap">
      <!-- 统计卡片 -->
      <el-row :gutter="12" class="stats-row">
        <el-col :span="4" v-for="card in statCards" :key="card.key">
          <el-card class="stat-card" :style="{ background: card.bg }" shadow="never">
            <div class="stat-inner">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 年份筛选 -->
      <div class="filter-bar">
        <span class="filter-label">📅 年份筛选：</span>
        <el-radio-group v-model="selectedYear" size="small" @change="onYearChange">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="y in store.years" :key="y" :value="y">{{ y }}</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 地图 -->
      <el-card class="map-card" shadow="never" v-if="store.mapData">
        <div class="map-legend">
          <span class="legend-title">城市热力</span>
          <span v-if="store.mapData?.heat_max" class="legend-hint">
            最高 {{ store.mapData.heat_max }} 次
          </span>
          <span class="legend-tip">鼠标移到区域上显示地市名称与到访明细</span>
          <span class="legend-item" v-for="l in heatLegend" :key="l.label">
            <span class="legend-dot" :style="{ background: l.color }"></span>
            {{ l.label }}
          </span>
          <span class="legend-divider"></span>
          <span class="legend-title">城市气泡</span>
          <span class="legend-item" v-for="l in bubbleLegend" :key="l.label">
            <span class="legend-dot" :style="{ background: l.color }"></span>
            {{ l.label }}
          </span>
        </div>
        <ChinaHeatmap :heatmap="store.mapData.heatmap" :bubbles="store.mapData.bubbles" />
      </el-card>

      <!-- 图表行 -->
      <el-row :gutter="16" class="charts-row" v-if="store.stats">
        <el-col :span="14">
          <el-card class="chart-card" shadow="never">
            <template #header><span>📊 每年旅行趋势</span></template>
            <div ref="trendChartRef" style="height: 260px"></div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card class="chart-card" shadow="never">
            <template #header><span>🥧 省份分布</span></template>
            <div ref="pieChartRef" style="height: 260px"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 最近足迹 -->
      <el-card class="recent-card" shadow="never" v-if="store.records.length">
        <template #header><span>📝 最近足迹</span></template>
        <div class="timeline">
          <div v-for="r in store.records" :key="r.tid" class="timeline-item">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <div class="timeline-top">
                <span class="timeline-year">{{ r.tyear }}</span>
                <span class="timeline-city">📍 {{ maskLocation(r.tname) }}</span>
                <span v-if="r.parentnode" class="timeline-prov">（{{ maskLocation(r.parentnode) }}{{ r.district ? ' · ' + r.district : '' }}）</span>
                <span v-if="r.rating" class="timeline-rating">{{ '⭐'.repeat(r.rating) }}</span>
              </div>
              <div class="timeline-meta">
                <span v-if="r.tcost">💰 {{ maskAmount(r.tcost) }}</span>
                <span v-if="r.companions">👥 {{ r.companions }}</span>
                <span v-if="r.duration_days">📆 {{ r.duration_days }} 天</span>
              </div>
              <div v-if="r.tremark" class="timeline-remark">{{ r.tremark }}</div>
            </div>
            <div class="timeline-actions">
              <el-button size="small" text @click="editRecord(r)">编辑</el-button>
              <el-button size="small" text type="danger" @click="handleDelete(r)">删除</el-button>
            </div>
          </div>
        </div>
        <div class="pagination-wrap" v-if="store.total > store.pageSize">
          <el-pagination
            v-model:current-page="store.currentPage"
            :page-size="store.pageSize"
            :total="store.total"
            layout="prev, pager, next"
            @current-change="store.setPage"
          />
        </div>
      </el-card>
    </div>

    <!-- 行程日志视图 -->
    <div v-else v-loading="logLoading" class="trip-log-view">
      <div class="log-toolbar">
        <div class="log-stats">
          <span class="log-stat"><b>{{ tripLog.total_days }}</b> 天行程</span>
          <span class="log-stat"><b>{{ tripLog.total_items }}</b> 个打卡点</span>
          <span class="log-stat pending"><b>{{ tripLog.pending_days }}</b> 天待沉淀</span>
        </div>
        <el-date-picker
          v-model="logRange"
          type="daterange"
          unlink-panels
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          @change="loadTripLog"
        />
      </div>

      <el-empty v-if="!tripLog.days.length" description="还没有打卡记录，去旅行心愿单打卡后会自动出现在这里" />

      <div
        v-for="day in tripLog.days"
        :key="day.date + day.city"
        class="log-day"
        :class="{ done: day.consolidated }"
      >
        <div class="log-day-head">
          <span class="log-date">{{ formatDay(day.date) }}</span>
          <span class="log-city">📍 {{ day.city }}</span>
          <el-tag v-if="day.consolidated" size="small" type="success" effect="plain">已沉淀足迹</el-tag>
          <el-tag v-else size="small" type="warning" effect="plain">临时日志</el-tag>
          <span class="log-meta">
            {{ day.item_count }} 项
            <template v-if="day.avg_rating"> · 均分 {{ day.avg_rating }}</template>
            <template v-if="day.worth_count"> · {{ day.worth_count }} 项值得反复</template>
          </span>
          <span class="log-actions">
            <el-button v-if="!day.consolidated" size="small" type="primary" plain @click="openConsolidate(day)">沉淀为足迹</el-button>
            <span v-else-if="day.record" class="log-record-info">
              <template v-if="day.record.tcost">💰 {{ maskAmount(day.record.tcost) }}</template>
              <template v-if="day.record.rating"> · {{ '⭐'.repeat(day.record.rating) }}</template>
              <template v-if="day.record.companions"> · {{ day.record.companions }}</template>
            </span>
          </span>
        </div>
        <div class="log-items">
          <div v-for="it in day.items" :key="it.id" class="log-item">
            <span class="li-icon">{{ it.is_food ? '🍽️' : '📍' }}</span>
            <span class="li-name">{{ it.name }}</span>
            <el-rate v-if="it.rating" :model-value="it.rating" disabled size="small" />
            <el-tag v-if="it.worth_revisit" size="small" effect="plain" type="danger">值得反复</el-tag>
            <span v-if="it.notes" class="li-notes">{{ it.notes }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 沉淀为足迹弹窗 -->
    <el-dialog v-model="showConsolidate" title="沉淀为旅行足迹" width="520px" :close-on-click-modal="false">
      <div v-if="consolidateDay" class="consolidate-body">
        <div class="consolidate-head">
          <span>🗓️ {{ formatDay(consolidateDay.date) }}</span>
          <span class="ch-city">📍 {{ consolidateDay.city }}</span>
        </div>
        <div class="consolidate-summary">{{ consolidateDay.summary }}</div>
        <el-form label-width="90px" class="consolidate-form">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="花费(元)">
                <el-input-number v-model="consolidateForm.tcost" :min="0" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="停留天数">
                <el-input-number v-model="consolidateForm.duration_days" :min="1" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="满意度">
            <el-rate v-model="consolidateForm.rating" :max="5" show-text />
          </el-form-item>
          <el-form-item label="同行伙伴">
            <el-input v-model="consolidateForm.companions" placeholder="如：独自、朋友、家人" />
          </el-form-item>
          <el-form-item label="足迹摘要">
            <el-input v-model="consolidateForm.tremark" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
        <div class="consolidate-hint">沉淀后生成一条旅行足迹，参与地图热力与年度统计；打卡明细仍保留在行程日志中。</div>
      </div>
      <template #footer>
        <el-button @click="showConsolidate = false">取消</el-button>
        <el-button type="primary" :loading="consolidating" @click="submitConsolidate">确认沉淀</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑表单弹窗 -->
    <el-dialog v-model="showForm" :title="editingRecord ? '编辑旅行记录' : '✈️ 添加旅行记录'" width="560px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="省份 *" prop="parentnode">
          <el-select v-model="formData.parentnode" placeholder="选择省份" @change="onProvinceChange" style="width:100%">
            <el-option v-for="p in provinces" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="地级市 *" prop="tname">
          <el-select v-model="formData.tname" placeholder="选择城市" @change="onCityChange" style="width:100%">
            <el-option v-for="c in cities" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="区/县级市" prop="district">
          <el-select v-model="formData.district" placeholder="选择区县（可选）" clearable style="width:100%">
            <el-option v-for="d in districts" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="访问年份 *" prop="tyear">
          <el-select v-model="formData.tyear" style="width:100%">
            <el-option v-for="y in currentYearRange" :key="y" :label="y" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item label="具体日期">
          <el-date-picker v-model="formData.ttime" type="date" placeholder="选择日期" style="width:100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="花费(元)">
              <el-input-number v-model="formData.tcost" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="停留天数">
              <el-input-number v-model="formData.duration_days" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="满意度">
          <el-rate v-model="formData.rating" :max="5" show-text />
        </el-form-item>
        <el-form-item label="同行伙伴">
          <el-input v-model="formData.companions" placeholder="如：独自、朋友、家人" />
        </el-form-item>
        <el-form-item label="旅行笔记">
          <el-input v-model="formData.tremark" type="textarea" :rows="3" placeholder="写点什么吧..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">{{ editingRecord ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import * as echarts from 'echarts'
import * as toolkitApi from '../../toolkit/api/toolkitApi'
import * as travelApi from '../api/travelApi'
import { useTravelStore } from '../stores/travelStore'
import ChinaHeatmap from '../components/ChinaHeatmap.vue'
import type { TravelRecord, TripLog, TripLogDay } from '../types/travelTypes'

const store = useTravelStore()
const { maskAmount, maskLocation } = usePrivacyMask()
const showForm = ref(false)
const submitting = ref(false)
const editingRecord = ref<TravelRecord | null>(null)
const selectedYear = ref('')

// ===== 行程日志（打卡聚合视图） =====
const viewMode = ref<'map' | 'log'>('map')
const logLoading = ref(false)
const logRange = ref<[string, string] | null>(null)
const tripLog = ref<TripLog>({ days: [], total_days: 0, total_items: 0, pending_days: 0 })
const showConsolidate = ref(false)
const consolidating = ref(false)
const consolidateDay = ref<TripLogDay | null>(null)
const consolidateForm = ref({
  tcost: null as number | null,
  duration_days: 1,
  rating: 0,
  companions: '',
  tremark: '',
})

async function loadTripLog() {
  logLoading.value = true
  try {
    const params: { from?: string; to?: string } = {}
    if (logRange.value?.[0]) params.from = logRange.value[0]
    if (logRange.value?.[1]) params.to = logRange.value[1]
    const res = await travelApi.getTripLog(params)
    tripLog.value = res.data
  } catch {
    ElMessage.error('加载行程日志失败')
  } finally {
    logLoading.value = false
  }
}

function formatDay(date: string): string {
  const [, m, d] = date.split('-')
  return `${Number(m)}月${Number(d)}日`
}

function openConsolidate(day: TripLogDay) {
  consolidateDay.value = day
  consolidateForm.value = {
    tcost: null,
    duration_days: 1,
    rating: day.avg_rating ? Math.round(day.avg_rating) : 0,
    companions: '',
    tremark: day.summary,
  }
  showConsolidate.value = true
}

async function submitConsolidate() {
  if (!consolidateDay.value) return
  consolidating.value = true
  try {
    await travelApi.consolidateTripDay({
      date: consolidateDay.value.date,
      city: consolidateDay.value.city,
      tcost: consolidateForm.value.tcost,
      duration_days: consolidateForm.value.duration_days,
      rating: consolidateForm.value.rating || null,
      companions: consolidateForm.value.companions,
      tremark: consolidateForm.value.tremark,
    })
    ElMessage.success('已沉淀为旅行足迹')
    showConsolidate.value = false
    await loadTripLog()
    refreshAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '沉淀失败')
  } finally {
    consolidating.value = false
  }
}

watch(viewMode, (mode) => {
  if (mode === 'log') loadTripLog()
})

const trendChartRef = ref<HTMLElement>()
const pieChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

const currentYear = new Date().getFullYear()
const currentYearRange = computed(() => {
  const years: number[] = []
  for (let y = currentYear; y >= 2000; y--) years.push(y)
  return years
})

const formRef = ref()

// 三级联动
const provinces = ref<string[]>([])
const cities = ref<string[]>([])
const districts = ref<string[]>([])

async function loadProvinces() {
  try {
    const res = await toolkitApi.getProvinces()
    provinces.value = res.data || []
  } catch { /* 静默 */ }
}

function onProvinceChange(province: string) {
  formData.value.tname = ''
  formData.value.district = ''
  cities.value = []
  districts.value = []
  if (!province) return
  toolkitApi.getCities(province).then(res => {
    cities.value = res.data || []
  })
}

function onCityChange(city: string) {
  formData.value.district = ''
  districts.value = []
  if (!city) return
  toolkitApi.getDistricts(city).then(res => {
    districts.value = res.data || []
  })
}

const formData = ref({
  parentnode: '',
  tname: '',
  district: '',
  tyear: currentYear,
  ttime: '',
  tcost: null as number | null,
  duration_days: null as number | null,
  rating: 0,
  companions: '',
  tremark: '',
})

const formRules = {
  parentnode: [{ required: true, message: '请选择省份', trigger: 'change' }],
  tname: [{ required: true, message: '请选择城市', trigger: 'change' }],
  tyear: [{ required: true, message: '请选择年份', trigger: 'change' }],
}

const heatLegend = [
  { label: '未去过', color: '#E9EDF3' },
  { label: '偶尔', color: '#B3D4FF' },
  { label: '多次', color: '#7BB3FF' },
  { label: '频繁', color: '#3D7EFF' },
  { label: '深度游', color: '#0049B3' },
]

const bubbleLegend = [
  { label: '满意 (5)', color: '#FCD34D' },
  { label: '不错 (4)', color: '#60A5FA' },
  { label: '一般 (≤3)', color: '#9CA3AF' },
]

const statCards = computed(() => {
  const o = store.stats?.overview
  if (!o) return []
  return [
    { key: 'records', label: '旅行记录', value: `${o.record_count} 条`, bg: '#f0f5ff', color: '#2f54eb' },
    { key: 'cities', label: '到访城市', value: `${o.city_count} 个`, bg: '#fff7e6', color: '#fa8c16' },
    { key: 'provinces', label: '到访省份', value: `${o.province_count} 个`, bg: '#f6ffed', color: '#52c41a' },
    { key: 'days', label: '累计天数', value: o.total_days ? `${o.total_days} 天` : '-', bg: '#fff0f6', color: '#eb2f96' },
    { key: 'cost', label: '总花费', value: o.total_cost ? maskAmount(o.total_cost) : '-', bg: '#fef3e8', color: '#e67e22' },
    { key: 'rating', label: '平均满意度', value: o.avg_rating ? `${o.avg_rating} ⭐` : '-', bg: '#f3e8ff', color: '#9333ea' },
  ]
})

// Year filter
function onYearChange(val: string | number) {
  if (val === '') {
    store.fetchRecords()
    store.fetchMapData()
    store.fetchStats()
  } else {
    const y = Number(val)
    store.fetchRecords({ year: y })
    store.fetchMapData(y, y)
    store.fetchStats(y, y)
  }
}

// Form
function editRecord(r: TravelRecord) {
  editingRecord.value = r
  formData.value = {
    parentnode: r.parentnode || '',
    tname: r.tname || '',
    district: r.district || '',
    tyear: r.tyear || currentYear,
    ttime: r.ttime || '',
    tcost: r.tcost,
    duration_days: r.duration_days,
    rating: r.rating || 0,
    companions: r.companions || '',
    tremark: r.tremark || '',
  }
  // 回显级联菜单
  if (r.parentnode) {
    toolkitApi.getCities(r.parentnode).then(res => {
      cities.value = res.data || []
      if (r.tname) {
        toolkitApi.getDistricts(r.tname).then(res2 => {
          districts.value = res2.data || []
        })
      }
    })
  }
  showForm.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()
  submitting.value = true
  try {
    const data = { ...formData.value }
    if (editingRecord.value) {
      await store.updateRecord(editingRecord.value.tid, data)
      ElMessage.success('更新成功')
    } else {
      await store.createRecord(data)
      ElMessage.success('添加成功')
    }
    showForm.value = false
    resetForm()
    refreshAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

function handleDelete(r: TravelRecord) {
  ElMessageBox.confirm(`确定删除「${r.tname}」的记录吗？`, '确认', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    await store.deleteRecord(r.tid)
    ElMessage.success('已删除')
    refreshAll()
  }).catch(() => {})
}

function resetForm() {
  editingRecord.value = null
  cities.value = []
  districts.value = []
  formData.value = {
    parentnode: '',
    tname: '',
    district: '',
    tyear: currentYear,
    ttime: '',
    tcost: null,
    duration_days: null,
    rating: 0,
    companions: '',
    tremark: '',
  }
}

// Charts
function initTrendChart() {
  if (!trendChartRef.value || !store.stats) return
  trendChart = echarts.init(trendChartRef.value)
  const trend = store.stats.yearly_trend
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '8%', right: '8%', bottom: '12%', top: '8%' },
    xAxis: {
      type: 'category',
      data: trend.map(t => t.year),
      axisLabel: { color: '#9CA3AF' },
      axisLine: { lineStyle: { color: '#E5E7EB' } },
    },
    yAxis: [
      {
        type: 'value',
        name: '次数',
        minInterval: 1,
        axisLabel: { color: '#9CA3AF' },
        splitLine: { lineStyle: { color: '#F3F4F6' } },
      },
    ],
    series: [
      {
        name: '旅行次数',
        type: 'bar',
        data: trend.map(t => t.count),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#3D7EFF' },
            { offset: 1, color: '#B3D4FF' },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
        barMaxWidth: 40,
      },
    ],
  })
}

function initPieChart() {
  if (!pieChartRef.value || !store.stats) return
  pieChart = echarts.init(pieChartRef.value)
  const dist = store.stats.province_distribution
  const colors = ['#3D7EFF', '#60A5FA', '#7BB3FF', '#B3D4FF', '#0049B3']
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '55%'],
      data: dist.map((d, i) => ({
        name: d.province,
        value: d.count,
        itemStyle: { color: colors[i % colors.length] },
      })),
      label: { color: '#374151', fontSize: 12 },
      emphasis: {
        label: { fontSize: 14, fontWeight: 'bold' },
        itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.2)' },
      },
    }],
  })
}

function refreshAll() {
  store.fetchRecords()
  store.fetchMapData()
  store.fetchStats()
}

function handleResize() {
  trendChart?.resize()
  pieChart?.resize()
}

watch(() => store.stats, () => {
  nextTick(() => {
    initTrendChart()
    initPieChart()
  })
}, { deep: true })

onMounted(() => {
  loadProvinces()
  store.fetchYears()
  store.fetchRecords()
  store.fetchMapData()
  store.fetchStats()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped lang="scss">
.travel-dashboard {
  padding: 24px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;

    .header-left {
      h1 {
        font-size: 22px;
        font-weight: 700;
        color: #1F2937;
        margin: 0 0 6px 0;

        .header-icon { margin-right: 8px; }
      }
      .header-desc {
        font-size: 13px;
        color: #9CA3AF;
        margin: 0;
      }
    }
  }

  .stats-row {
    margin-bottom: 20px;

    .stat-card {
      border: none;
      border-radius: 10px;

      .stat-inner {
        text-align: center;
        padding: 6px 0;

        .stat-value {
          font-size: 24px;
          font-weight: 700;
          color: #1F2937;
        }
        .stat-label {
          font-size: 13px;
          color: #6B7280;
          margin-top: 4px;
        }
      }
    }
  }

  .filter-bar {
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 12px;

    .filter-label {
      font-size: 14px;
      font-weight: 500;
      color: #374151;
      white-space: nowrap;
    }
  }

  .map-card {
    border: none;
    border-radius: 10px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);

    .map-legend {
      display: flex;
      align-items: center;
      gap: 12px;
      padding-bottom: 12px;
      flex-wrap: wrap;

      .legend-title {
        font-size: 12px;
        font-weight: 600;
        color: #374151;
      }

      .legend-hint {
        font-size: 12px;
        color: #9CA3AF;
        margin-left: -6px;
      }

      .legend-tip {
        font-size: 12px;
        color: #9CA3AF;
        margin-left: auto;
      }

      .legend-divider {
        width: 1px;
        height: 20px;
        background: #E5E7EB;
      }

      .legend-item {
        font-size: 12px;
        color: #6B7280;
        display: flex;
        align-items: center;
        gap: 4px;

        .legend-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          display: inline-block;
        }
      }
    }
  }

  .charts-row {
    margin-bottom: 20px;

    .chart-card {
      border: none;
      border-radius: 10px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);

      :deep(.el-card__header) {
        padding: 14px 20px;
        font-size: 14px;
        font-weight: 500;
        border-bottom: 1px solid #f2f2f2;
      }
    }
  }

  .recent-card {
    border: none;
    border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);

    :deep(.el-card__header) {
      padding: 14px 20px;
      font-size: 14px;
      font-weight: 500;
      border-bottom: 1px solid #f2f2f2;
    }

    .timeline {
      position: relative;
      padding-left: 20px;

      &::before {
        content: '';
        position: absolute;
        left: 6px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: #E5E7EB;
      }

      .timeline-item {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 0;
        position: relative;
        border-bottom: 1px solid #f9fafb;

        &:last-child { border-bottom: none; }

        .timeline-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: #3D7EFF;
          border: 2px solid #fff;
          position: absolute;
          left: -17px;
          top: 16px;
          z-index: 1;
        }

        .timeline-content {
          flex: 1;

          .timeline-top {
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;

            .timeline-year {
              font-size: 12px;
              color: #9CA3AF;
              background: #F3F4F6;
              padding: 2px 8px;
              border-radius: 4px;
            }

            .timeline-city {
              font-size: 15px;
              font-weight: 600;
              color: #1F2937;
            }

            .timeline-prov {
              font-size: 12px;
              color: #9CA3AF;
            }

            .timeline-rating {
              font-size: 12px;
            }
          }

          .timeline-meta {
            display: flex;
            gap: 16px;
            margin-top: 4px;
            font-size: 12px;
            color: #6B7280;
          }

          .timeline-remark {
            margin-top: 6px;
            font-size: 13px;
            color: #374151;
            line-height: 1.5;
            background: #F9FAFB;
            padding: 6px 10px;
            border-radius: 6px;
          }
        }

        .timeline-actions {
          display: flex;
          gap: 4px;
          flex-shrink: 0;
        }
      }

      .pagination-wrap {
        display: flex;
        justify-content: center;
        padding: 16px 0 4px;
      }
    }
  }
}

/* ===== 行程日志视图 ===== */
.travel-dashboard .header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.trip-log-view {
  .log-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 16px;
    padding: 12px 16px;
    background: #fff;
    border-radius: 10px;
    border: 1px solid #EEF0F3;
  }

  .log-stats {
    display: flex;
    gap: 20px;
    font-size: 13px;
    color: #6B7280;

    b {
      color: #1F2937;
      font-size: 16px;
      margin-right: 4px;
    }

    .pending b {
      color: #D97706;
    }
  }

  .log-day {
    background: #fff;
    border: 1px dashed #E5E7EB;
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 14px;

    &.done {
      border-style: solid;
      border-color: #E5E7EB;
    }

    .log-day-head {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;

      .log-date {
        font-size: 15px;
        font-weight: 600;
        color: #1F2937;
      }

      .log-city {
        font-size: 14px;
        color: #374151;
      }

      .log-meta {
        font-size: 12px;
        color: #9CA3AF;
      }

      .log-actions {
        margin-left: auto;
        display: flex;
        align-items: center;
      }

      .log-record-info {
        font-size: 12px;
        color: #6B7280;
      }
    }

    .log-items {
      margin-top: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-left: 4px;

      .log-item {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 13px;
        color: #374151;

        .li-icon {
          font-size: 15px;
        }

        .li-name {
          font-weight: 500;
        }

        .li-notes {
          color: #9CA3AF;
          font-size: 12px;
          max-width: 260px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }
  }
}

.consolidate-body {
  .consolidate-head {
    display: flex;
    gap: 12px;
    font-size: 14px;
    font-weight: 500;
    color: #1F2937;

    .ch-city {
      font-weight: 400;
      color: #4B5563;
    }
  }

  .consolidate-summary {
    margin: 8px 0 16px;
    padding: 8px 12px;
    background: #F9FAFB;
    border-radius: 8px;
    font-size: 13px;
    color: #4B5563;
  }

  .consolidate-hint {
    font-size: 12px;
    line-height: 1.5;
    color: #9CA3AF;
  }
}
</style>
