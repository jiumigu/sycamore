<template>
  <div class="output-page">
    <div class="page-header">
      <h2>📊 个人良品率</h2>
      <el-tag size="small" type="info" effect="plain">把自我要求从道德问题变成质量管理问题</el-tag>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row" v-if="store.stats">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">总良品率</div>
          <div class="stat-main">
            <span class="stat-value" :class="yieldRateClass">{{ store.stats.yield_rate }}%</span>
          </div>
          <div class="stat-sub">
            良品 {{ store.stats.good_count }} / 总数 {{ store.stats.total_records }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">容错率（不良品）</div>
          <div class="stat-main">
            <span class="stat-value text-yellow">{{ store.stats.defect_rate }}%</span>
          </div>
          <div class="stat-sub">
            不良品 {{ store.stats.defective_count }} 件
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">废品率</div>
          <div class="stat-main">
            <span class="stat-value" :class="wasteRateClass">{{ store.stats.waste_rate }}%</span>
          </div>
          <div class="stat-sub">
            废品 {{ store.stats.waste_count }} 件
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 核心洞察 -->
    <el-card v-if="store.stats && store.stats.total_records > 0" shadow="hover" class="insight-card">
      <div class="insight-header">💡 核心洞察</div>
      <div class="insight-body">
        <p>
          你的良品率在 <strong>{{ store.stats.yield_rate }}%</strong>，
          意味着每 10 件事有 <strong>{{ 10 - Math.round(store.stats.yield_rate / 10) }}</strong> 件不完美
          — {{ insightMessage }}
        </p>
        <div v-if="Object.keys(store.stats.by_difficulty).length > 0" class="insight-detail">
          <span v-for="d in sortedDifficultyStats" :key="d.diff">
            难度{{ d.diff }}: <strong>{{ d.rate }}%</strong> ·
          </span>
          难度越高，良品率越低。
        </div>
      </div>
    </el-card>

    <!-- 月度趋势 -->
    <el-card v-if="store.stats && store.stats.monthly_trend.length > 0" shadow="hover" class="trend-card">
      <template #header>
        <div class="section-header">
          <span>📈 月度趋势</span>
        </div>
      </template>
      <div class="trend-bars">
        <div v-for="item in store.stats.monthly_trend" :key="item.month" class="trend-bar-item">
          <div class="trend-bar-label">{{ item.month?.slice(5) }}月</div>
          <div class="trend-bar-track">
            <div
              class="trend-bar-fill"
              :style="{ width: item.yield_rate + '%', background: barColor(item.yield_rate) }"
            />
          </div>
          <div class="trend-bar-value">{{ item.yield_rate }}%</div>
          <div class="trend-bar-count">({{ item.total }})</div>
        </div>
      </div>
    </el-card>

    <!-- 分类统计 -->
    <el-row :gutter="16" class="section-row">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="section-header">📋 按类别</div>
          </template>
          <div v-if="categoryStatsList.length === 0" class="empty-text">暂无数据</div>
          <div v-for="item in categoryStatsList" :key="item.code" class="stat-row-item">
            <div class="stat-row-label">{{ item.label }}</div>
            <div class="stat-row-bar">
              <div class="stat-row-fill" :style="{ width: item.yield_rate + '%' }" />
            </div>
            <div class="stat-row-value">{{ item.yield_rate }}%</div>
            <div class="stat-row-count">({{ item.good }}/{{ item.total }})</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="section-header">📊 按难度</div>
          </template>
          <div v-if="Object.keys(store.stats?.by_difficulty || {}).length === 0" class="empty-text">暂无数据</div>
          <div v-for="d in sortedDifficultyStats" :key="d.diff" class="stat-row-item">
            <div class="stat-row-label">难度{{ d.diff }}</div>
            <div class="stat-row-bar">
              <div class="stat-row-fill" :style="{ width: d.rate + '%' }" />
            </div>
            <div class="stat-row-value">{{ d.rate }}%</div>
            <div class="stat-row-count">({{ d.good }}/{{ d.total }})</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 产出记录列表 -->
    <el-card shadow="hover" class="records-card">
      <template #header>
        <div class="section-header">
          <span>📋 产出记录</span>
          <div class="header-actions">
            <el-select v-model="store.filterCategory" placeholder="类别" clearable size="small" style="width: 90px" @change="store.fetchRecords()">
              <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
            </el-select>
            <el-select v-model="store.filterQuality" placeholder="质量" clearable size="small" style="width: 90px" @change="store.fetchRecords()">
              <el-option v-for="q in QUALITY_OPTIONS" :key="q.value" :label="q.label" :value="q.value" />
            </el-select>
            <el-button type="primary" size="small" @click="handleAdd">+ 记录事项</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="store.loading" :data="store.records" style="width: 100%" empty-text="暂无记录">
        <el-table-column label="质量" width="80">
          <template #default="{ row }">
            <el-tag :type="qualityTagType(row.quality)" size="small">{{ row.quality_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="事项" min-width="160" show-overflow-tooltip />
        <el-table-column label="类别" width="70">
          <template #default="{ row }">{{ row.category_display }}</template>
        </el-table-column>
        <el-table-column label="难度" width="60" align="center">
          <template #default="{ row }">{{ row.difficulty }}</template>
        </el-table-column>
        <el-table-column label="失败类型" width="90" show-overflow-tooltip>
          <template #default="{ row }">{{ row.fail_type_display || '-' }}</template>
        </el-table-column>
        <el-table-column label="经验教训" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.lesson_learned || '-' }}</template>
        </el-table-column>
        <el-table-column label="日期" width="90">
          <template #default="{ row }">{{ row.occurred_at || row.created_at?.slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <OutputForm v-model:visible="formVisible" :record="editingRecord" @saved="formVisible = false" />
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, onMounted } from 'vue'
import { useOutputStore } from '../stores/outputStore'
import { CATEGORY_OPTIONS, QUALITY_OPTIONS } from '../types/outputTypes'
import type { OutputRecord } from '../types/outputTypes'
import OutputForm from '../components/OutputForm.vue'

