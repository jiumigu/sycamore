<template>
  <div class="relation-dashboard">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">🤝 关系管理</h1>
        <el-tag type="warning" class="module-tag">连接与足迹</el-tag>
      </div>
      <div class="header-actions">
        <el-input v-model="searchText" placeholder="搜索姓名/标签..." clearable style="width:200px" @input="onSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-radio-group v-model="filterQuality" @change="onFilterChange" size="small">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="nourishing">🌱 滋养型</el-radio-button>
          <el-radio-button value="neutral">⚪ 中性</el-radio-button>
          <el-radio-button value="draining">⚡ 消耗型</el-radio-button>
          <el-radio-button value="toxic">⚠️ 有害型</el-radio-button>
        </el-radio-group>
        <el-select v-model="filterStatus" placeholder="状态筛选" clearable size="default" style="width:110px" @change="onFilterChange">
          <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="filterYear" placeholder="选择年份" clearable size="default" style="width:110px" @change="onFilterChange">
          <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="String(y)" />
        </el-select>
        <el-select v-model="filterLocation" placeholder="认识地点" clearable size="default" style="width:130px" @change="onFilterChange">
          <el-option v-for="loc in locationOptions" :key="loc" :label="loc" :value="loc" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 添加关系
        </el-button>
        <el-button @click="refreshAll">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- 隐私模式提示条 -->
    <div v-if="privacyStore.privacyMode" class="privacy-banner">
      🔒 隐私模式 — 姓名、标签、地点等信息已脱敏
    </div>

    <!-- Tabs 切换 -->
    <el-tabs v-model="activeTab" class="main-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="💬 关系列表" name="list">
        <!-- 统计卡片 -->
        <div class="stats-section">
          <div class="total-stat">共计 <strong>{{ store.overview?.total_relationships || 0 }}</strong> 个关系 · 累计能量 <strong>{{ store.overview?.total_energy > 0 ? '+' : '' }}{{ store.overview?.total_energy || 0 }}</strong></div>
          <el-row :gutter="12" class="stats-row">
            <el-col :span="6" v-for="card in statCards" :key="card.key">
              <el-card class="stat-card" :class="'stat-' + card.key" shadow="hover" @click="filterByType(card.key)">
                <div class="stat-label">{{ card.label }}</div>
                <div class="stat-value">{{ card.value }}</div>
              </el-card>
            </el-col>
          </el-row>
        </div>

        <!-- 待提醒列表 -->
        <el-card class="section-card" v-if="store.dueReminders.length">
          <template #header>
            <div class="section-header">
              <span>⏰ 待跟进提醒</span>
            </div>
          </template>
          <div class="reminder-list">
            <div v-for="r in store.dueReminders" :key="r.id" class="reminder-item" @click="$router.push(`/relation/${r.id}`)">
              <div class="reminder-dot" :style="{ background: QUALITY_CONFIG[r.quality]?.color || '#9CA3AF' }"></div>
              <div class="reminder-info">
                <span class="reminder-name">{{ maskName(r.name, privacyStore.privacyMode) }}</span>
                <span class="reminder-tags" v-if="r.tags">{{ privacyStore.privacyMode ? '***' : r.tags }}</span>
              </div>
              <div class="reminder-meta">
                <span v-if="r.days_since !== null" class="reminder-days">{{ r.days_since }}天未联系</span>
                <span v-else class="reminder-days">尚未互动</span>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 关系列表 -->
        <el-card class="section-card">
          <template #header>
            <div class="section-header">
              <span>👥 关系档案（{{ store.totalCount }}）</span>
            </div>
          </template>

          <div v-loading="store.loading" class="relation-grid">
            <div v-for="r in filteredRelationships" :key="r.id" class="relation-card" @click="$router.push(`/relation/${r.id}`)">
              <div class="card-top">
                <div class="avatar" :style="{ background: store.overview ? qualityGradient(r.relation_type) : '#e5e7eb' }">
                  {{ r.name.charAt(0) }}
                </div>
                <div class="card-meta">
                  <div class="relation-name">{{ maskName(r.name, privacyStore.privacyMode) }}</div>
                  <div class="relation-tags" v-if="r.tags">
                    <el-tag v-for="tag in r.tags.split(/[,，、]/).filter(Boolean).slice(0, 3)" :key="tag" size="small" round>{{ privacyStore.privacyMode ? '***' : tag.trim() }}</el-tag>
                  </div>
                </div>
                <el-tag :type="relationTagType(r.relation_type)" effect="dark" size="small" class="quality-tag">{{ relationTypeLabel(r.relation_type) }}</el-tag>
              </div>

              <div class="card-body">
                <div class="info-row" v-if="r.last_interaction">
                  <span class="info-label">最近互动</span>
                  <span class="info-value">{{ formatTime(r.last_interaction) }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">互动次数</span>
                  <span class="info-value">{{ r.interaction_count }}</span>
                </div>
                <div class="info-row" v-if="r.avg_energy !== null && r.avg_energy !== undefined">
                  <span class="info-label">平均能量</span>
                  <span class="info-value" :style="{ color: r.avg_energy >= 0 ? '#10B981' : '#EF4444' }">
                    {{ r.avg_energy > 0 ? '+' : '' }}{{ r.avg_energy }} 分/次
                  </span>
                </div>
              </div>

              <div class="card-footer">
                <el-tag :type="statusTagType(r.current_status)" size="small" effect="plain">
                  {{ statusLabel(r.current_status) }}
                </el-tag>
                <el-button size="small" text @click.stop="$router.push(`/relation/${r.id}`)">详情 →</el-button>
              </div>
            </div>
            <el-empty v-if="!store.loading && filteredRelationships.length === 0" description="暂无关系记录" />
          </div>

          <el-pagination
            v-if="store.totalCount > 0"
            v-model:current-page="store.currentPage"
            :page-size="store.pageSize"
            :total="store.totalCount"
            layout="prev, pager, next"
            small
            class="pagination"
            @current-change="onPageChange"
          />
        </el-card>
      </el-tab-pane>

      <!-- 认识地点分析 Tab -->
      <el-tab-pane label="📊 认识地点分析" name="location">
        <el-card class="section-card">
          <template #header><span>📍 认识地点分析图</span></template>
          <LocationBubbleChart
            :locations="locationData.locations"
            :loading="locationLoading"
          />
        </el-card>

        <el-card class="section-card" v-if="locationData.summary">
          <template #header><span>📊 统计摘要</span></template>
          <LocationStatsSummary :summary="locationData.summary" />
        </el-card>

        <el-card class="section-card" v-if="locationData.locations.length">
          <template #header><span>📋 地点详情列表</span></template>
          <LocationStatsTable
            :locations="locationData.locations"
            :loading="locationLoading"
          />
        </el-card>
      </el-tab-pane>

      <!-- 读者群体 Tab -->
      <el-tab-pane label="👥 读者群体" name="readers">
        <ReaderList />
      </el-tab-pane>

      <!-- 月末盘点 Tab -->
      <el-tab-pane label="📊 月末盘点" name="monthly-summary">
        <MonthlySummaryTab />
      </el-tab-pane>
    </el-tabs>

    <!-- 添加/编辑关系弹窗 -->
    <el-dialog v-model="formVisible" :title="isEdit ? '编辑关系' : '🤝 添加关系'" width="560px" @close="resetForm">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="formData.name" placeholder="姓名/昵称" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="别名">
              <el-input v-model="formData.alias" placeholder="曾用名/绰号" maxlength="200" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="认识时间">
              <el-date-picker v-model="formData.met_date" type="date" placeholder="选择日期"
                format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width:100%" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="认识地点">
              <el-input v-model="formData.met_place" placeholder="地点" maxlength="200" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="认识场景">
          <el-input v-model="formData.met_scene" type="textarea" :rows="2" placeholder="曾经如何相识..." maxlength="500" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="当时身份">
              <el-input v-model="formData.identity_then" placeholder="同学/同事/网友..." maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="当前状态" prop="current_status">
              <el-select v-model="formData.current_status" style="width:100%">
                <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="他能给我">
              <el-input v-model="formData.they_give_me" type="textarea" :rows="2" placeholder="情感支持/信息/陪伴..." maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="我能给他">
              <el-input v-model="formData.i_give_them" type="textarea" :rows="2" placeholder="倾听/帮助/鼓励..." maxlength="500" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="标签">
          <el-input v-model="formData.tags" placeholder="逗号分隔，如：大学同学, 室友, 篮球" maxlength="200" />
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="formData.notes" type="textarea" :rows="2" placeholder="..." maxlength="500" />
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { maskName } from '@/shared/utils/privacy'
import ReaderList from '../components/ReaderList.vue'
import MonthlySummaryTab from '../components/reader/MonthlySummaryTab.vue'
import { useRelationshipStore } from '../stores/relationshipStore'
import { useReaderStore } from '../stores/readerStore'
import { QUALITY_CONFIG, STATUS_OPTIONS, RELATION_TYPE_LABELS, RELATION_TYPE_TAG } from '../types/relationshipTypes'
import type { Relationship, LocationStatsData } from '../types/relationshipTypes'
import * as api from '../api/relationshipApi'
import LocationBubbleChart from '../components/LocationBubbleChart.vue'
import LocationStatsSummary from '../components/LocationStatsSummary.vue'
import LocationStatsTable from '../components/LocationStatsTable.vue'

import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'

const store = useRelationshipStore()
const readerStore = useReaderStore()
const privacyStore = usePrivacyStore()

// Tabs
const activeTab = ref('list')
const locationData = ref<LocationStatsData>({ locations: [], summary: { total_locations: 0, total_people: 0, best_location: null, best_nourishing_rate: 0 } })
const locationLoading = ref(false)

async function loadLocationStats() {
  locationLoading.value = true
  try {
    const res = await api.getLocationStats()
    locationData.value = res.data
  } finally {
    locationLoading.value = false
  }
}

function handleTabChange(name: string) {
  if (name === 'location') {
    loadLocationStats()
  } else if (name === 'readers') {
    readerStore.fetchAll()
  } else if (name === 'monthly-summary') {
    readerStore.fetchMonthlySummaries()
    readerStore.fetchYearlyStats()
  }
}

// Filters
const searchText = ref('')
const filterQuality = ref('')
const filterStatus = ref('')
const filterYear = ref('')
const filterLocation = ref('')
const locationOptions = ref<string[]>([])

const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: 10 }, (_, i) => currentYear - i)

