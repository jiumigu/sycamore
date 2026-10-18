<template>
  <div class="health-overview">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <el-button size="small" @click="$router.push('/health')">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <h2 class="page-title">🏃 生命步数总览</h2>
        <el-tag size="small" type="success">长期视图</el-tag>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="$router.push('/health/contrib')">📊 贡献图</el-button>
        <el-button size="small" :loading="refreshing" @click="refresh">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- 超大进度条 -->
    <el-card class="section-card progress-card" v-loading="loading && !store.summary">
      <div class="progress-header">
        <div class="progress-title">
          目标：在有限生命中走完 <strong>{{ (TARGET_STEPS / 10000).toLocaleString() }} 万步</strong>
          （{{ formatNumber(TARGET_STEPS) }}步）
        </div>
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
              v-for="i in totalMilestones"
              :key="i"
              class="milestone-dot"
              :class="{
                completed: store.summary && i <= store.summary.completed_milestones,
                current: store.summary && i === store.summary.completed_milestones + 1,
              }"
              :style="{ left: (i / totalMilestones * 100) + '%' }"
              :title="`第${i}个里程碑 (${formatNumber((i - 1) * MILESTONE_SIZE)} - ${formatNumber(i * MILESTONE_SIZE)}步)`"
            ></div>
          </div>
        </div>
      </div>
      <div class="progress-info" v-if="store.summary && store.summary.current_milestone">
        当前里程碑：第{{ store.summary.current_milestone.number }}个
        （{{ formatNumber(store.summary.current_milestone.start) }} -
        {{ formatNumber(store.summary.current_milestone.end) }}步）
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

    <!-- 里程碑地图（完整 50 格，点格子看详情） -->
    <el-card class="section-card" v-loading="loading && !store.milestones">
      <template #header>
        <div class="section-header">
          <span>
            🎯 里程碑地图
            <em class="section-sub">
              每 {{ formatNumber(MILESTONE_SIZE) }} 步一个 · 共 {{ milestoneList.length }} 个
            </em>
          </span>
          <div class="legend">
            <span class="legend-item"><span class="dot completed"></span> 已完成</span>
            <span class="legend-item"><span class="dot current"></span> 当前</span>
            <span class="legend-item"><span class="dot pending"></span> 未完成</span>
          </div>
        </div>
      </template>

      <div class="milestone-grid" v-if="milestoneList.length">
        <div
          v-for="m in milestoneList"
          :key="m.number"
          class="milestone-cell"
          :class="{ completed: m.is_completed, current: m.is_current }"
          @click="selectMilestone(m)"
        >
          <div class="cell-icon">{{ m.is_completed ? '🏆' : m.is_current ? '🌟' : '📍' }}</div>
          <div class="cell-number">第{{ m.number }}个</div>
          <div class="cell-range">{{ formatNumber(m.start) }} - {{ formatNumber(m.end) }}</div>
          <div v-if="m.is_current && !m.is_completed" class="cell-progress">
            <div class="cell-progress-bar">
              <div class="cell-progress-fill" :style="{ width: Math.min(m.progress_percent || 0, 100) + '%' }"></div>
            </div>
            <div class="cell-progress-text">{{ (m.progress_percent || 0).toFixed(1) }}%</div>
          </div>
        </div>
      </div>
      <el-empty v-else-if="!loading" description="暂无里程碑数据" />
    </el-card>

    <!-- 年度步数对比 -->
    <el-card class="section-card" v-loading="loading && !store.yearlyComparison.length">
      <template #header><span>📊 年度步数对比</span></template>
      <!-- 🔴 图表容器必须**先有高度**再 `echarts.init`，否则拿到 0 高、画不出东西
           （这正是「有数据但图是空的」最常见的成因）。 -->
      <div ref="yearlyChartRef" class="chart-box"></div>
      <el-empty v-if="!store.yearlyComparison.length && !loading" description="暂无年度数据" />
    </el-card>

    <!-- 里程碑详情弹窗 -->
    <el-dialog v-model="detailVisible" title="里程碑详情" width="400px">
      <template v-if="selectedMilestone">
        <div class="detail-content">
          <div class="detail-icon">{{ selectedMilestone.is_completed ? '🏆' : selectedMilestone.is_current ? '🌟' : '📍' }}</div>
          <h2 class="detail-title">第{{ selectedMilestone.number }}个里程碑</h2>
          <div class="detail-range">
            {{ formatNumber(selectedMilestone.start) }} →
            {{ formatNumber(selectedMilestone.end) }}
          </div>

          <el-divider />

          <div class="detail-info">
            <div class="info-row">
              <span class="info-label">状态</span>
              <span class="info-value">
                <el-tag v-if="selectedMilestone.is_completed" type="success" effect="dark">已完成</el-tag>
                <el-tag v-else-if="selectedMilestone.is_current" type="warning" effect="dark">进行中</el-tag>
                <el-tag v-else type="info" effect="plain">未开始</el-tag>
              </span>
            </div>

            <div v-if="selectedMilestone.is_completed && selectedMilestone.completed_date" class="info-row">
              <span class="info-label">达成日期</span>
              <span class="info-value">{{ selectedMilestone.completed_date }}</span>
            </div>

            <div v-if="selectedMilestone.is_completed && selectedMilestone.days_taken" class="info-row">
              <span class="info-label">耗时</span>
              <span class="info-value">{{ selectedMilestone.days_taken }} 天</span>
            </div>

            <div v-if="selectedMilestone.is_current && !selectedMilestone.is_completed" class="info-row">
              <span class="info-label">当前进度</span>
              <span class="info-value">
                {{ formatNumber(selectedMilestone.current_progress || 0) }} /
                {{ formatNumber(selectedMilestone.end - selectedMilestone.start) }}
              </span>
            </div>

            <div v-if="selectedMilestone.is_current && !selectedMilestone.is_completed" class="info-row">
              <span class="info-label">还需</span>
              <span class="info-value">
                {{ formatNumber((selectedMilestone.end - selectedMilestone.start) - (selectedMilestone.current_progress || 0)) }} 步
              </span>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ArrowLeft, Refresh, Star, TrendCharts, Calendar, Medal } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { useHealthStore } from '../../stores/healthStore'
