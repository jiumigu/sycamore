<template>
  <div class="task-list-view">
    <div class="page-header">
      <el-button size="small" @click="$router.push('/temporal')">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <h2 class="page-title">📋 时间任务清单</h2>
      <el-button size="small" type="primary" @click="openCreate">＋ 手工新增</el-button>
      <el-button size="small" @click="$router.push('/temporal/mapping')">🧩 映射编辑器</el-button>
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
      <el-table-column label="结束时间" width="90">
        <template #default="{ row }">
          <span v-if="row.end_time">{{ endTimeText(row) }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column width="86">
        <template #header>
          <el-tooltip placement="top" content="该条记录的时长；正常情况下等于「结束 − 开始」，两者不一致时以本列为准">
            <span class="th-tip">时长</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <span v-if="!row.duration_display" class="muted">-</span>
          <el-tooltip v-else :disabled="!spanMismatch(row)" placement="top" :content="durationTip(row)">
            <span :class="{ 'dur-multi': spanMismatch(row) }">{{ row.duration_display }}<i v-if="spanMismatch(row)" class="dur-mark">*</i></span>
          </el-tooltip>
        </template>
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

    <!-- 单条新增 / 编辑（时长由起止时间自动计算，不再手填） -->
    <el-dialog v-model="editVisible" :title="editingId ? '编辑任务' : '手工新增记录'" width="540px">
      <el-form :model="editForm" label-width="80px" size="small">
        <el-form-item label="任务名称" required>
          <el-input v-model="editForm.task_name" placeholder="如：深度工作 / 刷短视频" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.task_description" type="textarea" :rows="2" />
        </el-form-item>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="开始时间" required>
              <el-date-picker v-model="editForm.start_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss"
                :clearable="false" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间" required>
              <el-date-picker v-model="editForm.end_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss"
                :clearable="false" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="时长">
          <div class="dur-auto">
            <span v-if="formSpanOk" class="dur-value">{{ formDurationText }}<small>小时</small></span>
            <span v-if="formSpanOk" class="dur-hhmm">{{ formHhmmText }}</span>
            <span v-else-if="formSpanMin !== null" class="dur-err">结束时间需晚于开始时间（跨零点请把结束时间选到次日）</span>
            <span v-else class="muted">选定起止时间后自动计算</span>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="2" placeholder="如：和启迪聊天" />
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
import { ref, reactive, computed, onMounted } from 'vue'
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
// v3.58.6：不再有 duration_hours 输入 —— 时长由「开始时间 → 结束时间」自动算，后端落库时同步派生
const editForm = reactive({
  task_name: '', task_description: '', start_time: '', end_time: '', notes: '',
})

function attrStyle(name: string) {
  return { background: (ATTRIBUTION_COLOR_MAP[name] || '#94A3B8') + '22', color: ATTRIBUTION_COLOR_MAP[name] || '#64748B', border: 'none' }
}
function typeStyle(name: string) {
  return { background: (ACTIVITY_TYPE_COLOR_MAP[name] || '#94A3B8') + '22', color: ACTIVITY_TYPE_COLOR_MAP[name] || '#64748B', border: 'none' }
}

// ─── 时间列展示 ───────────────────────────────────────────────────────────
// 一行 = 一条 ATracker 原始记录（v3.58.5 起不再按「任务名 + 日期」合并）：
//   start_time / end_time / duration_hours 同属该条记录 → 「时长 == 结束 − 开始」。
// 若仍不一致（源数据里计时器暂停等），以「记录时长」为准，这里显式标出来避免误读。
function endTimeText(row: any): string {
  const e = String(row.end_time || '')
  if (!e) return ''
  const start = String(row.start_time || '')
  // 跨零点（全库仅 3 条）才补日期，其余只显示 HH:mm
  if (start && start.slice(0, 10) !== e.slice(0, 10)) return `${e.slice(5, 10)} ${e.slice(11, 16)}`
  return e.slice(11, 16)
}

function spanMinutes(row: any): number | null {
  if (!row.start_time || !row.end_time) return null
  const s = Date.parse(String(row.start_time).replace(' ', 'T'))
  const e = Date.parse(String(row.end_time).replace(' ', 'T'))
  if (Number.isNaN(s) || Number.isNaN(e)) return null
  return (e - s) / 60000
}

function fmtMinutes(min: number): string {
  const m = Math.max(0, Math.round(min))
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

// ─── 弹窗内的时长自动计算（v3.58.6）──────────────────────────────────────────
function fmtLocal(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:00`
}

/** DRF 返回 ISO（`2026-09-17T19:30:00+08:00`）→ 日期选择器 value-format 可吃的本地时刻串 */
function isoToInput(v: string | null): string {
  if (!v) return ''
  const s = String(v)
  return s.includes('T') ? s.slice(0, 19).replace('T', ' ') : s
}

/** 弹窗内「结束 − 开始」的分钟数；任一端缺失/非法 → null */
const formSpanMin = computed<number | null>(() => {
  const s = editForm.start_time ? Date.parse(editForm.start_time.replace(' ', 'T')) : NaN
  const e = editForm.end_time ? Date.parse(editForm.end_time.replace(' ', 'T')) : NaN
  if (Number.isNaN(s) || Number.isNaN(e)) return null
  return (e - s) / 60000
})
const formSpanOk = computed(() => formSpanMin.value !== null && formSpanMin.value > 0)
const formDurationText = computed(() => (formSpanOk.value ? (formSpanMin.value as number / 60).toFixed(2) : ''))
const formHhmmText = computed(() => (formSpanOk.value ? fmtMinutes(formSpanMin.value as number) : ''))

// 容差 2 分钟：吸收秒级存取与 duration_display 向下取整的误差
function spanMismatch(row: any): boolean {
  const span = spanMinutes(row)
  if (span === null || row.duration_hours == null) return false
  return Math.abs(span - Number(row.duration_hours) * 60) > 2
}

function durationTip(row: any): string {
  const span = spanMinutes(row) ?? 0
  return `起止跨度 ${fmtMinutes(span)}（${String(row.start_time).slice(11, 16)} → ${String(row.end_time).slice(11, 16)}），记录时长 ${fmtMinutes(Number(row.duration_hours) * 60)}；不一致时以「记录时长」为准`
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

function openCreate() {
  editingId.value = null
  // 默认「刚刚过去的一小时」：手动补记时改动最小，且一打开就能看到时长
  const now = new Date()
  now.setSeconds(0, 0)
  editForm.task_name = ''
  editForm.task_description = ''
  editForm.start_time = fmtLocal(new Date(now.getTime() - 3600_000))
  editForm.end_time = fmtLocal(now)
  editForm.notes = ''
  editVisible.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  editForm.task_name = row.task_name
  editForm.task_description = row.task_description || ''
  editForm.start_time = isoToInput(row.start_time)
  editForm.end_time = isoToInput(row.end_time)
  editForm.notes = row.notes || ''
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.task_name.trim()) { ElMessage.warning('请输入任务名称'); return }
  if (!editForm.start_time) { ElMessage.warning('请选择开始时间'); return }
  if (!editForm.end_time) { ElMessage.warning('请选择结束时间（时长由起止时间自动计算）'); return }
  if (!formSpanOk.value) { ElMessage.error('结束时间需晚于开始时间；跨零点请把结束时间选到次日'); return }
  saving.value = true
  try {
    // 不提交 duration_hours —— 时长由后端按「结束 − 开始」算，避免两处口径打架
    const payload = {
      task_name: editForm.task_name.trim(),
      task_description: editForm.task_description,
      start_time: editForm.start_time,
      end_time: editForm.end_time,
      notes: editForm.notes,
    }
    if (editingId.value) {
      await temporalApi.updateTask(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await temporalApi.createTask(payload)
      page.value = 1
      ElMessage.success(`已新增 ${(formSpanMin.value! / 60).toFixed(2)} 小时`)
    }
    editVisible.value = false
    loadTasks()
  } catch (e: any) {
    // 后端校验（结束 ≤ 开始）会把原因放在 end_time 字段上，透出来比「保存失败」有用
    const detail = e?.response?.data?.end_time
    ElMessage.error(Array.isArray(detail) ? detail[0] : (detail || '保存失败'))
  } finally { saving.value = false }
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
  .th-tip { border-bottom: 1px dashed #cbd5e1; cursor: help; }
  // 时长 ≠ 起止跨度（源数据本身如此），用琥珀色 + 星标提示，避免误读为「算错了」
  .dur-multi { color: #b45309; cursor: help;
    .dur-mark { font-style: normal; margin-left: 1px; }
  }
  // 弹窗内自动算出的时长（只读，不再手填）
  .dur-auto { display: flex; align-items: baseline; gap: 8px; font-size: 13px; color: #4b5563;
    .dur-value { font-size: 16px; font-weight: 600; color: #0f766e;
      small { margin-left: 2px; font-size: 11px; font-weight: 400; color: #64748b; } }
    .dur-hhmm { font-size: 12px; color: #94a3b8; }
    .dur-err { font-size: 12px; color: #dc2626; }
  }
}
</style>