const filteredRelationships = computed(() => store.relationships)

function buildFilterParams() {
  const params: Record<string, unknown> = {}
  if (filterQuality.value) params.type = filterQuality.value
  if (filterStatus.value) params.status = filterStatus.value
  if (filterYear.value) params.year = filterYear.value
  if (filterLocation.value) params.location = filterLocation.value
  if (searchText.value.trim()) params.search = searchText.value.trim()
  return params
}

function onSearch() {
  store.currentPage = 1
  store.fetchRelationships(buildFilterParams())
}

function onFilterChange() {
  store.currentPage = 1
  store.fetchRelationships(buildFilterParams())
}

function onPageChange(page: number) {
  store.currentPage = page
  store.fetchRelationships(buildFilterParams())
}

// Stat cards
const statCards = computed(() => {
  const o = store.overview
  if (!o) return []
  return [
    { key: 'nourishing', label: '🌱 滋养型', value: o.nourishing_count },
    { key: 'neutral', label: '⚪ 中性', value: o.neutral_count },
    { key: 'draining', label: '⚡ 消耗型', value: o.draining_count },
    { key: 'toxic', label: '⚠️ 有害型', value: o.harmful_count },
  ]
})

function filterByType(type: string) {
  filterQuality.value = filterQuality.value === type ? '' : type
  onFilterChange()
}