import { MILESTONE_SIZE, TARGET_STEPS, TOTAL_MILESTONES } from '../../types/healthTypes'
import type { MilestoneItem } from '../../types/healthTypes'

const store = useHealthStore()

const loading = ref(false)
const refreshing = ref(false)
const totalMilestones = TOTAL_MILESTONES

const milestoneList = computed(() => store.milestones?.milestones || [])

// 统计卡片
// ⚠️ `icon` 存的是**组件本身**，不是字符串：`:is="'Star'"` 只有在图标被全局注册时才解析得出来，
//    本项目没做全局注册 ⇒ 写字符串等于不显示（卡片只剩一块底色方块）。
const statCards = computed(() => {
  const s = store.summary
  if (!s) return []
  return [
    { key: 'total', label: '累计步数', value: formatNumber(s.total_steps), icon: Star, bg: '#fff7e6', color: '#fa8c16' },
    { key: 'milestone', label: '里程碑', value: `${s.completed_milestones}/${s.total_milestones}`, icon: Medal, bg: '#f0fff0', color: '#52c41a' },
    { key: 'daily', label: '日均步数', value: formatNumber(s.daily_avg), icon: TrendCharts, bg: '#e6f7ff', color: '#1890ff' },
    { key: 'predict', label: s.prediction ? '预估完成' : '运动天数', value: s.prediction ? s.prediction.target_date : `${s.days_active}天`, icon: Calendar, bg: '#fff0f6', color: '#eb2f96' },
  ]
})

// 里程碑详情
const detailVisible = ref(false)
const selectedMilestone = ref<MilestoneItem | null>(null)

function selectMilestone(m: MilestoneItem) {
  selectedMilestone.value = m
  detailVisible.value = true
}

// 年度对比图
const yearlyChartRef = ref<HTMLElement>()
let yearlyChart: echarts.ECharts | null = null

function formatNumber(n: number | undefined | null): string {
  if (n === undefined || n === null) return '0'
  if (n >= 100000000) return (n / 100000000).toFixed(2) + '亿'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
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
    yAxis: {
      type: 'value', name: '步数',
      axisLabel: {
        formatter: (v: number) => v >= 100000000 ? (v / 100000000).toFixed(1) + '亿' : v >= 10000 ? (v / 10000).toFixed(0) + '万' : v,
      },
    },
    series: [{
      type: 'bar', data: steps, barWidth: '50%',
      itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] },
      label: {
        show: true, position: 'top', fontSize: 10,
        formatter: (p: any) => p.value >= 100000000 ? (p.value / 100000000).toFixed(1) + '亿' : p.value >= 10000 ? (p.value / 10000).toFixed(0) + '万' : p.value,
      },
    }],
  })
  yearlyChart.resize()
}

