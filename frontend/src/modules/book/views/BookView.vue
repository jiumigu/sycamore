<template>
  <div class="book-view">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">阅读管理</h1>
        <el-tag type="primary" class="module-tag">知识沉淀</el-tag>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建书籍
        </el-button>
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

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
                <div class="stat-label">总书籍数</div>
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
                <div class="stat-label">已完成</div>
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
                <div class="stat-label">平均推荐</div>
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

    <el-row :gutter="20" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><div class="card-header"><span>年度阅读统计</span></div></template>
          <div ref="yearChartRef" class="chart-container" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><div class="card-header"><span>书籍类型分布</span></div></template>
          <div v-if="stats?.type_stats?.length" ref="typeChartRef" class="chart-container" />
          <el-empty v-else description="暂无类型数据" :image-size="100" />
        </el-card>
      </el-col>
    </el-row>

    <el-card class="filter-card">
      <div class="filter-header">
        <div class="search-section">
          <el-input
            v-model="searchForm.search"
            placeholder="搜索书名或作者..."
            class="search-input"
            :prefix-icon="Search"
            clearable
            @input="handleSearch"
          />
        </div>
        <div class="filter-section">
          <el-select v-model="searchForm.year" placeholder="年份" clearable @change="handleSearch" class="filter-select">
            <el-option v-for="y in yearOptions" :key="y" :label="y" :value="String(y)" />
          </el-select>
          <el-select v-model="searchForm.btype" placeholder="书籍类型" clearable @change="handleSearch" class="filter-select">
            <el-option v-for="t in BTYPE_OPTIONS" :key="t" :label="t" :value="t" />
          </el-select>
          <el-select v-model="searchForm.status" placeholder="阅读状态" clearable @change="handleSearch" class="filter-select">
            <el-option v-for="s in STATUS_OPTIONS" :key="s" :label="s" :value="s" />
          </el-select>
          <el-select v-model="searchForm.reading_depth" placeholder="阅读深度" clearable @change="handleSearch" class="filter-select">
            <el-option v-for="d in READING_DEPTH_OPTIONS" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
          <el-button @click="resetSearch" class="reset-btn">
            <el-icon><RefreshRight /></el-icon>重置
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="table-card">
      <el-table v-loading="loading" :data="bookList" style="width: 100%" @selection-change="handleSelectionChange" @row-dblclick="openEditDialog">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="bid" label="ID" width="70" sortable />
        <el-table-column prop="btitle" label="书名" min-width="180" show-overflow-tooltip />
        <el-table-column prop="author" label="作者" width="120" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ row.btype_display || row.btype }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">{{ row.status_display || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="阅读深度" width="90">
          <template #default="{ row }">
            <el-tag :type="getDepthTagType(row.reading_depth)" size="small">{{ row.reading_depth_display || '未知' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="推荐" width="100">
          <template #default="{ row }">
            <div class="recommend-stars">
              <span v-for="i in 5" :key="i" class="star" :class="{ active: i <= (row.recommend || 0) }">★</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="阅读日期" width="110" sortable>
          <template #default="{ row }">{{ row.readDate?.slice(0, 10) || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEditDialog(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
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

    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'create' ? '新建书籍' : '编辑书籍'"
      width="700px"
      destroy-on-close
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="110px" class="book-form">
        <div class="form-section">
          <h3 class="section-title">📖 基本信息</h3>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="书名" prop="btitle">
                <el-input v-model="formData.btitle" placeholder="请输入书名" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="作者" prop="author">
                <el-input v-model="formData.author" placeholder="请输入作者" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="原著书名" prop="original_title">
                <el-input v-model="formData.original_title" placeholder="原著书名（可选）" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="年度" prop="years">
                <el-input v-model="formData.years" disabled />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="书籍类型" prop="btype">
                <el-select v-model="formData.btype" placeholder="请选择类型" style="width: 100%">
                  <el-option v-for="t in BTYPE_OPTIONS" :key="t" :label="t" :value="t" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="阅读状态" prop="status">
                <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%" @change="onStatusChange">
                  <el-option v-for="s in STATUS_OPTIONS" :key="s" :label="s" :value="s" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="阅读深度" prop="reading_depth">
                <el-select v-model="formData.reading_depth" placeholder="请选择" style="width: 100%">
                  <el-option v-for="d in READING_DEPTH_OPTIONS" :key="d.value" :label="d.label" :value="d.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="推荐指数" prop="recommend">
                <el-rate v-model="formData.recommend" :max="5" show-text :texts="RECOMMEND_TEXTS" style="line-height: 32px" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="阅读日期" prop="readDate">
            <el-date-picker
              v-model="formData.readDate"
              type="date"
              placeholder="选择阅读日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              style="width: 100%"
              @change="onReadDateChange"
            />
          </el-form-item>
        </div>

        <div class="form-section">
          <h3 class="section-title">💭 阅读体验</h3>
          <el-form-item label="读前观点" prop="openop">
            <el-input v-model="formData.openop" type="textarea" rows="3" placeholder="记录打开书时的观点和期待" maxlength="1000" show-word-limit />
          </el-form-item>
          <el-form-item label="读后感" prop="closedop">
            <el-input v-model="formData.closedop" type="textarea" rows="4" placeholder="记录读完书后的感想和收获" maxlength="2000" show-word-limit />
          </el-form-item>
          <el-form-item label="行动项" prop="action_item">
            <el-input v-model="formData.action_item" type="textarea" rows="2" placeholder="读完这本书，我决定做一件什么事？" maxlength="500" show-word-limit />
          </el-form-item>
          <el-form-item v-if="formData.status === '弃读'" label="弃读原因" prop="abandon_reason">
            <el-input v-model="formData.abandon_reason" type="textarea" rows="3" placeholder="请记录弃读原因..." maxlength="500" show-word-limit />
          </el-form-item>
          <el-form-item label="标签" prop="tags">
            <el-select
              v-model="formData.tags"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="选择或输入标签"
              style="width: 100%"
            >
              <el-option label="经典必读" value="经典必读" />
              <el-option label="强烈推荐" value="强烈推荐" />
              <el-option label="值得重读" value="值得重读" />
              <el-option label="思维启发" value="思维启发" />
            </el-select>
          </el-form-item>
        </div>
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
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  Search, Refresh, Plus, Delete, Edit, Document, Check, Star, Calendar, RefreshRight,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { useBookStore } from '../stores/bookStore'
import {
  BTYPE_OPTIONS, STATUS_OPTIONS, READING_DEPTH_OPTIONS, RECOMMEND_TEXTS,
} from '../types/bookTypes'
import type { Book } from '../types/bookTypes'

const bookStore = useBookStore()

const loading = computed(() => bookStore.loading)
const submitting = computed(() => bookStore.submitting)
const bookList = computed(() => bookStore.bookList)
const stats = computed(() => bookStore.stats)
const totalCount = computed(() => bookStore.totalCount)

const currentPage = ref(1)
const pageSize = ref(20)
const selectedIds = ref<number[]>([])
const dialogVisible = ref(false)
const dialogType = ref<'create' | 'edit'>('create')
const formRef = ref<FormInstance>()

const yearChartRef = ref<HTMLElement>()
const typeChartRef = ref<HTMLElement>()
let yearChart: echarts.ECharts | null = null
let typeChart: echarts.ECharts | null = null

const yearOptions = computed(() => {
  const years: number[] = []
  const cy = new Date().getFullYear()
  for (let i = cy; i >= cy - 10; i--) years.push(i)
  return years
})

const searchForm = reactive({
  year: '', btype: '', status: '',
  reading_depth: undefined as number | undefined,
  search: '',
})

const formData = reactive({
  bid: undefined as number | undefined,
  years: '', btitle: '', author: '', original_title: '',
  btype: '', status: '', recommend: 3, reading_depth: 3,
  readDate: '', openop: '', closedop: '', action_item: '', abandon_reason: '',
  tags: [] as string[],
})

const formRules: FormRules = {
  btitle: [
    { required: true, message: '请输入书名', trigger: 'blur' },
    { max: 255, message: '书名不能超过 255 个字符', trigger: 'blur' },
  ],
  btype: [{ required: true, message: '请选择书籍类型', trigger: 'change' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

function getStatusTagType(status: string) {
  const map: Record<string, string> = {
    '计划阅读': 'info', '精读': 'success', '通读': 'primary',
    '消遣': 'info', '弃读': 'danger', '在读': 'warning',
    '已完成': 'success', '待重读': 'warning',
  }
  return map[status] || 'info'
}

function getDepthTagType(depth: number) {
  const map: Record<number, string> = { 1: 'info', 2: 'info', 3: 'primary', 4: 'warning', 5: 'success' }
  return map[depth] || 'info'
}

function onReadDateChange(val: string) {
  formData.years = val ? new Date(val).getFullYear().toString() : ''
}

function onStatusChange(status: string) {
  if (status !== '弃读') formData.abandon_reason = ''
}

function handleSelectionChange(val: Book[]) {
  selectedIds.value = val.map(item => item.bid)
}

function handleSearch() { currentPage.value = 1; fetchData() }

function resetSearch() {
  Object.assign(searchForm, { year: '', btype: '', status: '', reading_depth: undefined, search: '' })
  fetchData()
}

async function fetchData() {
  const params: Record<string, unknown> = { page: currentPage.value, page_size: pageSize.value }
  if (searchForm.year) params.years = searchForm.year
  if (searchForm.btype) params.btype = searchForm.btype
  if (searchForm.status) params.status = searchForm.status
  if (searchForm.reading_depth !== undefined) params.reading_depth = searchForm.reading_depth
  if (searchForm.search) params.search = searchForm.search
  try {
    await bookStore.fetchBookList(params)
  } catch { ElMessage.error('获取数据失败') }
}

async function fetchStats() {
  try { await bookStore.fetchStats(); await initCharts() } catch {}
}

function resetForm() {
  const now = new Date()
  formData.bid = undefined
  formData.years = now.getFullYear().toString()
  formData.btitle = ''
  formData.author = ''
  formData.original_title = ''
  formData.btype = ''
  formData.status = ''
  formData.recommend = 3
  formData.reading_depth = 3
  formData.readDate = now.toISOString().slice(0, 10)
  formData.openop = ''
  formData.closedop = ''
  formData.abandon_reason = ''
  formData.tags = []
}

function openCreateDialog() { dialogType.value = 'create'; resetForm(); dialogVisible.value = true }

async function openEditDialog(row: Book) {
  dialogType.value = 'edit'
  try {
    const detail = await bookStore.fetchBookById(row.bid)
    if (!detail) return
    formData.bid = detail.bid
    formData.years = detail.years || ''
    formData.btitle = detail.btitle || ''
    formData.author = detail.author || ''
    formData.original_title = detail.original_title || ''
    formData.btype = detail.btype || ''
    formData.status = detail.status || ''
    formData.recommend = detail.recommend ?? 3
    formData.reading_depth = detail.reading_depth || 3
    formData.readDate = detail.readDate || ''
    formData.openop = detail.openop || ''
    formData.closedop = detail.closedop || ''
    formData.action_item = detail.action_item || ''
    formData.abandon_reason = detail.abandon_reason || ''
    formData.tags = ensureArray(detail.tags)
    dialogVisible.value = true
  } catch {
    ElMessage.error('获取书籍详情失败')
  }
}

function ensureArray(value: unknown): string[] {
  if (Array.isArray(value)) return value
  if (typeof value === 'string') return value ? value.split(',') : []
  return []
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    try {
      const data: Record<string, unknown> = {
        years: formData.years,
        btitle: formData.btitle?.trim(),
        btype: formData.btype,
        status: formData.status,
        recommend: formData.recommend,
        reading_depth: Number(formData.reading_depth),
        readDate: formData.readDate || null,
      }
      if (formData.author?.trim()) data.author = formData.author.trim()
      if (formData.original_title?.trim()) data.original_title = formData.original_title.trim()
      if (formData.openop) data.openop = formData.openop
      if (formData.closedop) data.closedop = formData.closedop
      if (formData.status === '弃读' && formData.abandon_reason) data.abandon_reason = formData.abandon_reason
      if (formData.tags.length) data.tags = formData.tags.join(',')

      if (dialogType.value === 'create') {
        await bookStore.createNewBook(data)
        ElMessage.success('创建成功')
      } else if (formData.bid) {
        await bookStore.updateExistingBook(formData.bid, data)
        ElMessage.success('更新成功')
      }
      dialogVisible.value = false
      await fetchData(); await fetchStats()
    } catch {
      ElMessage.error('操作失败')
    }
  })
}

async function handleDelete(row: Book) {
  try {
    await ElMessageBox.confirm(`确定要删除"${row.btitle}"吗？`, '提示', { type: 'warning' })
    await bookStore.deleteExistingBook(row.bid)
    ElMessage.success('删除成功')
    await fetchData(); await fetchStats()
  } catch (error) { if (error !== 'cancel') ElMessage.error('删除失败') }
}

function handleDialogClose() { formRef.value?.resetFields() }

function handleSizeChange(val: number) { pageSize.value = val; currentPage.value = 1; fetchData() }
function handleCurrentChange(page: number) { currentPage.value = page; fetchData() }
function refreshData() { fetchData(); fetchStats(); ElMessage.success('数据已刷新') }

function initCharts() {
  nextTick(() => {
    if (yearChartRef.value) {
      if (!yearChart) yearChart = echarts.init(yearChartRef.value)
      const yd = stats.value?.year_stats || []
      yearChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: yd.map(i => i.years).reverse(), axisLabel: { rotate: 30 } },
        yAxis: { type: 'value', name: '阅读数量' },
        series: [{ type: 'bar', data: yd.map(i => i.count).reverse(), barWidth: '40%', itemStyle: { color: '#409EFF', borderRadius: [4, 4, 0, 0] } }],
      })
    }
    if (typeChartRef.value) {
      if (!typeChart) typeChart = echarts.init(typeChartRef.value)
      const td = (stats.value?.type_stats || []).filter(i => i.count > 0)
      if (td.length) {
        typeChart.setOption({
          tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
          legend: { orient: 'vertical', left: 'left', data: td.map(i => i.btype) },
          series: [{
            name: '书籍类型分布', type: 'pie', radius: ['50%', '70%'],
            center: ['55%', '50%'], avoidLabelOverlap: false,
            itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
            label: { show: false },
            emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
            data: td.map(i => ({ name: i.btype, value: i.count })),
          }],
        })
      }
    }
  })
}

