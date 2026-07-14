<template>
  <div class="daily-log-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">📝 日记流</h1>
        <el-tag type="primary" class="module-tag">时间感知</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-section">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" style="background: #e6f7ff">
                <el-icon color="#1890ff"><Document /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats?.total_count || 0 }}</div>
                <div class="stat-label">总记录数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" style="background: #f6ffed">
                <el-icon color="#52c41a"><Edit /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ formatNumber(stats?.total_words) }}</div>
                <div class="stat-label">总字数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" style="background: #fff7e6">
                <el-icon color="#fa8c16"><EditPen /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ formatNumber(stats?.total_oneday) }}</div>
                <div class="stat-label">OneDay 字数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon" style="background: #fff1f0">
                <el-icon color="#f5222d"><Calendar /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats?.month_count || 0 }}</div>
                <div class="stat-label">本月新增</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 日历热图 -->
    <el-card class="heatmap-card">
      <template #header>
        <div class="card-header">
          <span>📅 日记日历热图</span>
          <div class="year-switcher">
            <el-button @click="prevYear" :icon="ArrowLeft" circle size="small" />
            <span class="year-label">{{ currentYear }}</span>
            <el-button @click="nextYear" :icon="ArrowRight" circle size="small" />
          </div>
        </div>
      </template>
      <div class="heatmap-body">
        <div class="heatmap-grid">
          <div v-for="month in 12" :key="month" class="heatmap-month">
            <div class="month-label">{{ month }}月</div>
            <div class="month-days">
              <div
                v-for="day in daysInMonth(month)"
                :key="day"
                class="heatmap-day"
                :style="{ backgroundColor: getDayColor(month, day) }"
                :title="getDayTooltip(month, day)"
              ></div>
            </div>
          </div>
        </div>
        <div class="heatmap-footer">
          <span class="legend-label">少</span>
          <span v-for="level in 5" :key="level" class="legend-block" :style="{ backgroundColor: colorScale[level - 1] }"></span>
          <span class="legend-label">多</span>
          <span class="legend-summary">共 <strong>{{ Object.keys(heatmapData).length }}</strong> 天有记录</span>
        </div>
      </div>
    </el-card>

    <!-- 年份筛选标签 -->
    <el-card class="section-card filter-tabs-card">
      <el-radio-group v-model="searchForm.years" @change="handleSearch">
        <el-radio-button value="">全部年份</el-radio-button>
        <el-radio-button v-for="y in yearOptions" :key="y" :value="String(y)">{{ y }}</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- 筛选栏 -->
    <el-card class="section-card">
      <div class="filter-bar">
        <el-input
          v-model="searchForm.title"
          placeholder="搜索主题..."
          clearable
          class="search-input"
          @input="handleSearch"
        />
        <el-select v-model="searchForm.otype" placeholder="类型" clearable @change="handleSearch" class="filter-select">
          <el-option v-for="o in OTYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-button type="danger" :disabled="!selectedIds.length" @click="handleBulkDelete" class="bulk-delete-btn">
          <el-icon><Delete /></el-icon>
          批量删除
        </el-button>
        <div class="filter-actions">
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            新增日记
          </el-button>
          <el-button @click="resetSearch" class="reset-btn">
            <el-icon><RefreshRight /></el-icon>重置
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 数据表格 -->
    <el-card class="table-card">
      <el-table
        v-loading="loading"
        :data="onedayList"
        style="width: 100%; cursor: pointer;"
        @selection-change="handleSelectionChange"
        @row-click="handleRowClick"
        @row-dblclick="openEditDialog"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="oid" label="ID" width="70" sortable />
        <el-table-column prop="title" label="主题" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="logseq-title" :class="{ 'has-logseq': row.logseq_file }">
              {{ row.title || '无标题' }}
            </span>
            <el-tooltip v-if="row.logseq_file" content="在 Logseq 中打开" placement="top">
              <el-icon class="logseq-icon"><Link /></el-icon>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="创建日期" width="120" sortable>
          <template #default="{ row }">
            {{ formatDate(row.begin_date) }}
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.otype)" size="small">
              {{ row.otype_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="oneday" label="OneDay" width="90" sortable>
          <template #default="{ row }">
            <el-input-number
              v-if="editingRow === row.oid && editingField === 'oneday'"
              v-model="row.oneday"
              :min="0"
              size="small"
              controls-position="right"
              @blur="handleFieldBlur(row, 'oneday')"
              @keyup.enter="handleFieldBlur(row, 'oneday')"
            />
            <span v-else @click="startEditField(row, 'oneday')" class="editable-cell">{{ row.oneday ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="page" label="Page" width="90" sortable>
          <template #default="{ row }">
            <el-input-number
              v-if="editingRow === row.oid && editingField === 'page'"
              v-model="row.page"
              :min="0"
              size="small"
              controls-position="right"
              @blur="handleFieldBlur(row, 'page')"
              @keyup.enter="handleFieldBlur(row, 'page')"
            />
            <span v-else @click="startEditField(row, 'page')" class="editable-cell">{{ row.page ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="总字数" width="80" sortable prop="total">
          <template #default="{ row }">
            <el-tag size="small" :type="(row.total ?? 0) > 0 ? 'success' : 'info'">
              {{ row.total ?? 0 }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.logseq_file" size="small" text @click.stop="openLogseq(row)">
              <el-icon><Link /></el-icon> Logseq
            </el-button>
            <el-button type="primary" link size="small" @click.stop="openEditDialog(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button type="danger" link size="small" @click.stop="handleDelete(row)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalCount"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- Logseq 查看对话框 -->
    <LogseqViewer
      v-model="showLogseqViewer"
      :title="viewingLogseqTitle"
      :filepath="viewingLogseqPath"
    />

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'create' ? '新建每日记录' : '编辑每日记录'"
      width="520px"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="主题" prop="title">
          <el-input v-model="formData.title" placeholder="请输入主题" maxlength="255" />
        </el-form-item>

        <el-form-item label="创建日期" prop="begin_date">
          <el-date-picker
            v-model="formData.begin_date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            :disabled-date="(d: Date) => d.getTime() > Date.now()"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="内容类型" prop="otype">
          <el-select v-model="formData.otype" placeholder="请选择" style="width: 100%">
            <el-option v-for="o in OTYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="OneDay" prop="oneday">
              <el-input-number v-model="formData.oneday" :min="0" :max="999999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Page" prop="page">
              <el-input-number v-model="formData.page" :min="0" :max="999999" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="标签">
          <el-input v-model="formData.flag" placeholder="标签" maxlength="50" />
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" :rows="2" placeholder="备注" maxlength="255" />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search, Refresh, Plus, Delete, Edit, ArrowLeft, ArrowRight,
  Document, EditPen, Calendar, RefreshRight, Link,
} from '@element-plus/icons-vue'
import { useTemporalStore } from '../stores/temporalStore'
import { OTYPE_OPTIONS } from '../types/temporalTypes'
import { getYearlyHeatmap } from '../api/temporalApi'
import type { OneDayPage } from '../types/temporalTypes'
import LogseqViewer from '../components/LogseqViewer.vue'

const store = useTemporalStore()

const loading = computed(() => store.loading)
const onedayList = computed(() => store.onedayList)
const stats = computed(() => store.stats)
const totalCount = computed(() => store.totalCount)
const submitting = computed(() => store.submitting)

const currentPage = ref(1)
const pageSize = ref(20)
const selectedIds = ref<number[]>([])
const dialogVisible = ref(false)
const dialogType = ref<'create' | 'edit'>('create')
const formRef = ref()
const editingRow = ref<number | null>(null)
const editingField = ref<string | null>(null)
const showLogseqViewer = ref(false)
const viewingLogseqTitle = ref('')
const viewingLogseqPath = ref('')

// ── 日历热图 ──

const currentYear = ref(new Date().getFullYear())
const heatmapData = ref<Record<string, { count: number; title: string }>>({})

const colorScale = ['#EBEDF0', '#9BE9A8', '#40C463', '#30A14E', '#216E39']

const daysInMonth = (month: number) => new Date(currentYear.value, month, 0).getDate()

async function fetchYearlyHeatmap(year: number) {
  try {
    const res = await getYearlyHeatmap(year)
    const map: Record<string, { count: number; title: string }> = {}
    for (const item of res.data.data) {
      const key = item.date.slice(5)
      map[key] = { count: item.count, title: item.title }
    }
    heatmapData.value = map
  } catch {
    heatmapData.value = {}
  }
}

function getDayColor(month: number, day: number): string {
  const key = `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  const data = heatmapData.value[key]
  if (!data || data.count === 0) return colorScale[0]
  if (data.count < 500) return colorScale[1]
  if (data.count < 1000) return colorScale[2]
  if (data.count < 2000) return colorScale[3]
  return colorScale[4]
}

function getDayTooltip(month: number, day: number): string {
  const key = `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  const data = heatmapData.value[key]
  if (!data) return `${month}月${day}日：无记录`
  return `${month}月${day}日：${data.count} 字 — ${data.title || '无标题'}`
}

function prevYear() { currentYear.value--; fetchYearlyHeatmap(currentYear.value) }
function nextYear() { currentYear.value++; fetchYearlyHeatmap(currentYear.value) }

// ──

const yearOptions = computed(() => {
  const years: number[] = []
  const cy = new Date().getFullYear()
  for (let i = cy; i >= cy - 10; i--) years.push(i)
  return years
})

const searchForm = reactive({
  years: '',
  otype: '',
  title: '',
})

const formData = reactive({
  oid: undefined as number | undefined,
  title: '',
  begin_date: '',
  otype: 'ONEDAY',
  oneday: 0,
  page: 0,
  flag: '',
  remark: '',
})

const formRules = {
  begin_date: [{ required: true, message: '请选择创建日期', trigger: 'change' }],
  otype: [{ required: true, message: '请选择内容类型', trigger: 'change' }],
}

function formatNumber(n: number | undefined | null): string {
  if (!n) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return String(n)
}

function formatDate(d: string | undefined | null): string {
  if (!d) return ''
  return d.slice(0, 10)
}

function getTypeTagType(type: string) {
  const m: Record<string, string> = {
    MIGU: 'success', HAPPY: 'warning', SAD: 'danger',
    DIGITAL: 'info', SUMMARY: '', ONEDAY: '', IDEA: 'info', ACHIEVE: 'success',
  }
  return m[type] || ''
}

function handleSelectionChange(val: OneDayPage[]) {
  selectedIds.value = val.map(v => v.oid)
}

function startEditField(row: OneDayPage, field: string) {
  editingRow.value = row.oid
  editingField.value = field
}

async function handleFieldBlur(row: OneDayPage, field: string) {
  editingRow.value = null
  editingField.value = null
  try {
    await store.updateOneDay(row.oid, { [field]: row[field as keyof OneDayPage] })
    ElMessage.success(field === 'oneday' ? 'OneDay 字数已更新' : 'Page 字数已更新')
    store.fetchStats()
  } catch {
    ElMessage.error('更新失败')
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchData()
}

function resetSearch() {
  searchForm.years = ''
  searchForm.otype = ''
  searchForm.title = ''
  handleSearch()
}

async function fetchData() {
  const params: Record<string, unknown> = {
    page: currentPage.value,
    page_size: pageSize.value,
  }
  if (searchForm.years) params.years = searchForm.years
  if (searchForm.otype) params.otype = searchForm.otype
  if (searchForm.title) params.title = searchForm.title
  await store.fetchOneDayList(params)
}

function openCreateDialog() {
  dialogType.value = 'create'
  formData.oid = undefined
  formData.title = ''
  formData.begin_date = new Date().toISOString().slice(0, 10)
  formData.otype = 'ONEDAY'
  formData.oneday = 0
  formData.page = 0
  formData.flag = ''
  formData.remark = ''
  dialogVisible.value = true
}

function openEditDialog(row: OneDayPage) {
  dialogType.value = 'edit'
  formData.oid = row.oid
  formData.title = row.title || ''
  formData.begin_date = formatDate(row.begin_date)
  formData.otype = row.otype
  formData.oneday = row.oneday ?? 0
  formData.page = row.page ?? 0
  formData.flag = row.flag || ''
  formData.remark = row.remark || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const data: Record<string, unknown> = {
    title: formData.title || null,
    begin_date: formData.begin_date || null,
    otype: formData.otype,
    oneday: formData.oneday,
    page: formData.page,
    flag: formData.flag || null,
    remark: formData.remark || null,
  }
  Object.keys(data).forEach(k => { if (data[k] === null || data[k] === undefined) delete data[k] })

  try {
    if (dialogType.value === 'create') {
      await store.createOneDay(data)
      ElMessage.success('创建成功')
    } else if (formData.oid) {
      await store.updateOneDay(formData.oid, data)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    fetchData()
    store.fetchStats()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(row: OneDayPage) {
  try {
    await ElMessageBox.confirm('确定删除这条记录？', '提示', { type: 'warning' })
    await store.deleteOneDay(row.oid)
    ElMessage.success('已删除')
    fetchData()
    store.fetchStats()
  } catch { /* cancelled */ }
}

async function handleBulkDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除 ${selectedIds.value.length} 条记录？`, '提示', { type: 'warning' })
    await store.bulkDeleteOneDay(selectedIds.value)
    ElMessage.success('批量删除成功')
    selectedIds.value = []
    fetchData()
    store.fetchStats()
  } catch { /* cancelled */ }
}

function handleDialogClose() {
  formRef.value?.resetFields()
}

function handleSizeChange(val: number) { pageSize.value = val; fetchData() }
function handleCurrentChange(val: number) { currentPage.value = val; fetchData() }

const handleRowClick = (row: OneDayPage) => {
  if (row.logseq_file) {
    openLogseq(row)
  } else {
    openEditDialog(row)
  }
}

const openLogseq = (row: OneDayPage) => {
  viewingLogseqTitle.value = row.title || row.begin_date?.slice(0, 10) || 'Logseq'
  viewingLogseqPath.value = row.logseq_file ?? ''
  showLogseqViewer.value = true
}

function handleRefresh() {
  fetchData()
  store.fetchStats()
  fetchYearlyHeatmap(currentYear.value)
  ElMessage.success('数据已刷新')
}

onMounted(() => {
  fetchData()
  store.fetchStats()
  fetchYearlyHeatmap(currentYear.value)
})
</script>

<style scoped lang="scss">
.daily-log-view {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

// ── 页面头部 ──
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .page-title {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
    .module-tag { font-size: 12px; }
  }
  .header-actions { display: flex; gap: 12px; }
}

// ── 统计卡片 ──
.stats-section { margin-bottom: 24px; }

.stat-card {
  :deep(.el-card__body) { padding: 20px; }

  .stat-content {
    display: flex;
    align-items: center;
    gap: 16px;

    .stat-icon {
      width: 48px; height: 48px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }
    .stat-info {
      .stat-value { font-size: 24px; font-weight: 600; line-height: 1; color: var(--el-text-color-primary); margin-bottom: 4px; }
      .stat-label { font-size: 14px; color: var(--el-text-color-regular); }
    }
  }
}

// ── 日历热图 ──
.heatmap-card {
  margin-bottom: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 10px;
    span { font-size: 16px; font-weight: 500; }

    .year-switcher {
      display: flex;
      align-items: center;
      gap: 8px;

      .year-label {
        font-size: 16px; font-weight: 600; color: var(--el-text-color-primary);
        min-width: 48px; text-align: center;
      }
    }
  }

  .heatmap-body {
    padding: 4px 8px 12px;

    .heatmap-grid {
      display: flex; gap: 4px; overflow-x: auto;

      .heatmap-month {
        flex: 1; min-width: 0; display: flex; flex-direction: column;

        .month-label {
          font-size: 11px; color: #6B7280; text-align: center;
          margin-bottom: 4px; width: 100%;
        }

        .month-days {
          display: flex; flex-direction: column; gap: 2px; width: 100%;

          .heatmap-day {
            width: 100%; height: 10px;
            border-radius: 2px; cursor: default;

            &:hover {
              outline: 1px solid rgba(0,0,0,0.4);
              outline-offset: 0;
            }
          }
        }
      }
    }

    .heatmap-footer {
      display: flex; align-items: center; gap: 2px; margin-top: 8px;

      .legend-label { font-size: 10px; color: #9CA3AF; }
      .legend-block {
        width: 8px; height: 8px; border-radius: 1px; display: inline-block;
      }
      .legend-summary { margin-left: 12px; font-size: 11px; color: #6B7280;
        strong { color: var(--el-text-color-primary); }
      }
    }
  }
}

// ── 通用卡片区 ──
.section-card { margin-bottom: 16px; }

.filter-tabs-card {
  :deep(.el-card__body) { padding: 12px 16px; }
}

// ── 筛选栏 ──
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;

  .search-input { width: 200px; }
  .filter-select { width: 120px; }

  .filter-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
  }
}

// ── 数据表格 ──
.table-card {
  :deep(.el-card__body) { padding: 20px; }

  .pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}

.editable-cell {
  cursor: pointer; padding: 2px 4px; border-radius: 3px; display: inline-block;
  &:hover { background: var(--el-fill-color-light); color: var(--el-color-primary); }
}

.logseq-title.has-logseq {
  color: var(--el-color-primary);
  font-weight: 500;
}

.logseq-icon {
  margin-left: 4px;
  font-size: 14px;
  color: var(--el-color-primary);
  vertical-align: middle;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