// Form state
const formVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()
const formData = ref({
  name: '',
  alias: '',
  met_date: null as string | null,
  met_place: '',
  met_scene: '',
  identity_then: '',
  they_give_me: '',
  i_give_them: '',
  current_status: 'active',
  notes: '',
  tags: '',
})

const formRules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  current_status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

// Helpers
function formatTime(t: string | null | undefined): string {
  if (!t) return '-'
  return t.slice(0, 10)
}

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' {
  if (status === 'active') return 'success'
  if (status === 'distant') return 'warning'
  if (status === 'paused') return 'info'
  return 'danger'
}

function relationTypeLabel(type: string): string {
  return RELATION_TYPE_LABELS[type] || type
}

function relationTagType(type: string): 'success' | 'warning' | 'danger' | 'info' {
  return RELATION_TYPE_TAG[type] || 'info'
}

function statusLabel(status: string): string {
  return STATUS_OPTIONS.find(s => s.value === status)?.label || status
}

function qualityGradient(quality: string): string {
  const c = QUALITY_CONFIG[quality]
  return c ? c.color : '#9CA3AF'
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  formData.value = {
    name: '', alias: '', met_date: null, met_place: '', met_scene: '',
    identity_then: '', they_give_me: '', i_give_them: '',
    current_status: 'active', notes: '', tags: '',
  }
  formVisible.value = true
}