function handleResize() {
  yearlyChart?.resize()
}

async function loadData() {
  loading.value = true
  try {
    // 只取总览需要的三件事：进度条 / 里程碑地图 / 年度对比。
    // 🔴 这里**不要**顺手把记录列表也取了 —— 它归首页，两页各取所需。
    await store.fetchOverview()
  } finally {
    loading.value = false
  }
  await nextTick()
  initYearlyChart()
}

async function refresh() {
  refreshing.value = true
  try {
    await loadData()
  } finally {
    refreshing.value = false
  }
}

// 🔴 数据可能在别处（首页）被刷新过 ⇒ 不能在 `onMounted` 那一次画完就完事。
//    依赖异步数据的组件只认「数据到达」这个时机（深链 / 刷新进本页时，
//    `onMounted` 那一刻数据往往还没到 —— 画出来就是一张空图）。
watch(() => store.yearlyComparison, () => nextTick(initYearlyChart), { deep: true })

onMounted(async () => {
  window.addEventListener('resize', handleResize)
  await loadData()
})

onBeforeUnmount(() => {
  // 本页是**来回进出的子页**（不像以前那块常驻首页），必须自己收尾：
  // 否则每进出一次就多一个 ECharts 实例与一个 window resize 监听。
  window.removeEventListener('resize', handleResize)
  yearlyChart?.dispose()
  yearlyChart = null
})
</script>

<style scoped lang="scss">
.health-overview {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    .header-left { display: flex; align-items: center; gap: 12px;
      .page-title { margin: 0; font-size: 22px; font-weight: 600; color: #1F2937; }
    }
    .header-actions { display: flex; gap: 8px; align-items: center; }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
    .section-header { display: flex; justify-content: space-between; align-items: center;
      .section-sub { font-style: normal; font-size: 12px; font-weight: 400; color: #909399; margin-left: 6px; }
    }
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

  .chart-box { height: 280px; width: 100%; }

  .milestone-grid {
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: 8px;
    padding: 8px;

    .milestone-cell {
      border: 1px solid #e8e8e8;
      border-radius: 8px;
      padding: 8px 4px;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s;
      background: #fafafa;

      &.completed { background: #f6ffed; border-color: #b7eb8f;
        .cell-icon { font-size: 20px; }
        .cell-number { color: #52c41a; font-weight: 600; }
        .cell-range { color: #73d13d; }
      }
      &.current { background: #fffbe6; border-color: #ffe58f; border-width: 2px; box-shadow: 0 0 8px rgba(250,173,20,0.3);
        .cell-icon { font-size: 22px; }
        .cell-number { color: #fa8c16; font-weight: 600; }
        .cell-range { color: #faad14; }
      }
      &:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }

      .cell-icon { font-size: 18px; margin-bottom: 4px; }
      .cell-number { font-size: 12px; color: #606266; }
      .cell-range { font-size: 10px; color: #bfbfbf; margin-top: 2px; }

      .cell-progress { margin-top: 6px;
        .cell-progress-bar { height: 4px; background: #f0f0f0; border-radius: 2px; overflow: hidden;
          .cell-progress-fill { height: 100%; background: linear-gradient(90deg, #faad14, #fa8c16); border-radius: 2px; transition: width 0.5s; }
        }
        .cell-progress-text { font-size: 10px; color: #fa8c16; margin-top: 2px; }
      }
    }
  }

  .legend { display: flex; gap: 16px;
    .legend-item { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px;
      .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%;
        &.completed { background: #52c41a; }
        &.current { background: #fa8c16; box-shadow: 0 0 4px rgba(250,140,22,0.5); }
        &.pending { background: #d9d9d9; }
      }
    }
  }
}

.detail-content {
  text-align: center;
  .detail-icon { font-size: 48px; margin-bottom: 8px; }
  .detail-title { font-size: 20px; font-weight: 600; color: #1F2937; margin: 0 0 4px; }
  .detail-range { font-size: 14px; color: #909399; }

  .detail-info { text-align: left;
    .info-row { display: flex; justify-content: space-between; padding: 8px 0; align-items: center;
      .info-label { font-size: 13px; color: #909399; }
      .info-value { font-size: 14px; color: #1F2937; font-weight: 500; }
    }
  }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 6px rgba(250,140,22,0.4); }
  50% { box-shadow: 0 0 12px rgba(250,140,22,0.8); }
}
</style>
