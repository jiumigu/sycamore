<template>
  <div class="bill-list-view">
    <!-- 支出必要性小结（必要/可选/冲动/未标记） -->
    <div class="necessity-summary">
      <span class="sum-label"><el-icon><DataAnalysis /></el-icon> 支出小结</span>
      <span v-for="s in statsList" :key="s.necessity" class="sum-item">
        <el-tag :type="necessityTagType(s.necessity)" size="small" effect="plain">
          {{ s.necessity === 'unmarked' ? '未标记' : s.necessity }}
        </el-tag>
        {{ s.count }} 笔
        <b>¥{{ s.total.toLocaleString() }}</b>
      </span>
      <span class="sum-grand">共 {{ statsGrand.count }} 笔 / ¥{{ statsGrand.total.toLocaleString() }}</span>
    </div>

    <!-- 工具条 -->
    <div class="bill-toolbar">
      <el-button type="primary" @click="openForm()">
        <el-icon><Plus /></el-icon>新增账单
      </el-button>

      <el-dropdown trigger="click" :disabled="!canBatch" @command="applyBatch">
        <el-button :disabled="!canBatch">
          批量标记<el-badge v-if="selectedExpenseCount" :value="selectedExpenseCount" class="batch-badge" />
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="n in NECESSITY_CHOICES" :key="n" :command="n">
              <el-tag :type="necessityTagType(n)" size="small" effect="plain">{{ n }}</el-tag>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-select
        v-model="necessityFilter" size="small" clearable placeholder="必要性" style="width: 110px"
        @change="reloadFromFilter"
      >
        <el-option v-for="o in necessityFilterOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>

      <el-select v-model="billTypeFilter" size="small" clearable placeholder="类型" style="width: 96px" @change="reloadFromFilter">
        <el-option label="收入" value="收入" />
        <el-option label="支出" value="支出" />
      </el-select>

      <el-date-picker
        v-model="billDateRange" size="small" type="daterange" value-format="YYYY-MM-DD"
        start-placeholder="开始" end-placeholder="结束" style="width: 236px"
        @change="onRangeChange"
      />

      <el-input
        v-model="billSearch" placeholder="搜索备注 / 商户 / 分类" clearable size="small" style="width: 190px"
        @keyup.enter="applySearch" @clear="applySearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <el-button size="small" @click="resetFilters">重置</el-button>
      <span class="total-hint">共 {{ billTotal }} 条</span>
    </div>

    <!-- 表格 -->
    <el-table
      :data="bills" v-loading="billsLoading" stripe size="small" max-height="480"
      @selection-change="(rows: any[]) => (selectedRows = rows)"
    >
      <el-table-column type="selection" width="42" :selectable="(row: any) => row.transaction_type === '支出'" />
      <el-table-column label="日期" width="104">
        <template #default="{ row }">{{ (row.date || '').slice(0, 10) }}</template>
      </el-table-column>
      <el-table-column label="类型" width="56" prop="transaction_type" />
      <el-table-column label="金额" width="96" align="right">
        <template #default="{ row }">
          <span :class="row.transaction_type === '收入' ? 'amount income' : 'amount'">
            {{ row.transaction_type === '收入' ? '+' : '-' }}¥{{ Number(row.amount).toLocaleString() }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="必要性" width="106">
        <template #default="{ row }">
          <el-select
            v-if="row.transaction_type === '支出'"
            size="small" :model-value="row.necessity || ''" style="width: 100px"
            @change="(v: string) => onRowNecessityChange(row, v)"
          >
            <el-option v-for="o in necessitySelectOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="分类" width="72" prop="category" />
      <el-table-column label="商户" width="104" prop="merchant" show-overflow-tooltip />
      <el-table-column label="备注" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.notes || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link @click="openForm(row)">编辑</el-button>
          <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="billPage" :page-size="PAGE_SIZE" :total="billTotal"
      layout="prev, pager, next" small style="margin-top: 10px; justify-content: center"
      @current-change="loadBills"
    />

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="editingId ? '编辑账单' : '新增账单'" width="520px" :close-on-click-modal="false">
      <el-form :model="form" label-width="80px" size="small">
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="类型" required>
              <el-select v-model="form.transaction_type" style="width: 100%" @change="onTypeChange">
                <el-option label="收入" value="收入" />
                <el-option label="支出" value="支出" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="金额" required>
              <el-input-number v-model="form.amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="form.transaction_type === '支出'" label="必要性">
          <el-radio-group v-model="form.necessity">
            <el-radio-button v-for="n in NECESSITY_CHOICES" :key="n" :value="n">{{ n }}</el-radio-button>
            <el-radio-button value="">不标记</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="日期">
              <el-date-picker v-model="form.date" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类">
              <el-input v-model="form.category" placeholder="餐饮/交通…" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="商户">
              <el-input v-model="form.merchant" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="子分类">
              <el-input v-model="form.subcategory" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="完善这笔账单的备注说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="formVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="saveBill">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, DataAnalysis } from '@element-plus/icons-vue'