function openEdit(row: Relationship) {
  isEdit.value = true
  editingId.value = row.id
  formData.value = {
    name: row.name,
    alias: row.alias || '',
    met_date: row.met_date || null,
    met_place: row.met_place || '',
    met_scene: row.met_scene || '',
    identity_then: row.identity_then || '',
    they_give_me: row.they_give_me || '',
    i_give_them: row.i_give_them || '',
    current_status: row.current_status || 'active',
    notes: row.notes || '',
    tags: row.tags || '',
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
      await api.updateRelationship(editingId.value, payload)
    } else {
      await api.createRelationship(payload)
    }
    ElMessage.success(isEdit.value ? '已更新' : '已添加')
    formVisible.value = false
    await refreshAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: Relationship) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.name}」的所有记录？`, '提示', { type: 'warning' })
    await api.deleteRelationship(row.id)
    ElMessage.success('已删除')
    await refreshAll()
  } catch { /* cancelled */ }
}

function resetForm() {
  formRef.value?.resetFields()
}

function refreshList() {
  store.currentPage = 1
  store.fetchRelationships(buildFilterParams())
}

async function loadMetPlaces() {
  try {
    const res = await api.getMetPlaces()
    locationOptions.value = res.data || []
  } catch { locationOptions.value = [] }
}

async function refreshAll() {
  await Promise.all([
    store.fetchRelationships(buildFilterParams()),
    store.fetchOverview(),
    store.fetchDueReminders(),
    loadMetPlaces(),
  ])
}

onMounted(async () => {
  await Promise.all([
    store.fetchRelationships(buildFilterParams()),
    store.fetchOverview(),
    store.fetchDueReminders(),
    loadMetPlaces(),
  ])
})
</script>

<style scoped lang="scss">
.relation-dashboard {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
    flex-wrap: wrap; gap: 12px;
    .header-left { display: flex; align-items: center; gap: 12px;
      .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    }
    .header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  }

  .main-tabs {
    :deep(.el-tabs__header) { margin-bottom: 18px; }
    :deep(.el-tabs__item) { font-size: 14px; padding: 0 18px; }
  }

  .section-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px;
    :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
    .section-header { display: flex; justify-content: space-between; align-items: center; }
    .pagination { margin-top: 12px; justify-content: flex-end; }
  }

  .stats-section { margin-bottom: 18px;
    .total-stat { font-size: 13px; color: #6B7280; margin-bottom: 12px; text-align: center;
      strong { color: #1F2937; }
    }
  }
  .stats-row { margin-bottom: 18px;
    .stat-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); cursor: pointer; text-align: center; padding: 12px 0; transition: transform 0.15s, box-shadow 0.15s;
      &:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.12); }
      .stat-label { font-size: 14px; margin-bottom: 4px; }
      .stat-value { font-size: 24px; font-weight: 700; color: #1F2937; line-height: 1.3; }
      &.stat-nourishing { background: linear-gradient(135deg, #ecfdf5, #d1fae5); .stat-value { color: #059669; } }
      &.stat-neutral { background: linear-gradient(135deg, #f3f4f6, #e5e7eb); .stat-value { color: #6B7280; } }
      &.stat-draining { background: linear-gradient(135deg, #fffbeb, #fef3c7); .stat-value { color: #D97706; } }
      &.stat-toxic { background: linear-gradient(135deg, #fef2f2, #fecaca); .stat-value { color: #DC2626; } }
    }
  }

  .reminder-list {
    .reminder-item {
      display: flex; align-items: center; gap: 12px; padding: 10px 0;
      border-bottom: 1px solid #f5f5f5; cursor: pointer; transition: background 0.2s;
      &:hover { background: #faf5ff; }
      &:last-child { border-bottom: none; }
      .reminder-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
      .reminder-info { flex: 1; display: flex; align-items: center; gap: 8px;
        .reminder-name { font-weight: 500; color: #1F2937; font-size: 14px; }
        .reminder-tags { font-size: 12px; color: #9CA3AF; }
      }
      .reminder-meta {
        .reminder-days { font-size: 12px; color: #EF4444; white-space: nowrap; }
      }
    }
  }

  .relation-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px;
    padding: 4px 0;
    min-height: 120px;

    .relation-card {
      background: #fff;
      border: 1px solid #f0f0f0;
      border-radius: 10px;
      padding: 16px;
      cursor: pointer;
      transition: all 0.2s;
      &:hover { border-color: #c4b5fd; box-shadow: 0 4px 12px rgba(139,92,246,0.1); transform: translateY(-2px); }

      .card-top { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px;
        .avatar { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 600; font-size: 16px; flex-shrink: 0; }
        .card-meta { flex: 1; min-width: 0;
          .relation-name { font-size: 15px; font-weight: 600; color: #1F2937; margin-bottom: 4px; }
          .relation-tags { display: flex; flex-wrap: wrap; gap: 4px; }
        }
        .quality-tag { flex-shrink: 0; }
      }

      .card-body {
        margin-bottom: 12px;
        .info-row { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; font-size: 13px;
          .info-label { color: #9CA3AF; }
          .info-value { color: #374151; font-weight: 500; }
        }
      }

      .card-footer { display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 1px solid #f5f5f5; }
    }
  }
}

// ============================================
// 隐私模式提示条
// ============================================
.privacy-banner {
  background: #fdf6ec;
  border: 1px solid #e6a23c;
  border-radius: 6px;
  padding: 6px 16px;
  font-size: 13px;
  color: #e6a23c;
  margin-bottom: 12px;
}
</style>
