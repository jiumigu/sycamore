<template>
  <div class="task-list-view">
    <div class="page-header">
      <el-button size="small" @click="$router.push('/temporal')">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <h2 class="page-title">📋 时间任务清单</h2>
      <el-button size="small" type="primary" @click="$router.push('/temporal/mapping')">🧩 映射编辑器</el-button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-date-picker
        v-model="filter.dateRange"
        type="daterange"
        range-separator="~"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        size="small"
        style="width:240px"
        @change="applyFilter"
      />
      <el-select v-model="filter.attribution" placeholder="L1 归因" clearable size="small" style="width:120px" @change="applyFilter">
        <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
      </el-select>
      <el-select v-model="filter.activity_type" placeholder="L2 活动类型" clearable size="small" style="width:140px" @change="applyFilter">
        <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
      </el-select>
      <el-checkbox v-model="filter.unclassified" size="small" @change="applyFilter">仅未归类</el-checkbox>
      <el-input v-model="filter.keyword" placeholder="搜索任务名 / 备注" clearable size="small" style="width:180px"
        @keyup.enter="applyFilter" @clear="applyFilter">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button size="small" @click="applyFilter">查询</el-button>
      <el-button size="small" @click="resetFilter">重置</el-button>
    </div>

    <!-- 批量操作条 -->
    <div class="bulk-bar" v-if="selectedRows.length">
      <span>已选 {{ selectedRows.length }} 项</span>
      <el-button size="small" type="primary" @click="bulkVisible = true">批量改 L1 归因 / L2 类型</el-button>
      <el-button size="small" @click="clearSelection">取消选择</el-button>
    </div>

    <el-table ref="tableRef" :data="tasks" v-loading="loading" stripe size="small" max-height="560"
      @selection-change="onSelectionChange" row-key="id">
      <el-table-column type="selection" width="40" reserve-selection />
      <el-table-column label="任务（L3）" prop="task_name" min-width="130" show-overflow-tooltip />
      <el-table-column label="开始时间" width="140">
        <template #default="{ row }">{{ (row.start_time || '').slice(0, 16) }}</template>
      </el-table-column>
      <el-table-column label="时长" width="80">
        <template #default="{ row }">{{ row.duration_display || '-' }}</template>
      </el-table-column>
      <el-table-column label="L1 归因" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.attribution" size="small" :style="attrStyle(row.attribution)">{{ row.attribution }}</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="L2 类型" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.activity_type" size="small" :style="typeStyle(row.activity_type)">{{ row.activity_type }}</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.notes || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next" small
      style="margin-top:12px;justify-content:center" @current-change="loadTasks" />

    <!-- 批量改弹窗 -->
    <el-dialog v-model="bulkVisible" title="批量设置 L1 归因 / L2 类型" width="460px">
      <el-form label-width="110px" size="small">
        <el-form-item label="L2 活动类型" required>
          <el-select v-model="bulkForm.activity_type" style="width:100%">
            <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="L1 价值归因">
          <el-select v-model="bulkForm.attribution" clearable style="width:100%">
            <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="bulkVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="applyBulk">应用</el-button>
      </template>
    </el-dialog>

    <!-- 单条编辑（沿用 TemporalTaskSerializer 字段） -->
    <el-dialog v-model="editVisible" :title="editingId ? '编辑任务' : '新增任务'" width="520px">
      <el-form :model="editForm" label-width="80px" size="small">
        <el-form-item label="任务名称" required>
          <el-input v-model="editForm.task_name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.task_description" type="textarea" :rows="2" />
        </el-form-item>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="开始时间">
              <el-date-picker v-model="editForm.start_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时长(时)">
              <el-input-number v-model="editForm.duration_hours" :min="0" :max="24" :step="0.5" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="editVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Search } from '@element-plus/icons-vue'
import * as temporalApi from '@/modules/temporal/api/temporalApi'
import { useTemporalStore } from '../stores/temporalStore'
import { ACTIVITY_TYPE_COLOR_MAP, ACTIVITY_TYPE_OPTIONS, ATTRIBUTION_COLOR_MAP, ATTRIBUTION_OPTIONS } from '../types/temporalTypes'