import * as wealthApi from '../api/wealthApi'

/** 外部（月度日历）联动年月：默认按该月筛选 */
const props = defineProps<{ year?: number; month?: number }>()

const NECESSITY_CHOICES = ['必要', '可选', '冲动'] as const
const PAGE_SIZE = 20

const NECESSITY_TAG: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  必要: 'success', 可选: 'warning', 冲动: 'danger', unmarked: 'info',
}
function necessityTagType(v: string) {
  return NECESSITY_TAG[v] || 'info'
}
const necessityFilterOptions = [
  { label: '未标记', value: 'unmarked' },
  ...NECESSITY_CHOICES.map((n) => ({ label: n, value: n })),
]
const necessitySelectOptions = [
  ...NECESSITY_CHOICES.map((n) => ({ label: n, value: n })),
  { label: '未标记', value: '' },
]

// ─── 列表 ───
const bills = ref<any[]>([])
const billsLoading = ref(false)
const billTotal = ref(0)
const billPage = ref(1)
const selectedRows = ref<any[]>([])

// ─── 筛选 ───
const billTypeFilter = ref('')
const necessityFilter = ref('')
const billSearch = ref('')
const billDateRange = ref<[string, string] | null>(null)
const rangeTouched = ref(false) // 用户是否手动改过日期范围（改过则脱离年月联动）

const defaultMonthRange = computed<[string, string] | null>(() => {
  if (!props.year || !props.month) return null
  const lastDay = new Date(props.year, props.month, 0).getDate()
  const p = (n: number) => String(n).padStart(2, '0')
  return [`${props.year}-${p(props.month)}-01`, `${props.year}-${p(props.month)}-${p(lastDay)}`]
})

watch(
  () => [props.year, props.month],
  () => {
    if (rangeTouched.value) return
    billDateRange.value = defaultMonthRange.value
    billPage.value = 1
    loadBills()
    loadStats()
  },
)

function onRangeChange(val: [string, string] | null) {
  rangeTouched.value = true
  billDateRange.value = val
  billPage.value = 1
  loadBills()
  loadStats()
}
function reloadFromFilter() {
  billPage.value = 1
  loadBills()
}
function applySearch() {
  billPage.value = 1
  loadBills()
}
function resetFilters() {
  billTypeFilter.value = ''
  necessityFilter.value = ''
  billSearch.value = ''
  rangeTouched.value = false
  billDateRange.value = defaultMonthRange.value
  billPage.value = 1
  loadBills()
  loadStats()
}

function listParams() {
  const params: Record<string, unknown> = { page: billPage.value, page_size: PAGE_SIZE }
  if (billTypeFilter.value) params.transaction_type = billTypeFilter.value
  if (necessityFilter.value) params.necessity = necessityFilter.value
  if (billDateRange.value?.length === 2) {
    params.date_from = billDateRange.value[0]
    params.date_to = billDateRange.value[1]
  }
  if (billSearch.value.trim()) params.search = billSearch.value.trim()
  return params
}

async function loadBills() {
  billsLoading.value = true
  try {
    const res = await wealthApi.getBills(listParams())
    const data = res.data
    bills.value = (data.results || data) as any[]
    billTotal.value = data.count ?? bills.value.length
  } catch {
    bills.value = []
  } finally {
    billsLoading.value = false
  }
}

// ─── 必要性小结（仅支出，按当前日期范围统计） ───
const statsList = ref<{ necessity: string; count: number; total: number }[]>([])
const statsGrand = ref({ count: 0, total: 0 })