const store = useOutputStore()

const formVisible = ref(false)
const editingRecord = ref<OutputRecord | null>(null)

const yieldRateClass = computed(() => {
  if (!store.stats) return ''
  const r = store.stats.yield_rate
  if (r >= 80) return 'text-green'
  if (r >= 60) return 'text-yellow'
  return 'text-red'
})

const wasteRateClass = computed(() => {
  if (!store.stats) return ''
  const r = store.stats.waste_rate
  if (r <= 5) return 'text-green'
  if (r <= 10) return 'text-yellow'
  return 'text-red'
})

const insightMessage = computed(() => {
  if (!store.stats) return ''
  const r = store.stats.yield_rate
  if (r >= 85) return '优秀的良品率，可以尝试更高难度的事。'
  if (r >= 70) return '健康的容错空间，适合稳步提升。'
  if (r >= 50) return '值得复盘一下不良品模式，找出改进方向。'
  return '可能有系统性问题，建议降低难度或改变方法。'
})

const categoryStatsList = computed(() => {
  if (!store.stats) return []
  return Object.entries(store.stats.by_category).map(([code, stat]) => ({
    code,
    label: stat.label,
    total: stat.total,
    good: stat.good,
    yield_rate: stat.yield_rate,
  }))
})

const sortedDifficultyStats = computed(() => {
  if (!store.stats) return []
  return Object.entries(store.stats.by_difficulty)
    .map(([diff, stat]) => ({
      diff: Number(diff),
      total: stat.total,
      good: stat.good,
      rate: stat.yield_rate,
    }))
    .sort((a, b) => a.diff - b.diff)
})

function qualityTagType(quality: string) {
  if (quality === 'good') return 'success'
  if (quality === 'defective') return 'warning'
  return 'danger'
}

function barColor(rate: number) {
  if (rate >= 80) return '#10B981'
  if (rate >= 60) return '#F59E0B'
  return '#EF4444'
}

function handleAdd() {
  editingRecord.value = null
  formVisible.value = true
}

function handleEdit(row: OutputRecord) {
  editingRecord.value = row
  formVisible.value = true
}

async function handleDelete(row: OutputRecord) {
  try {
    await ElMessageBox.confirm('确定删除这条记录吗？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await store.deleteRecord(row.id)
  } catch {
    // cancelled
  }
}

onMounted(() => {
  store.fetchAll()
})
</script>

<style scoped lang="scss">
.output-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;

  h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: #1F2937;
  }
}

.stats-row { margin-bottom: 16px; }

.stat-card {
  border: none;
  border-radius: 10px;
  :deep(.el-card__body) { padding: 16px; }
}

.stat-label {
  font-size: 12px;
  color: #6B7280;
  margin-bottom: 4px;
}

.stat-main {
  margin-bottom: 4px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
}

.stat-sub {
  font-size: 12px;
  color: #9CA3AF;
}

.text-green { color: #10B981; }
.text-yellow { color: #F59E0B; }
.text-red { color: #EF4444; }

.insight-card {
  margin-bottom: 16px;
  border: none;
  border-radius: 10px;
  :deep(.el-card__body) { padding: 16px 20px; }
}

.insight-header {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.insight-body {
  font-size: 13px;
  color: #4B5563;
  line-height: 1.6;

  p { margin: 0; }
}

.insight-detail {
  margin-top: 6px;
  color: #9CA3AF;
  font-size: 12px;

  strong { color: #6B7280; }
}

.trend-card {
  margin-bottom: 16px;
  border: none;
  border-radius: 10px;
}

.trend-bars {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.trend-bar-item {
  flex: 1;
  min-width: 50px;
  text-align: center;
}

.trend-bar-label {
  font-size: 11px;
  color: #6B7280;
  margin-bottom: 4px;
}

.trend-bar-track {
  height: 60px;
  background: #F3F4F6;
  border-radius: 4px;
  position: relative;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}

.trend-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
  min-width: 2px;
}

.trend-bar-value {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  margin-top: 2px;
}

.trend-bar-count {
  font-size: 10px;
  color: #9CA3AF;
}

.section-row {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.stat-row-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}

.stat-row-label {
  width: 60px;
  flex-shrink: 0;
  color: #374151;
}

.stat-row-bar {
  flex: 1;
  height: 8px;
  background: #F3F4F6;
  border-radius: 4px;
  overflow: hidden;
}

.stat-row-fill {
  height: 100%;
  background: #10B981;
  border-radius: 4px;
  transition: width 0.3s;
}

.stat-row-value {
  width: 40px;
  text-align: right;
  font-weight: 600;
  color: #374151;
}

.stat-row-count {
  width: 60px;
  text-align: right;
  font-size: 11px;
  color: #9CA3AF;
}

.empty-text {
  font-size: 13px;
  color: #9CA3AF;
  padding: 12px 0;
  text-align: center;
}

.records-card {
  border: none;
  border-radius: 10px;
}
</style>