const store = useTemporalStore()

const tasks = ref<any[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const selectedRows = ref<any[]>([])
const tableRef = ref<any>(null)

const filter = reactive<{ dateRange: string[]; activity_type: string; attribution: string; keyword: string; unclassified: boolean }>({
  dateRange: [], activity_type: '', attribution: '', keyword: '', unclassified: false,
})

const bulkVisible = ref(false)
const saving = ref(false)
const bulkForm = reactive<{ activity_type: string; attribution: string | null }>({ activity_type: '', attribution: null })

const editVisible = ref(false)
const editingId = ref<number | null>(null)
const editForm = reactive({
  task_name: '', task_description: '', start_time: '', duration_hours: 0, notes: '',
})

function attrStyle(name: string) {
  return { background: (ATTRIBUTION_COLOR_MAP[name] || '#94A3B8') + '22', color: ATTRIBUTION_COLOR_MAP[name] || '#64748B', border: 'none' }
}
function typeStyle(name: string) {
  return { background: (ACTIVITY_TYPE_COLOR_MAP[name] || '#94A3B8') + '22', color: ACTIVITY_TYPE_COLOR_MAP[name] || '#64748B', border: 'none' }
}

async function loadTasks() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (filter.dateRange?.length === 2) { params.date_from = filter.dateRange[0]; params.date_to = filter.dateRange[1] }
    if (filter.activity_type) params.activity_type = filter.activity_type
    if (filter.attribution) params.attribution = filter.attribution
    if (filter.unclassified) params.unclassified = '1'
    if (filter.keyword.trim()) params.search = filter.keyword.trim()
    const res = await temporalApi.getTaskList(params)
    const data = res.data
    tasks.value = (data.results || data) as any[]
    total.value = data.count ?? tasks.value.length
  } catch { tasks.value = [] } finally { loading.value = false }
}

function applyFilter() { page.value = 1; loadTasks() }
function resetFilter() {
  filter.dateRange = []; filter.activity_type = ''; filter.attribution = ''; filter.keyword = ''; filter.unclassified = false
  applyFilter()
}
function onSelectionChange(rows: any[]) { selectedRows.value = rows }
function clearSelection() { selectedRows.value = []; tableRef.value?.clearSelection() }

async function applyBulk() {
  if (!selectedRows.value.length || !bulkForm.activity_type) return
  saving.value = true
  try {
    const res = await store.batchSetMeta({
      task_names: selectedRows.value.map((r) => r.task_name),
      activity_type: bulkForm.activity_type,
      attribution: bulkForm.attribution || null,
    })
    ElMessage.success(`已更新 ${res.updated} 个任务`)
    bulkVisible.value = false
    await loadTasks()
  } catch { ElMessage.error('批量失败') } finally { saving.value = false }
}

function openEdit(row: any) {
  editingId.value = row.id
  editForm.task_name = row.task_name
  editForm.task_description = row.task_description || ''
  editForm.start_time = row.start_time || ''
  editForm.duration_hours = row.duration_hours ?? 0
  editForm.notes = row.notes || ''
  editVisible.value = true
}
async function saveEdit() {
  if (!editForm.task_name.trim()) { ElMessage.warning('请输入任务名称'); return }
  saving.value = true
  try {
    if (editingId.value) await temporalApi.updateTask(editingId.value, { ...editForm })
    else await temporalApi.createTask({ ...editForm })
    ElMessage.success('保存成功')
    editVisible.value = false
    loadTasks()
  } catch { ElMessage.error('保存失败') } finally { saving.value = false }
}

onMounted(async () => { await loadTasks() })
</script>

<style scoped lang="scss">
.task-list-view { padding: 16px;
  .page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
    .page-title { margin: 0; font-size: 18px; font-weight: 600; } }
  .filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .bulk-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; font-size: 13px; color: #4b5563; }
  .muted { color: #b8bcc4; }
}
</style>
