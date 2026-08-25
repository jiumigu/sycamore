<template>
  <div class="fixed-expense">
    <!-- 返回按钮由 ToolDetail 统一提供，勿在此重复添加 -->
    <h2 class="page-title">💰 固定开销计算器</h2>
    <p class="subtitle">知道自己每天睁开眼就要花多少钱</p>

    <el-card class="calc-form">
      <template #header><span class="card-title">⚙️ 开销设置</span></template>
      <el-alert v-if="editingId" title="正在编辑已有记录" type="info" show-icon :closable="false" style="margin-bottom:12px">
        <el-button size="small" text @click="cancelEdit">取消编辑</el-button>
      </el-alert>
      <el-form label-width="80px">
        <el-form-item label="记录名称">
          <el-input v-model="form.name" placeholder="如：当前生活成本" style="max-width: 320px" />
        </el-form-item>

        <div class="items-section">
          <div class="items-header">
            <span>开销项目</span>
            <el-button size="small" @click="addItem">+ 添加项目</el-button>
          </div>

          <div v-for="(item, index) in form.items" :key="index" class="item-row">
            <el-select v-model="item.icon" size="small" style="width: 60px">
              <el-option v-for="icon in iconOptions" :key="icon.value" :label="icon.value" :value="icon.value" />
            </el-select>
            <el-input v-model="item.name" size="small" placeholder="项目名" style="flex: 1; min-width: 200px" />
            <el-input-number v-model="item.amount" :min="0" :precision="2" size="small" style="width: 160px" />
            <el-select v-model="item.period" size="small" style="width: 90px">
              <el-option label="/天" value="daily" />
              <el-option label="/月" value="monthly" />
              <el-option label="/年" value="yearly" />
            </el-select>
            <el-button size="small" type="danger" @click="removeItem(index)" circle>✕</el-button>
          </div>
          <el-empty v-if="form.items.length === 0" description="暂无项目，点击「添加项目」" :image-size="40" />
        </div>

        <el-form-item label="备注">
          <el-input v-model="form.notes" placeholder="选填，记录计算时的想法" style="max-width: 320px" />
        </el-form-item>

        <el-form-item style="margin-top: 16px">
          <el-button type="primary" :loading="saving" @click="handleCalculate">计算</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 计算结果 -->
    <el-card v-if="result !== null" class="result-card" shadow="hover">
      <el-row :gutter="16">
        <el-col :span="8">
          <div class="big-number">
            <div class="label">每天睁开眼就要花</div>
            <div class="value">¥{{ fmt(result.total_daily) }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="big-number">
            <div class="label">每月固定开销</div>
            <div class="value">¥{{ fmt(result.total_monthly) }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="big-number highlight">
            <div class="label">每年固定开销</div>
            <div class="value">¥{{ fmt(result.total_yearly) }}</div>
          </div>
        </el-col>
      </el-row>

      <el-divider />

      <!-- 各项目换算明细 -->
      <div class="breakdown">
        <div v-for="item in positiveItems" :key="item.name + item.amount + item.period" class="breakdown-item">
          <div class="breakdown-head">
            <span class="breakdown-name">{{ item.icon }} {{ item.name }}</span>
            <span class="breakdown-original">原始 ¥{{ fmt(item.amount) }} / 每{{ periodUnit(item.period) }}</span>
          </div>
          <div class="breakdown-conversion">
            <span>每日 ¥{{ fmt(convertToDaily(item)) }}</span>
            <span class="arrow">→</span>
            <span>每月 ¥{{ fmt(convertToMonthly(item)) }}</span>
            <span class="arrow">→</span>
            <span>每年 ¥{{ fmt(convertToYearly(item)) }}</span>
          </div>
          <div class="breakdown-bar">
            <el-progress :percentage="getPercent(convertToDaily(item))" :stroke-width="6" :show-text="false" />
            <span class="breakdown-pct">{{ getPercent(convertToDaily(item)) }}%</span>
          </div>
        </div>
      </div>

      <el-alert v-if="insight" :title="insight" type="info" show-icon :closable="false" style="margin-top: 12px" />
    </el-card>

    <!-- 历史记录 -->
    <el-card class="history-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📋 计算历史</span>
          <el-tag size="small">{{ history.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="history" v-loading="loading" stripe size="small" style="width: 100%">
        <el-table-column label="名称" min-width="110">
          <template #default="{ row }">{{ row.name || '未命名记录' }}</template>
        </el-table-column>
        <el-table-column label="每天" width="90">
          <template #default="{ row }">¥{{ fmt(row.total_daily) }}</template>
        </el-table-column>
        <el-table-column label="每月" width="100">
          <template #default="{ row }">¥{{ fmt(row.total_monthly) }}</template>
        </el-table-column>
        <el-table-column label="每年" width="100">
          <template #default="{ row }">¥{{ fmt(row.total_yearly) }}</template>
        </el-table-column>
        <el-table-column label="项目数" width="70">
          <template #default="{ row }">{{ (row.items || []).length }}</template>
        </el-table-column>
        <el-table-column label="日期" width="100">
          <template #default="{ row }">{{ row.created_at?.slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="editRecord(row)">编辑</el-button>
            <el-button size="small" link type="primary" @click="copyAndEdit(row)">复制</el-button>
            <el-button size="small" link type="primary" @click="viewRecord(row)">查看</el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && history.length === 0" description="暂无计算记录" />
    </el-card>

    <!-- 查看详情 -->
    <el-dialog v-model="showDetailDialog" title="开销详情" width="650px" append-to-body>
      <template v-if="viewingRecord">
        <div class="detail-header">
          <span class="detail-name">{{ viewingRecord.name || '未命名记录' }}</span>
          <span class="detail-date">{{ viewingRecord.created_at?.slice(0, 10) }}</span>
        </div>

        <el-divider />

        <!-- 开销列表 -->
        <div class="expense-table">
          <div class="table-header">
            <span class="col-name">项目</span>
            <span class="col-original">原始金额</span>
            <span class="col-monthly">折合月均</span>
          </div>
          <div v-for="item in (viewingRecord.items || [])" :key="item.name + item.amount + item.period" class="table-row">
            <span class="col-name">{{ item.icon }} {{ item.name || '未命名项目' }}</span>
            <span class="col-original">¥{{ fmt(item.amount) }}/{{ periodLabel(item.period) }}</span>
            <span class="col-monthly">¥{{ fmt(convertToMonthly(item)) }}</span>
          </div>
        </div>
        <el-empty v-if="!viewingRecord.items?.length" description="无明细项目" :image-size="40" />

        <!-- 合计 -->
        <el-divider />
        <div class="detail-summary">
          <div class="summary-row">
            <span>月固定开销</span>
            <span class="summary-value">¥{{ fmt(viewingRecord.total_monthly) }}</span>
          </div>
          <div class="summary-row">
            <span>日固定开销</span>
            <span class="summary-value">¥{{ fmt(viewingRecord.total_daily) }}</span>
          </div>
        </div>

        <!-- 备注 -->
        <div v-if="viewingRecord.notes" class="detail-notes">
          <div class="notes-label">备注</div>
          <div class="notes-content">{{ viewingRecord.notes }}</div>
        </div>
      </template>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
        <el-button type="primary" @click="copyAndEdit(viewingRecord); showDetailDialog = false">复制并编辑</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getFixedExpenseList, createFixedExpense, updateFixedExpense, deleteFixedExpense } from '../../api/toolkitApi'
import type { FixedExpenseRecord } from '../../types/toolkitTypes'

type Period = 'daily' | 'monthly' | 'yearly'

interface ExpenseItem {
  name: string
  amount: number
  period: Period
  icon: string
}

const iconOptions = [
  { value: '🏠' }, { value: '💡' }, { value: '🌐' }, { value: '📱' },
  { value: '🚇' }, { value: '🍽️' }, { value: '📦' }, { value: '🛡️' },
  { value: '💰' }, { value: '🎓' }, { value: '🐱' }, { value: '☕' },
  { value: '🎬' }, { value: '💊' }, { value: '👗' }, { value: '🎮' },
  { value: '🏋️' }, { value: '✂️' }, { value: '🧹' },
]

// 周期 → 天数换算
const PERIOD_DAYS: Record<Period, number> = { daily: 1, monthly: 30, yearly: 365 }

const form = reactive({
  name: '',
  items: [
    { name: '房租', amount: 0, period: 'monthly' as Period, icon: '🏠' },
    { name: '餐饮', amount: 0, period: 'monthly' as Period, icon: '🍽️' },
  ] as ExpenseItem[],
  notes: '',
})

const result = ref<{ total_daily: number; total_monthly: number; total_yearly: number } | null>(null)
const insight = ref('')
const saving = ref(false)
const loading = ref(false)
const history = ref<FixedExpenseRecord[]>([])

const editingId = ref<number | null>(null)
const showDetailDialog = ref(false)
const viewingRecord = ref<FixedExpenseRecord | null>(null)

const positiveItems = computed(() => form.items.filter(i => i.amount > 0))

function fmt(val: number | string) {
  const n = typeof val === 'string' ? parseFloat(val) : val
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function periodUnit(period: Period): string {
  return { daily: '天', monthly: '月', yearly: '年' }[period]
}

function periodLabel(period: Period): string {
  return { daily: '日', monthly: '月', yearly: '年' }[period]
}

// 统一换算：任意周期 → 每日等价金额
function convertToDaily(item: ExpenseItem): number {
  return Math.round((item.amount / PERIOD_DAYS[item.period]) * 100) / 100
}

function convertToMonthly(item: ExpenseItem): number {
  return Math.round(convertToDaily(item) * 30 * 100) / 100
}

function convertToYearly(item: ExpenseItem): number {
  return Math.round(convertToDaily(item) * 365 * 100) / 100
}

function addItem() {
  form.items.push({ name: '', amount: 0, period: 'monthly', icon: '💰' })
}

function removeItem(index: number) {
  form.items.splice(index, 1)
}

function getPercent(daily: number) {
  const total = positiveItems.value.reduce((sum, i) => sum + convertToDaily(i), 0)
  if (total <= 0) return 0
  return Math.round((daily / total) * 100)
}

function generateInsight(totalDaily: number, totalMonthly: number, totalYearly: number): string {
  if (totalDaily <= 0) return '先填上各项金额，才能看清每个月的固定成本。'
  if (totalDaily < 50) return `日均 ¥${fmt(totalDaily)}，固定开销很克制，这些成本没给你太大压力，可以把更多钱花在真正在意的事上。`
  if (totalDaily < 150) return `日均 ¥${fmt(totalDaily)}，每年约 ¥${fmt(totalYearly)}，每月留出 ¥${fmt(totalMonthly)} 预算即可，心里有数就不慌。`
  return `日均 ¥${fmt(totalDaily)} 不算低，每年要 ¥${fmt(totalYearly)}，建议逐项复盘：哪些是必要、哪些可以砍掉，省下的都是纯利润。`
}

async function fetchHistory() {
  loading.value = true
  try {
    const res = await getFixedExpenseList()
    history.value = (res.data?.results || []) as FixedExpenseRecord[]
  } catch {
    history.value = []
  } finally {
    loading.value = false
  }
}

async function handleCalculate() {
  if (form.items.length === 0) {
    ElMessage.warning('请先添加开销项目')
    return
  }
  const totalDaily = positiveItems.value.reduce((sum, i) => sum + convertToDaily(i), 0)
  const totalMonthly = Math.round(totalDaily * 30 * 100) / 100
  const totalYearly = Math.round(totalDaily * 365 * 100) / 100
  result.value = { total_daily: totalDaily, total_monthly: totalMonthly, total_yearly: totalYearly }
  insight.value = generateInsight(totalDaily, totalMonthly, totalYearly)

  const data = {
    name: form.name || '未命名记录',
    items: form.items,
    notes: form.notes,
    total_monthly: totalMonthly,
    total_daily: totalDaily,
    total_yearly: totalYearly,
  }

  saving.value = true
  try {
    if (editingId.value) {
      await updateFixedExpense(editingId.value, data)
      ElMessage.success('已更新')
    } else {
      await createFixedExpense(data)
      ElMessage.success('已保存到历史')
    }
    editingId.value = null
    await fetchHistory()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function resetForm() {
  form.name = ''
  form.items = [
    { name: '房租', amount: 0, period: 'monthly', icon: '🏠' },
    { name: '餐饮', amount: 0, period: 'monthly', icon: '🍽️' },
  ]
  form.notes = ''
  result.value = null
  insight.value = ''
}

function editRecord(record: FixedExpenseRecord) {
  editingId.value = record.id
  form.name = record.name || ''
  form.items = (record.items || []).map(item => ({ ...item }))
  form.notes = record.notes || ''
  result.value = null
  insight.value = ''
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function copyAndEdit(record: FixedExpenseRecord | null) {
  if (!record) return
  editingId.value = null
  form.name = record.name ? `${record.name}（副本）` : ''
  form.items = (record.items || []).map(item => ({ ...item }))
  form.notes = record.notes || ''
  result.value = null
  insight.value = ''
  ElMessage.success('已填充表单，修改后点击「计算」保存为新记录')
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function viewRecord(record: FixedExpenseRecord) {
  viewingRecord.value = record
  showDetailDialog.value = true
}

function cancelEdit() {
  editingId.value = null
  resetForm()
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这条记录？', '确认删除', { type: 'warning' })
    await deleteFixedExpense(id)
    ElMessage.success('已删除')
    await fetchHistory()
  } catch { /* cancelled */ }
}

onMounted(fetchHistory)
</script>

<style scoped lang="scss">
.fixed-expense {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;

  .page-title {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    color: #1F2937;
  }

  .subtitle {
    margin: -8px 0 0;
    font-size: 13px;
    color: #6B7280;
  }

  .card-title { font-size: 14px; font-weight: 600; }
  .card-header { display: flex; align-items: center; gap: 10px; }

  .calc-form :deep(.el-card__body) { padding: 16px 20px; }

  .items-section {
    margin-bottom: 16px;

    .items-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 14px;
      font-weight: 500;
      color: #374151;
      margin-bottom: 8px;
    }

    .item-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
  }

  .result-card {
    border: 1px solid var(--el-color-primary-light-5);
    :deep(.el-card__body) { padding: 20px; }

    .big-number {
      text-align: center;
      padding: 8px 0;

      .label {
        font-size: 12px;
        color: #6B7280;
        margin-bottom: 6px;
      }
      .value {
        font-size: 32px;
        font-weight: 800;
        color: #1F2937;
        line-height: 1.1;
      }
      &.highlight .value { color: var(--el-color-primary); }
    }

    .breakdown {
      display: flex;
      flex-direction: column;
      gap: 12px;

      .breakdown-head {
        display: flex;
        justify-content: space-between;
        font-size: 13px;
        color: #374151;
        margin-bottom: 4px;

        .breakdown-original { font-size: 12px; color: #9CA3AF; }
      }
      .breakdown-conversion {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        color: #6B7280;
        margin-bottom: 6px;

        .arrow { color: #C4C6CC; }
      }
      .breakdown-bar {
        display: flex;
        align-items: center;
        gap: 8px;

        :deep(.el-progress) { flex: 1; }
        .breakdown-pct {
          font-size: 12px;
          color: #6B7280;
          flex-shrink: 0;
          min-width: 36px;
          text-align: right;
        }
      }
    }
  }

  .history-card :deep(.el-card__body) { padding: 12px 16px 16px; }
}

/* 详情弹窗内容被 append-to-body 挂载到 body，须顶层作用域才能命中 */
.detail-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;

  .detail-name { font-size: 16px; font-weight: 600; color: #1F2937; }
  .detail-date { font-size: 12px; color: #9CA3AF; }
}

.expense-table {
  .table-header {
    display: flex;
    padding: 8px 0;
    font-size: 12px;
    color: #999;
    border-bottom: 1px solid #eee;
  }

  .table-row {
    display: flex;
    padding: 8px 0;
    border-bottom: 1px solid #f5f5f5;
    font-size: 14px;

    &:last-child { border-bottom: none; }
  }

  .col-name {
    flex: 1;
    min-width: 0;
  }

  .col-original {
    width: 150px;
    text-align: right;
    color: #666;
  }

  .col-monthly {
    width: 120px;
    text-align: right;
    font-weight: 500;
  }
}

.detail-summary {
  .summary-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    font-size: 15px;

    .summary-value {
      font-weight: 700;
      font-size: 18px;
      color: #409eff;
    }
  }
}

.detail-notes {
  margin-top: 12px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;

  .notes-label {
    font-size: 12px;
    color: #999;
    margin-bottom: 4px;
  }

  .notes-content {
    font-size: 13px;
    color: #666;
    line-height: 1.6;
    white-space: pre-wrap;
  }
}
</style>