function handleResize() { yearChart?.resize(); typeChart?.resize() }

onMounted(() => { fetchData(); fetchStats(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize); yearChart?.dispose(); typeChart?.dispose() })
</script>

<style scoped lang="scss">
.book-view {
  padding: 20px;
  background-color: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  .header-left { display: flex; align-items: center; gap: 12px;
    .page-title { margin: 0; font-size: 24px; font-weight: 600; color: var(--el-text-color-primary); }
    .module-tag { font-size: 12px; }
  }
  .header-actions { display: flex; gap: 12px; }
}

.stats-section { margin-bottom: 24px;
  .stat-card {
    :deep(.el-card__body) { padding: 20px; }
    .stat-content { display: flex; align-items: center; gap: 16px;
      .stat-icon { width: 48px; height: 48px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
      .stat-info {
        .stat-value { font-size: 24px; font-weight: 600; line-height: 1; color: var(--el-text-color-primary); margin-bottom: 4px; }
        .stat-label { font-size: 14px; color: var(--el-text-color-regular); }
      }
    }
  }
}

.chart-row { margin-bottom: 20px;
  .chart-card {
    .card-header { display: flex; justify-content: space-between; align-items: center; padding: 0 10px; span { font-size: 16px; font-weight: 500; } }
    .chart-container { height: 350px; width: 100%; padding: 10px; }
  }
}

.filter-card { margin-bottom: 20px;
  :deep(.el-card__body) { padding: 20px; }
  .filter-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;
    .search-section { flex: 1; min-width: 250px; .search-input { width: 100%; } }
    .filter-section { display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
      .filter-select { width: 130px; }
      .reset-btn { margin-left: 8px; }
    }
  }
}

.table-card {
  :deep(.el-card__body) { padding: 20px; }
  .recommend-stars { display: inline-flex; gap: 2px;
    .star { color: #d4d4d8; font-size: 14px; &.active { color: #f5a623; } }
  }
  .pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }
}

.book-form { max-height: 70vh; overflow-y: auto; padding-right: 12px;
  .form-section { margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--el-border-color-light);
    .section-title { margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: var(--el-color-primary); }
  }
}

.dialog-footer { display: flex; justify-content: flex-end; gap: 12px; }

@media (max-width: 768px) {
  .page-header { flex-direction: column; align-items: stretch; gap: 16px; }
  .stats-section .el-row { flex-direction: column; .el-col { width: 100%; margin-bottom: 16px; } }
  .filter-card .filter-header { flex-direction: column; align-items: stretch; }
}
</style>
