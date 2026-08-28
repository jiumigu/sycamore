<template>
  <div class="cashflow-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">现金实时盘点</h1>
        <el-tag type="warning" class="module-tag">财务维度</el-tag>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openNewDialog">
          <el-icon><Plus /></el-icon>
          新增盘点
        </el-button>
        <el-button @click="switchToMonthly">
          <el-icon><Calendar /></el-icon>
          月度日历
        </el-button>
        <el-button @click="switchToReview">
          <el-icon><DataAnalysis /></el-icon>
          月度复盘
        </el-button>
        <el-button @click="switchToHeatmap">
          <el-icon><Grid /></el-icon>
          热力图
        </el-button>
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="billDialogVisible = true; loadBills()">
          📋 账单清单
        </el-button>
      </div>
    </div>

    <!-- 资产全景 + 健康指标 -->
    <el-row :gutter="16" class="cashflow-top-row">
      <el-col :xs="24" :md="16">
        <el-card shadow="never" class="equal-height-card">
          <AssetOverview :overview="store.overview" :loading="store.overviewLoading" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="equal-height-card">
          <HealthMetrics
            :metrics="store.overview?.health_metrics ?? null"
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- 资产趋势 -->
    <el-card shadow="never" class="section-card">
      <AssetTrend
        :data="store.trendData"
        :months="trendMonths"
        @update:months="handleTrendMonthsChange"
      />
    </el-card>

    <!-- 盘点历史列表 -->
    <el-card shadow="never" class="section-card">
      <SnapshotHistory
        :items="store.snapshotList?.items ?? []"
        :total="store.snapshotList?.total ?? 0"
        :loading="store.listLoading"
        @edit="handleEditSnapshot"
        @delete="handleDeleteSnapshot"
        @page-change="handleSnapshotPageChange"
      />
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="showFormDialog"
      :title="editingId ? '编辑盘点' : '新增盘点'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="年月">
          <el-date-picker v-model="form.yearmon" type="month" value-format="YYYY-MM" style="width:100%" />
        </el-form-item>

        <el-form-item label="盘点日期">
          <el-date-picker v-model="form.btime" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="支付宝">
              <el-input-number v-model="form.zplay" :precision="2" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="微信">
              <el-input-number v-model="form.wechat" :precision="2" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="现金">
              <el-input-number v-model="form.cash" :precision="2" :min="0" :step="500" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="建行">
              <el-input-number v-model="form.jianbank" :precision="2" :min="0" :step="10000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="工行">
              <el-input-number v-model="form.gongbank" :precision="2" :min="0" :step="10000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="中国银行">
              <el-input-number v-model="form.zhongbank" :precision="2" :min="0" :step="10000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="农信社">
              <el-input-number v-model="form.nongbank" :precision="2" :min="0" :step="10000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="公积金">
              <el-input-number v-model="form.accumulationfund" :precision="2" :min="0" :step="10000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="负债">
              <el-input-number v-model="form.borrow" :precision="2" :min="0" :step="10000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="借出">
              <el-input-number v-model="form.lend" :precision="2" :min="0" :step="10000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <el-input v-model="form.remarks" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showFormDialog = false">取消</el-button>
        <el-button :loading="store.saving" @click="handleCopy">复制上月</el-button>
        <el-button type="primary" :loading="store.saving" @click="handleSave">
          {{ editingId ? '更新' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>

  <!-- 账单清单弹窗 -->
  <el-dialog v-model="billDialogVisible" title="📋 账单清单" width="960px" :close-on-click-modal="false">
    <div style="margin-bottom:10px;display:flex;gap:10px;align-items:center">
      <el-button size="small" type="primary" @click="openBillForm()">+ 新增账单</el-button>
      <el-select v-model="billTypeFilter" size="small" style="width:110px" placeholder="类型" clearable @change="loadBills">
        <el-option label="收入" value="收入" />
        <el-option label="支出" value="支出" />
      </el-select>
      <el-date-picker v-model="billDateRange" size="small" type="daterange" value-format="YYYY-MM-DD"
        start-placeholder="开始" end-placeholder="结束" style="width:240px" @change="loadBills" />
      <el-button size="small" @click="billTypeFilter=''; billDateRange=null; loadBills()">重置</el-button>
      <span class="hint" style="margin-left:auto">共 {{ billTotal }} 条 · 备注可编辑完善</span>
    </div>
    <el-table :data="bills" v-loading="billsLoading" stripe size="small" max-height="420">
      <el-table-column label="日期" width="150">
        <template #default="{ row }">{{ (row.date || '').slice(0, 10) }}</template>
      </el-table-column>
      <el-table-column label="类型" width="70" prop="transaction_type" />
      <el-table-column label="金额" width="90" align="right">
        <template #default="{ row }">¥{{ Number(row.amount).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="分类" width="80" prop="category" />
      <el-table-column label="商户" width="110" prop="merchant" show-overflow-tooltip />
      <el-table-column label="备注" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.notes || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link @click="openBillForm(row)">编辑</el-button>
          <el-button size="small" link type="danger" @click="handleDeleteBill(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="billPage" :page-size="20" :total="billTotal" layout="prev, pager, next" small
      style="margin-top:12px;justify-content:center" @current-change="loadBills" />
  </el-dialog>

  <!-- 账单新增/编辑弹窗 -->
  <el-dialog v-model="billFormVisible" :title="billEditingId ? '编辑账单' : '新增账单'" width="520px">
    <el-form :model="billForm" label-width="80px" size="small">
      <el-row :gutter="10">
        <el-col :span="12">
          <el-form-item label="类型" required>
            <el-select v-model="billForm.transaction_type" style="width:100%">
              <el-option label="收入" value="收入" />
              <el-option label="支出" value="支出" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="金额" required>
            <el-input-number v-model="billForm.amount" :min="0" :precision="2" style="width:100%" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="10">
        <el-col :span="12">
          <el-form-item label="日期">
            <el-date-picker v-model="billForm.date" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="分类">
            <el-input v-model="billForm.category" placeholder="餐饮/交通…" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="10">
        <el-col :span="12">
          <el-form-item label="商户">
            <el-input v-model="billForm.merchant" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="子分类">
            <el-input v-model="billForm.subcategory" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="备注">
        <el-input v-model="billForm.notes" type="textarea" :rows="2" placeholder="完善这笔账单的备注说明" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button size="small" @click="billFormVisible = false">取消</el-button>
      <el-button size="small" type="primary" :loading="billSaving" @click="saveBill">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Calendar, DataAnalysis, Grid } from '@element-plus/icons-vue'
import { useCashflowStore } from '../stores/cashflowStore'
import * as wealthApi from '../api/wealthApi'
import AssetOverview from '../components/cashflow/AssetOverview.vue'
import AssetTrend from '../components/cashflow/AssetTrend.vue'
import HealthMetrics from '../components/cashflow/HealthMetrics.vue'
import SnapshotHistory from '../components/cashflow/SnapshotHistory.vue'
import type { SnapshotListItem, SnapshotFormData } from '../types/wealthTypes'

const router = useRouter()
const store = useCashflowStore()

const trendMonths = ref(12)
const showFormDialog = ref(false)
const editingId = ref<number | null>(null)

const form = reactive({
  yearmon: '',
  btime: '',
  zplay: 0,
  wechat: 0,
  cash: 0,
  jianbank: 0,
  gongbank: 0,
  zhongbank: 0,
  nongbank: 0,
  accumulationfund: 0,
  lend: 0,
  borrow: 0,
  remarks: '',
})

function resetForm() {
  form.yearmon = ''
  form.btime = ''
  form.zplay = 0
  form.wechat = 0
  form.cash = 0
  form.jianbank = 0
  form.gongbank = 0
  form.zhongbank = 0
  form.nongbank = 0
  form.accumulationfund = 0
  form.lend = 0
  form.borrow = 0
  form.remarks = ''
}

function openNewDialog() {
  editingId.value = null
  resetForm()
  showFormDialog.value = true
}

function switchToMonthly() {
  router.push('/wealth/monthly')
}
function switchToReview() {
  router.push('/wealth/review')
}
function switchToHeatmap() {
  router.push('/wealth/heatmap')
}

function handleRefresh() {
  store.fetchOverview()
  store.fetchTrend(trendMonths.value)
  store.fetchSnapshotList()
}

function handleTrendMonthsChange(val: number) {
  trendMonths.value = val
  store.fetchTrend(val || 99)
}

async function handleCopy() {
  const now = new Date()
  const ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0')
  try {
    await store.copyLastMonth(ym)
    if (store.overview && store.overview.yearmon === ym) {
      const a = store.overview.accounts
      form.yearmon = ym
      form.btime = store.overview.snapshot_date || ''
      form.zplay = a.zplay
      form.wechat = a.wechat
      form.cash = a.cash
      form.jianbank = a.jianbank
      form.gongbank = a.gongbank
      form.zhongbank = a.zhongbank
      form.nongbank = a.nongbank
      form.accumulationfund = a.accumulationfund
      form.lend = store.overview.summary.lend
      form.borrow = store.overview.summary.borrow
      form.remarks = ''
    }
    ElMessage.success('已复制上月数据')
  } catch {
    ElMessage.warning('上月无盘点记录')
  }
}

async function handleSave() {
  const formData: SnapshotFormData = {
    yearmon: form.yearmon,
    btime: form.btime || undefined,
    zplay: form.zplay,
    wechat: form.wechat,
    cash: form.cash,
    jianbank: form.jianbank,
    gongbank: form.gongbank,
    zhongbank: form.zhongbank,
    nongbank: form.nongbank,
    accumulationfund: form.accumulationfund,
    lend: form.lend,
    borrow: form.borrow,
    remarks: form.remarks,
  }
  try {
    if (editingId.value) {
      await store.updateSnapshot(formData)
    } else {
      await store.saveSnapshot(formData)
    }
    showFormDialog.value = false
    editingId.value = null
  } catch {
    /* error handled by store */
  }
}

function handleEditSnapshot(row: SnapshotListItem) {
  editingId.value = row.baid
  form.yearmon = row.yearmon || ''
  form.btime = row.btime || ''
  form.zplay = row.zplay
  form.wechat = row.wechat
  form.cash = row.cash
  form.jianbank = row.jianbank
  form.gongbank = row.gongbank
  form.zhongbank = row.zhongbank
  form.nongbank = row.nongbank
  form.accumulationfund = row.accumulationfund
  form.lend = row.lend
  form.borrow = row.borrow
  form.remarks = row.remarks || ''
  showFormDialog.value = true
}

function handleDeleteSnapshot(baid: number) {
  store.removeSnapshot(baid)
}

function handleSnapshotPageChange(page: number) {
  store.fetchSnapshotList(page)
}

onMounted(() => {
  store.fetchOverview()
  store.fetchTrend(12)
  store.fetchSnapshotList()
})

// ─── 账单清单 CRUD ───
const billDialogVisible = ref(false)
const billFormVisible = ref(false)
const bills = ref<any[]>([])
const billsLoading = ref(false)
const billTotal = ref(0)
const billPage = ref(1)
const billSaving = ref(false)
const billEditingId = ref<number | null>(null)
const billTypeFilter = ref('')
const billDateRange = ref<[string, string] | null>(null)
const billForm = reactive({
  transaction_type: '支出', amount: 0, date: '', category: '', subcategory: '',
  merchant: '', notes: '',
})

async function loadBills() {
  billsLoading.value = true
  try {
    const params: Record<string, unknown> = { page: billPage.value, page_size: 20 }
    if (billTypeFilter.value) params.transaction_type = billTypeFilter.value
    if (billDateRange.value?.length === 2) {
      params.date_from = billDateRange.value[0]
      params.date_to = billDateRange.value[1]
    }
    const res = await wealthApi.getBills(params)
    const data = res.data
    bills.value = (data.results || data) as any[]
    billTotal.value = data.count ?? bills.value.length
  } catch { bills.value = [] } finally { billsLoading.value = false }
}

function openBillForm(row?: any) {
  billEditingId.value = row?.id ?? null
  billForm.transaction_type = row?.transaction_type || '支出'
  billForm.amount = row?.amount != null ? Number(row.amount) : 0
  billForm.date = row?.date || ''
  billForm.category = row?.category || ''
  billForm.subcategory = row?.subcategory || ''
  billForm.merchant = row?.merchant || ''
  billForm.notes = row?.notes || ''
  billFormVisible.value = true
}

async function saveBill() {
  if (!billForm.amount) { ElMessage.warning('请输入金额'); return }
  billSaving.value = true
  try {
    const payload = { ...billForm, date: billForm.date || new Date().toISOString().slice(0, 19).replace('T', ' ') }
    if (billEditingId.value) {
      await wealthApi.updateBill(billEditingId.value, payload)
    } else {
      await wealthApi.createBillRecord(payload)
    }
    ElMessage.success('保存成功')
    billFormVisible.value = false
    loadBills()
  } catch { ElMessage.error('保存失败') } finally { billSaving.value = false }
}

async function handleDeleteBill(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除这笔账单（${row.date?.slice(0, 10)} ¥${row.amount}）？`, '删除确认', { type: 'warning' })
    await wealthApi.deleteBill(row.id)
    ElMessage.success('已删除')
    loadBills()
  } catch { /* 取消 */ }
}

</script>

<style scoped>
.cashflow-view {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}
.module-tag { font-size: 12px; }
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.section-card {
  margin-bottom: 16px;
}
.section-card :deep(.el-card__body) { padding: 20px; }

/* 顶部卡片等高对齐 */
.cashflow-top-row {
  margin-bottom: 16px;
  .el-col {
    display: flex;
  }
}
.equal-height-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  :deep(.el-card__body) {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .header-actions { width: 100%; justify-content: flex-start; }
}
</style>
