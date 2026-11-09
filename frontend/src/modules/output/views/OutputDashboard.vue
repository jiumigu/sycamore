<template>
  <div class="output-page">
    <!-- 归档提示（仅在当前仍处于归档状态时显示，重新启用后自动消失） -->
    <el-alert v-if="ready && isArchived" title="此模块已归档，随时可重新启用" type="info" show-icon :closable="false" class="archive-banner" />

    <div class="page-header">
      <h2>📊 个人良品率</h2>
      <el-tag size="small" type="info" effect="plain">把自我要求从道德问题变成质量管理问题</el-tag>
    </div>

    <!-- 工具条：窗口是**看得见的选择**（以前它藏在 store 里，界面上没有任何痕迹） -->
    <div class="toolbar">
      <el-radio-group :model-value="store.window" size="small" @change="onWindowChange">
        <el-radio-button v-for="w in WINDOW_OPTIONS" :key="w.value" :value="w.value">
          {{ w.label }}
        </el-radio-button>
      </el-radio-group>
      <div class="toolbar-right">
        <!-- 未填日期的记录进不了任何按日期过滤的口径 —— 必须说出来，不能让它静默消失 -->
        <span v-if="undatedNote" class="undated-note">{{ undatedNote }}</span>
        <el-button type="primary" size="small" @click="handleAdd">+ 记一件事</el-button>
      </div>
    </div>

    <!-- 第一屏：一句话说清这段时间发生了什么（不再是「你 X 分」） -->
    <div class="summary">
      <p class="summary-text">{{ summaryText }}</p>
      <p v-if="summarySub" class="summary-sub">{{ summarySub }}</p>
    </div>

    <!-- 三张卡：件数 / 没达到预期 / 最常见原因（第三张才是出口） -->
    <el-row v-if="store.stats" :gutter="16" class="stats-row">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">记了几件</div>
          <div class="stat-main">
            <span class="stat-value">{{ store.stats.total_records }}</span>
            <span class="stat-unit">件</span>
          </div>
          <div class="stat-sub">{{ windowLabel }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">没达到预期</div>
          <div class="stat-main">
            <span class="stat-value text-yellow">{{ store.stats.redo_count }}</span>
            <span class="stat-unit">件</span>
          </div>
          <div class="stat-sub">
            {{ store.stats.sample_enough ? `占 ${redoRate}%` : `样本不足 ${store.stats.min_sample} 件，不报比例` }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">最常见的原因</div>
          <div class="stat-main">
            <span class="stat-value stat-value-text">{{ store.stats.top_fail_type?.label ?? '—' }}</span>
          </div>
          <div class="stat-sub">
            {{ store.stats.top_fail_type ? `${store.stats.top_fail_type.count} 次` : '还没填过失败类型' }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 失败类型分布：这一页唯一能指导下一步的东西 -->
    <el-card v-if="store.stats && store.stats.redo_count > 0" shadow="hover" class="section-card">
      <template #header>
        <div class="section-header">
          <span>没达到预期的，都是什么原因</span>
          <span class="header-hint" v-if="store.stats.fail_type_missing > 0">
            另有 {{ store.stats.fail_type_missing }} 件没填类型
          </span>
        </div>
      </template>
      <div
        v-for="f in store.stats.by_fail_type"
        :key="f.value"
        class="stat-row-item"
      >
        <div class="stat-row-label">{{ f.label }}</div>
        <div class="stat-row-bar">
          <div class="stat-row-fill" :style="{ width: failWidth(f.count) }" />
        </div>
        <div class="stat-row-count">{{ f.count }} 件</div>
      </div>
      <div v-if="store.stats.by_fail_type.length === 0" class="empty-text">
        都没填失败类型 —— 下次记录时补一下，这里才能看出「该改什么」
      </div>
    </el-card>

    <!-- 按类别 -->
    <el-card shadow="hover" class="section-card">
      <template #header>
        <div class="section-header"><span>按类别</span></div>
      </template>
      <div v-if="categoryStatsList.length === 0" class="empty-text">这个窗口里没有记录</div>
      <div v-for="item in categoryStatsList" :key="item.code" class="stat-row-item">
        <div class="stat-row-label">{{ item.label }}</div>
        <div class="stat-row-bar">
          <div class="stat-row-fill" :style="{ width: item.yield_rate + '%' }" />
        </div>
        <!-- 显示「几件里成了几件」而不是百分比：单类只有 1~2 件时，百分比没有意义 -->
        <div class="stat-row-count">{{ item.good }}/{{ item.total }} 件</div>
      </div>
    </el-card>

    <!-- 月度趋势：只有 2 个月以上才画（单月没有「趋势」可言） -->
    <el-card v-if="showTrend" shadow="hover" class="section-card">
      <template #header>
        <div class="section-header">
          <span>📈 月度良品率</span>
          <span class="header-hint">良品 ÷ 当月记录数</span>
        </div>
      </template>
      <div class="trend-bars">
        <div v-for="item in store.stats?.monthly_trend" :key="item.month" class="trend-bar-item">
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

    <!-- 产出记录列表 -->
    <el-card class="section-card records-card">
      <template #header>
        <div class="section-header">
          <span>📋 记录 · 共 {{ store.total }} 条</span>
          <div class="header-actions">
            <el-select v-model="store.filterCategory" placeholder="类别" clearable size="small" style="width: 90px" @change="applyFilter">
              <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
            </el-select>
            <el-select v-model="store.filterQuality" placeholder="结果" clearable size="small" style="width: 90px" @change="applyFilter">
              <el-option v-for="q in QUALITY_OPTIONS" :key="q.value" :label="q.label" :value="q.value" />
            </el-select>
          </div>
        </div>
      </template>

      <div class="output-table">
        <el-table v-loading="store.loading" :data="store.records" style="width: 100%" empty-text="这个窗口里没有记录">
          <el-table-column label="结果" width="86">
            <template #default="{ row }">
              <el-tag :type="qualityTagType(row.quality)" size="small">{{ row.quality_display }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="事项" min-width="200" show-overflow-tooltip />
          <el-table-column label="类别" width="70">
            <template #default="{ row }">{{ row.category_display }}</template>
          </el-table-column>
          <el-table-column label="失败类型" width="96" show-overflow-tooltip>
            <template #default="{ row }">{{ row.fail_type_display || '-' }}</template>
          </el-table-column>
          <el-table-column label="下次改什么" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.lesson_learned || '-' }}</template>
          </el-table-column>
          <el-table-column label="发生日期" width="110">
            <template #default="{ row }">
              <span style="white-space: nowrap;">{{ row.occurred_at || '未填' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" align="center">
            <template #default="{ row }">
              <el-button size="small" @click="handleEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <el-pagination
        v-if="store.total > 0"
        class="records-pager"
        :current-page="store.page"
        :page-size="store.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="store.total"
        layout="sizes, prev, pager, next"
        background
        small
        @current-change="store.goPage"
        @size-change="store.changePageSize"
      />
    </el-card>

    <OutputForm v-model:visible="formVisible" :record="editingRecord" @saved="formVisible = false" />
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, onMounted } from 'vue'
import { useOutputStore } from '../stores/outputStore'
import { CATEGORY_OPTIONS, QUALITY_OPTIONS, WINDOW_OPTIONS } from '../types/outputTypes'
import type { OutputRecord, OutputWindow } from '../types/outputTypes'
import OutputForm from '../components/OutputForm.vue'
import { useMenuArchive } from '@/shared/composables/useMenuArchive'

// 归档横幅的判据唯一实现在 useMenuArchive（存档态含用户偏好，非写死的 defaultArchived）
const { ready, isArchived } = useMenuArchive('output')

const store = useOutputStore()

const formVisible = ref(false)
const editingRecord = ref<OutputRecord | null>(null)

const windowLabel = computed(
  () => WINDOW_OPTIONS.find(w => w.value === store.window)?.label ?? '',
)

const redoRate = computed(() => {
  const s = store.stats
  if (!s || !s.total_records) return '0'
  return ((s.redo_count / s.total_records) * 100).toFixed(0)
})

/** 未填发生日期的记录：进不了任何按日期过滤的窗口，界面上要说清楚 */
const undatedNote = computed(() => {
  const s = store.stats
  if (!s || !s.undated_count) return ''
  return store.window === 'all'
    ? `含 ${s.undated_count} 条未填日期（不进趋势图）`
    : `另有 ${s.undated_count} 条未填日期，不在${windowLabel.value}里`
})

/** 第一屏那句话：说事实，不打分。 */
const summaryText = computed(() => {
  const s = store.stats
  if (!s) return '统计没取到，下面只有明细。'
  if (s.total_records === 0) return `${windowLabel.value}没有记录。`
  const head = `${windowLabel.value}记了 ${s.total_records} 件，其中 ${s.redo_count} 件没达到预期`
  if (!s.sample_enough) {
    return `${head} —— 样本还不够看比例（满 ${s.min_sample} 件才算）。`
  }
  if (s.top_fail_type) {
    return `${head}；最常见的原因：${s.top_fail_type.label}（${s.top_fail_type.count} 次）。`
  }
  return `${head}。`
})

const summarySub = computed(() => {
  const s = store.stats
  if (!s) return ''
  if (s.total_records === 0) {
    return store.window === '30d'
      ? '切到「全部」能看历史；或者现在就记一件。'
      : '换个窗口看看，或者现在就记一件。'
  }
  if (!s.sample_enough) return `先记满 ${s.min_sample} 件，再看哪种原因最多。`
  if (s.top_fail_type) return '下次遇到同类事情之前，先看一眼这条。'
  return ''
})

const categoryStatsList = computed(() => {
  if (!store.stats) return []
  return Object.entries(store.stats.by_category)
    .map(([code, stat]) => ({
      code,
      label: stat.label,
      total: stat.total,
      good: stat.good,
      yield_rate: stat.yield_rate,
    }))
    .sort((a, b) => b.total - a.total)
})

const showTrend = computed(() => (store.stats?.monthly_trend.length ?? 0) >= 2)

function failWidth(count: number) {
  const list = store.stats?.by_fail_type ?? []
  const max = Math.max(...list.map(f => f.count), 1)
  return `${(count / max) * 100}%`
}

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

function onWindowChange(v: string | number | boolean) {
  store.setWindow(v as OutputWindow)
}

/** 换筛选 ⇒ 回第 1 页重取（旧页码在新条件下没有意义） */
function applyFilter() {
  store.reload()
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
    await ElMessageBox.confirm(
      `确定删除「${row.title}」吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      },
    )
    await store.deleteRecord(row.id)
    ElMessage.success('已删除')
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;

  h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: #1F2937;
  }
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.undated-note {
  font-size: 12px;
  color: #9CA3AF;
}

.summary {
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 10px;
  padding: 14px 18px;
  margin-bottom: 16px;
}

.summary-text {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1F2937;
  line-height: 1.6;
}

.summary-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6B7280;
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
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1F2937;
}

.stat-value-text {
  font-size: 22px;
}

.stat-unit {
  font-size: 13px;
  color: #9CA3AF;
}

.stat-sub {
  font-size: 12px;
  color: #9CA3AF;
}

.text-yellow { color: #F59E0B; }

.section-card {
  margin-bottom: 16px;
  border: none;
  border-radius: 10px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.header-hint {
  font-size: 12px;
  font-weight: 400;
  color: #9CA3AF;
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
  width: 80px;
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

.stat-row-count {
  width: 66px;
  text-align: right;
  font-size: 11px;
  color: #9CA3AF;
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

.output-table {
  width: 100%;
  overflow-x: auto;

  :deep(.el-table__fixed-right) {
    right: 0;
    overflow: visible;
  }
}

.records-pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
