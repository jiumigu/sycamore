<template>
  <div class="book-chart-view">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">📊 阅读图形分析</h2>
        <el-tag type="primary" class="module-tag">书籍阅读 · 年度统计与类型分布</el-tag>
      </div>
      <div class="header-actions">
        <el-select
          v-model="year"
          placeholder="全部年份"
          clearable
          class="year-select"
          @change="fetchData"
        >
          <el-option v-for="y in yearOptions" :key="y" :label="`${y} 年`" :value="y" />
        </el-select>
        <el-button @click="fetchData">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button type="primary" plain @click="goBack">
          <el-icon><ArrowLeft /></el-icon>返回阅读管理
        </el-button>
      </div>
    </div>

    <!-- 统计卡片（随年份选择联动） -->
    <el-row :gutter="20" class="stats-section">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6f7ff">
              <el-icon color="#1890ff"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.total_count || 0 }}</div>
              <div class="stat-label">{{ scopeLabel('累计书籍', '入档书籍') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f6ffed">
              <el-icon color="#52c41a"><Check /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.completed_count || 0 }}</div>
              <div class="stat-label">{{ scopeLabel('已完成', '已完成') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff7e6">
              <el-icon color="#fa8c16"><Star /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.avg_recommend?.toFixed(1) || '0' }}</div>
              <div class="stat-label">{{ scopeLabel('平均推荐', '平均推荐') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff1f0">
              <el-icon color="#f5222d"><Reading /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.reading_count || 0 }}</div>
              <div class="stat-label">{{ scopeLabel('阅读中', '阅读中') }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 年度阅读统计：多年趋势，点击柱子可联动筛选该年类型分布 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>年度阅读统计</span>
              <el-tag v-if="year" size="small" type="warning" effect="plain">{{ year }} 年高亮</el-tag>
              <span v-else class="card-tip">点击柱子可查看该年类型分布</span>
            </div>
          </template>
          <div v-if="yearData.length" ref="yearChartRef" class="chart-container" />
          <el-empty v-else description="暂无年度数据" :image-size="100" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>书籍类型分布</span>
              <el-tag v-if="year" size="small" type="primary" effect="plain">{{ year }} 年</el-tag>
            </div>
          </template>
          <div v-if="pieData.length" ref="typeChartRef" class="chart-container" />
          <el-empty v-else description="该范围暂无类型数据" :image-size="100" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, ArrowLeft, Document, Check, Star, Reading } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import * as bookApi from '../api/bookApi'
import type { BookStats } from '../types/bookTypes'

const router = useRouter()

const loading = ref(false)
const year = ref<string | undefined>()
const stats = ref<BookStats | null>(null)

const yearChartRef = ref<HTMLDivElement>()
const typeChartRef = ref<HTMLDivElement>()
let yearChart: echarts.ECharts | null = null
let typeChart: echarts.ECharts | null = null

/** 年度趋势（升序）——year_stats 恒为全量，不受年份选择过滤 */
const yearData = computed(() => {
  const rows = (stats.value?.year_stats || [])
    .filter(i => i.years != null && String(i.years).trim() !== '')
    .map(i => ({ years: String(i.years), count: i.count }))
    .sort((a, b) => a.years.localeCompare(b.years))
  return rows
})

/** 年份下拉选项（降序） */
const yearOptions = computed(() => yearData.value.map(i => i.years).reverse())

/** 类型分布（随年份选择联动） */
const pieData = computed(() => (stats.value?.type_stats || []).filter(i => i.count > 0))

function scopeLabel(allText: string, scopedText: string) {
  return year.value ? `${year.value} 年${scopedText}` : allText
}

async function fetchData() {
  loading.value = true
  try {
    const params = year.value ? { year: year.value } : undefined
    const resp = await bookApi.getBookStats(params)
    stats.value = resp.data
    await nextTick()
    renderYearChart()
    renderTypeChart()
  } catch {
    ElMessage.error('获取统计失败')
  } finally {
    loading.value = false
  }
}

function renderYearChart() {
  const el = yearChartRef.value
  if (!el) {
    if (yearChart) { yearChart.dispose(); yearChart = null }
    return
  }
  if (!yearChart) {
    yearChart = echarts.init(el)
    yearChart.on('click', (params: echarts.ECElementEvent) => {
      const v = String(params.name ?? '')
      if (!v || !yearOptions.value.includes(v) || v === year.value) return
      year.value = v
      fetchData()
    })
  }
  const sel = year.value
  yearChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (ps: unknown) => {
      const arr = ps as Array<{ name: string; value: number }>
      if (!Array.isArray(arr) || !arr.length) return ''
      const item = arr[0]
      return `${item.name} 年：<b>${item.value}</b> 本${item.name === sel ? '（当前筛选）' : ''}`
    } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: yearData.value.map(i => i.years), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '阅读数量' },
    series: [{
      type: 'bar',
      barWidth: '40%',
      data: yearData.value.map(i => ({
        value: i.count,
        itemStyle: i.years === sel
          ? { color: '#F5A623', borderRadius: [4, 4, 0, 0], shadowBlur: 8, shadowColor: 'rgba(245,166,35,0.4)' }
          : { color: '#409EFF', borderRadius: [4, 4, 0, 0] },
      })),
    }],
  })
}

function renderTypeChart() {
  const el = typeChartRef.value
  if (!el) {
    if (typeChart) { typeChart.dispose(); typeChart = null }
    return
  }
  if (!typeChart) typeChart = echarts.init(el)
  const td = pieData.value
  typeChart.setOption({
    tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'middle', data: td.map(i => i.btype) },
    series: [{
      name: '书籍类型分布',
      type: 'pie',
      radius: ['50%', '70%'],
      center: ['55%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data: td.map(i => ({ name: i.btype, value: i.count })),
    }],
  })
}

function handleResize() {
  yearChart?.resize()
  typeChart?.resize()
}

function goBack() {
  router.push('/books')
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  yearChart?.dispose()
  typeChart?.dispose()
  yearChart = null
  typeChart = null
})
</script>

<style scoped lang="scss">
.book-chart-view {
  padding: 20px;
  background-color: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    .page-title { margin: 0; font-size: 22px; font-weight: 600; color: var(--el-text-color-primary); }
    .module-tag { font-size: 12px; }
  }
  .header-actions {
    display: flex;
    gap: 12px;
    align-items: center;
    .year-select { width: 130px; }
  }
}

.stats-section {
  margin-bottom: 20px;
  .stat-card {
    :deep(.el-card__body) { padding: 18px; }
    .stat-content { display: flex; align-items: center; gap: 14px;
      .stat-icon { width: 46px; height: 46px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
      .stat-info {
        .stat-value { font-size: 24px; font-weight: 600; line-height: 1; color: var(--el-text-color-primary); margin-bottom: 4px; }
        .stat-label { font-size: 13px; color: var(--el-text-color-regular); }
      }
    }
  }
}

.chart-row { margin-bottom: 20px;
  .chart-card {
    .card-header { display: flex; justify-content: space-between; align-items: center; gap: 8px;
      span { font-size: 15px; font-weight: 500; }
      .card-tip { font-size: 12px; font-weight: 400; color: var(--el-text-color-secondary); }
    }
    .chart-container { height: 380px; width: 100%; padding: 10px; }
  }
}

@media (max-width: 768px) {
  .page-header { flex-direction: column; align-items: stretch; gap: 16px; }
  .stats-section .el-row { flex-direction: column; .el-col { width: 100%; margin-bottom: 16px; } }
}
</style>