async function loadStats() {
  try {
    const params: Record<string, unknown> = { transaction_type: '支出' }
    if (billDateRange.value?.length === 2) {
      params.date_from = billDateRange.value[0]
      params.date_to = billDateRange.value[1]
    }
    const res = await wealthApi.getNecessityStats(params)
    statsList.value = (res.data?.summary || []).filter((s: any) => s.count > 0)
    statsGrand.value = {
      count: res.data?.grand_count ?? 0,
      total: res.data?.grand_total ?? 0,
    }
  } catch {
    statsList.value = []
    statsGrand.value = { count: 0, total: 0 }
  }
}

// ─── 批量标记 ───
const selectedExpenseCount = computed(
  () => selectedRows.value.filter((r) => r.transaction_type === '支出').length,
)
const canBatch = computed(() => selectedExpenseCount.value > 0)

async function applyBatch(necessity: string) {
  if (!canBatch.value) return
  const ids = selectedRows.value.filter((r) => r.transaction_type === '支出').map((r) => r.id)
  try {
    const res = await wealthApi.batchSetNecessity(ids, necessity)
    ElMessage.success(`已批量标记 ${res.data?.updated ?? ids.length} 笔为「${necessity}」`)
    selectedRows.value = []
    loadBills()
    loadStats()
  } catch {
    ElMessage.error('批量标记失败')
  }
}

// ─── 行内快速改必要性 ───
async function onRowNecessityChange(row: any, val: string) {
  const prev = row.necessity || ''
  row.necessity = val
  try {
    await wealthApi.updateBill(row.id, { necessity: val })
    loadStats()
  } catch {
    row.necessity = prev
    ElMessage.error('修改失败')
  }
}

// ─── 新增 / 编辑 ───
const formVisible = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  transaction_type: '支出', amount: 0, date: '', category: '', subcategory: '',
  merchant: '', notes: '', necessity: '',
})

function openForm(row?: any) {
  editingId.value = row?.id ?? null
  form.transaction_type = row?.transaction_type || '支出'
  form.amount = row?.amount != null ? Number(row.amount) : 0
  form.date = row?.date || ''
  form.category = row?.category || ''
  form.subcategory = row?.subcategory || ''
  form.merchant = row?.merchant || ''
  form.notes = row?.notes || ''
  form.necessity = row?.transaction_type === '支出' ? (row?.necessity || '') : ''
  formVisible.value = true
}

function onTypeChange(t: string) {
  if (t === '收入') form.necessity = ''
}

async function saveBill() {
  if (!form.amount) {
    ElMessage.warning('请输入金额')
    return
  }
  saving.value = true
  try {
    const payload: Record<string, unknown> = { ...form }
    if (form.transaction_type === '收入') payload.necessity = ''
    payload.date = form.date || new Date().toISOString().slice(0, 19).replace('T', ' ')
    if (editingId.value) {
      await wealthApi.updateBill(editingId.value, payload)
    } else {
      await wealthApi.createBillRecord(payload)
    }
    ElMessage.success('保存成功')
    formVisible.value = false
    loadBills()
    loadStats()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认删除这笔账单（${row.date?.slice(0, 10)} ¥${row.amount}）？`,
      '删除确认', { type: 'warning' },
    )
    await wealthApi.deleteBill(row.id)
    ElMessage.success('已删除')
    loadBills()
    loadStats()
  } catch { /* 取消 */ }
}

onMounted(() => {
  billDateRange.value = defaultMonthRange.value
  loadBills()
  loadStats()
})
</script>

<style scoped>
.bill-list-view {
  /* 默认无外层内边距，由父卡片容器控制 */
}

.necessity-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--el-text-color-regular);

  .sum-label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }
  .sum-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    b { color: var(--el-text-color-primary); }
  }
  .sum-grand {
    margin-left: auto;
    color: var(--el-text-color-secondary);
    b { color: #f56c6c; }
  }
}

.bill-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;

  .total-hint {
    margin-left: auto;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
  .batch-badge {
    margin-left: 2px;
    :deep(.el-badge__content) { font-size: 10px; }
  }
}

.amount {
  color: #67c23a;
  &.income { color: #f56c6c; }
}
.muted { color: var(--el-text-color-placeholder); }
</style>
