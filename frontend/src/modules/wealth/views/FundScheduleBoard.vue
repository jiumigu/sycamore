<template>
  <div class="fund-schedule-board">
    <!-- 基本信息：手里现金 + 计划名称 -->
    <el-card shadow="hover" class="board-card">
      <div class="info-form">
        <div class="field">
          <span class="field-label">💵 手里现金</span>
          <el-input-number v-model="cashOnHand" :min="0" :precision="2" :controls="false" style="width: 220px" />
        </div>
        <div class="field">
          <span class="field-label">📝 计划名称</span>
          <el-input v-model="planName" placeholder="如：8月资金安排" style="width: 280px" />
        </div>
      </div>
    </el-card>

    <!-- 预留项 -->
    <el-card shadow="hover" class="board-card">
      <template #header>
        <div class="section-header">
          <span>📌 预留项 <span class="hint">预留 = 打算留作某用途的钱</span></span>
          <div class="header-actions">
            <el-button size="small" type="danger" plain @click="addReserveItem('hard')">+ 硬性承诺</el-button>
            <el-button size="small" type="warning" plain @click="addReserveItem('soft')">+ 弹性预留</el-button>
            <el-button size="small" type="success" @click="openExpenseSelect">📥 导入固定开销</el-button>
          </div>
        </div>
      </template>

      <div v-if="reserveItems.length === 0" class="empty-state">
        暂无预留项，点击上方按钮添加，或从「固定开销计算器」导入
      </div>
      <div v-for="(item, index) in reserveItems" :key="index" class="reserve-row">
        <el-tag :type="item.type === 'hard' ? 'danger' : 'warning'" size="small">
          {{ item.type === 'hard' ? '硬性' : '弹性' }}
        </el-tag>
        <el-input v-model="item.name" size="small" placeholder="项目名" style="width: 200px" />
        <el-input-number v-model="item.amount" :min="0" :precision="2" :controls="false" size="small" style="width: 160px" />
        <el-button size="small" type="danger" text circle @click="removeReserveItem(index)">✕</el-button>
      </div>
    </el-card>

    <!-- 汇总 -->
    <el-card shadow="hover" class="board-card summary-card">
      <div class="summary-row">
        <div class="summary-item">
          <div class="summary-label">手里现金</div>
          <div class="summary-value">{{ fmt(cashOnHand) }}</div>
        </div>
        <div class="summary-item">
          <div class="summary-label">预留合计</div>
          <div class="summary-value" style="color: #e6a23c">{{ fmt(totalReserved) }}</div>
        </div>
        <div class="summary-item">
          <div class="summary-label">剩余可分配</div>
          <div class="summary-value" :style="{ color: remainingAmount < 0 ? '#f56c6c' : '#67c23a' }">
            {{ fmt(remainingAmount) }}
          </div>
        </div>
      </div>
      <el-alert
        v-if="balanceMismatch"
        type="error"
        :closable="false"
        :title="`金额不匹配：现金(${fmt(cashOnHand)}) ≠ 预留(${fmt(totalReserved)}) + 剩余(${fmt(remainingAmount)})`"
        style="margin-top: 12px"
      />
      <div class="save-row">
        <el-button type="primary" :loading="saving" :disabled="saving" @click="savePlan">保存计划</el-button>
        <span class="hint">每次保存生成一条历史快照</span>
      </div>
    </el-card>

    <!-- 历史计划 -->
    <el-card shadow="hover" class="board-card">
      <template #header>
        <div class="section-header">
          <span>📋 历史排程计划</span>
        </div>
      </template>

      <div v-if="historyPlans.length === 0" class="empty-state">暂无历史计划，保存后在此查看</div>
      <el-table v-else :data="historyPlans" style="width: 100%">
        <el-table-column prop="plan_name" label="计划名称" min-width="160" />
        <el-table-column label="手里现金" width="130" align="right">
          <template #default="{ row }">{{ fmt(row.cash_on_hand) }}</template>
        </el-table-column>
        <el-table-column label="预留合计" width="130" align="right">
          <template #default="{ row }">{{ fmt(row.total_reserved) }}</template>
        </el-table-column>
        <el-table-column label="剩余可分配" width="140" align="right">
          <template #default="{ row }">
            <span :style="{ color: Number(row.remaining) < 0 ? '#f56c6c' : '#67c23a' }">{{ fmt(row.remaining) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="日期" width="110">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" @click="viewPlan(row)">查看</el-button>
            <el-button size="small" type="danger" @click="deletePlan(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 计划详情弹窗 -->
    <el-dialog v-model="showPlanDialog" :title="viewingPlan?.plan_name || '计划详情'" width="520px" append-to-body>
      <div v-if="viewingPlan && viewingPlan.reserve_items.length" class="plan-item-list">
        <div v-for="(item, i) in viewingPlan.reserve_items" :key="i" class="plan-item">
          <el-tag :type="item.type === 'hard' ? 'danger' : 'warning'" size="small">
            {{ item.type === 'hard' ? '硬性' : '弹性' }}
          </el-tag>
          <span class="plan-item-name">{{ item.name }}</span>
          <span class="plan-item-amount">¥{{ fmt(item.amount) }}</span>
        </div>
      </div>
      <div v-else class="empty-state">该计划无预留项</div>
      <el-divider />
      <div class="plan-summary">
        <span>手里现金：¥{{ fmt(viewingPlan?.cash_on_hand) }}</span>
        <span>预留合计：¥{{ fmt(viewingPlan?.total_reserved) }}</span>
        <span>剩余可分配：¥{{ fmt(viewingPlan?.remaining) }}</span>
      </div>
    </el-dialog>

    <!-- 固定开销记录选择弹窗 -->
    <el-dialog v-model="showExpenseSelectDialog" title="选择固定开销记录" width="650px" append-to-body>
      <el-table
        :data="expenseHistory"
        highlight-current-row
        style="cursor: pointer"
        @row-click="handleExpenseRowClick"
      >
        <el-table-column width="40">
          <template #default="{ row }">
            <el-radio :model-value="selectedExpense?.id" :value="row.id" @click.stop="selectedExpense = row">
              <span />
            </el-radio>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="记录名称" min-width="150" />
        <el-table-column label="月开销" width="110">
          <template #default="{ row }">¥{{ fmt(row.total_monthly) }}</template>
        </el-table-column>
        <el-table-column label="日开销" width="100">
          <template #default="{ row }">¥{{ fmt(row.total_daily) }}</template>
        </el-table-column>
        <el-table-column label="项目数" width="70">
          <template #default="{ row }">{{ (row.items || []).length }}</template>
        </el-table-column>
        <el-table-column label="创建日期" width="110">
          <template #default="{ row }">{{ row.created_at?.slice(0, 10) }}</template>
        </el-table-column>
      </el-table>

      <div v-if="selectedExpense" class="selected-preview">
        <div class="preview-title">已选：{{ selectedExpense.name }}</div>
        <div v-for="(item, i) in selectedPreviewItems.slice(0, 5)" :key="i" class="preview-item">
          <span>{{ item.icon }} {{ item.name }}</span>
          <span>¥{{ fmt(item.amount) }}/{{ item.period === 'daily' ? '天' : item.period === 'yearly' ? '年' : '月' }}</span>
          <span>→ ¥{{ fmt(convertToMonthly(item)) }}/月</span>
        </div>
        <div v-if="selectedPreviewItems.length > 5" class="more-hint">
          ...等共 {{ selectedPreviewItems.length }} 项
        </div>
      </div>

      <template #footer>
        <el-button @click="showExpenseSelectDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedExpense" @click="confirmImportExpense">导入此记录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watchEffect, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatAmount } from '@/shared/utils/format'
import { getFundScheduleList, createFundSchedule, deleteFundSchedule, getFixedExpenseList } from '../api/fundSchedule'
import type { FixedExpenseItem, FixedExpenseRecord, FundScheduleRecord, ReserveItem } from '../types/wealthTypes'

const PERIOD_DAYS: Record<string, number> = { daily: 1, monthly: 30, yearly: 365 }

const saving = ref(false)
const planName = ref('')
const cashOnHand = ref(0)
const reserveItems = ref<ReserveItem[]>([])
const historyPlans = ref<FundScheduleRecord[]>([])
const showPlanDialog = ref(false)
const viewingPlan = ref<FundScheduleRecord | null>(null)
const showExpenseSelectDialog = ref(false)
const expenseHistory = ref<FixedExpenseRecord[]>([])
const selectedExpense = ref<FixedExpenseRecord | null>(null)
const selectedPreviewItems = computed(() => (selectedExpense.value?.items || []).filter((i) => Number(i.amount) > 0))

// 单一派生链：现金 → 预留合计 → 剩余，结构性消除二次扣减类 bug
const totalReserved = computed(() =>
  Math.round(reserveItems.value.reduce((sum, i) => sum + (Number(i.amount) || 0), 0) * 100) / 100,
)
const remainingAmount = computed(() =>
  Math.round(((Number(cashOnHand.value) || 0) - totalReserved.value) * 100) / 100,
)
// 安全网：恒等式 cash = reserved + remaining 被破坏时亮警示
const balanceMismatch = computed(() =>
  Math.abs((Number(cashOnHand.value) || 0) - totalReserved.value - remainingAmount.value) > 0.01,
)
watchEffect(() => {
  console.assert(!balanceMismatch.value, '[FundSchedule] 恒等式 cash = reserved + remaining 被破坏')
})

function fmt(v: number | string | null | undefined): string {
  const n = Number(v) || 0
  return (n < 0 ? '-' : '') + formatAmount(Math.abs(n))
}

function formatDate(dateStr: string) {
  return dateStr ? dateStr.slice(0, 10) : ''
}

function addReserveItem(type: 'hard' | 'soft') {
  reserveItems.value.push({ name: '', amount: 0, type })
}

function removeReserveItem(index: number) {
  reserveItems.value.splice(index, 1)
}

function resetForm() {
  planName.value = ''
  reserveItems.value = []
}

function handleExpenseRowClick(row: FixedExpenseRecord) {
  selectedExpense.value = row
}

async function openExpenseSelect() {
  try {
    const res = await getFixedExpenseList({ page_size: 100 })
    expenseHistory.value = (res.data?.results || []) as FixedExpenseRecord[]
  } catch {
    ElMessage.error('获取固定开销记录失败')
    return
  }
  if (expenseHistory.value.length === 0) {
    ElMessage.warning('固定开销计算器中没有数据')
    return
  }
  selectedExpense.value = null
  showExpenseSelectDialog.value = true
}

/** 将固定开销项目统一换算为月金额（与计算器一致：365 天口径，年周期 ÷12.17） */
function convertToMonthly(item: FixedExpenseItem): number {
  const days = PERIOD_DAYS[item.period] ?? 30
  return Math.round((Number(item.amount) / days) * 30 * 100) / 100
}

async function confirmImportExpense() {
  const expense = selectedExpense.value
  if (!expense) {
    ElMessage.warning('请选择一条固定开销记录')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将「${expense.name}」中的 ${selectedPreviewItems.value.length} 项导入为硬性承诺？`,
      '导入确认',
      { type: 'info' },
    )
  } catch {
    return // 用户取消
  }
  const count = selectedPreviewItems.value.length
  for (const item of selectedPreviewItems.value) {
    reserveItems.value.push({
      name: item.icon ? `${item.icon} ${item.name}` : item.name,
      amount: convertToMonthly(item),
      type: 'hard',
      linked_expense_id: expense.id,
    })
  }
  showExpenseSelectDialog.value = false
  selectedExpense.value = null
  ElMessage.success(`已从「${expense.name}」导入 ${count} 项硬性承诺`)
}

async function savePlan() {
  if (!planName.value.trim()) {
    ElMessage.warning('请输入计划名称')
    return
  }
  if (remainingAmount.value < 0) {
    try {
      await ElMessageBox.confirm('剩余可分配为负，确认保存该计划？', '确认', { type: 'warning' })
    } catch {
      return
    }
  }
  saving.value = true
  try {
    await createFundSchedule({
      plan_name: planName.value.trim(),
      cash_on_hand: Number(cashOnHand.value) || 0,
      reserve_items: reserveItems.value.map((i) => ({
        name: i.name,
        amount: Number(i.amount) || 0,
        type: i.type,
        linked_expense_id: i.linked_expense_id ?? null,
      })),
    })
    ElMessage.success('计划已保存')
    resetForm()
    await loadHistory()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function loadHistory() {
  try {
    const res = await getFundScheduleList({ page_size: 100 })
    historyPlans.value = (res.data?.results || []) as FundScheduleRecord[]
  } catch {
    // 历史列表加载失败不阻塞页面
  }
}

function viewPlan(row: FundScheduleRecord) {
  viewingPlan.value = row
  showPlanDialog.value = true
}

function deletePlan(row: FundScheduleRecord) {
  ElMessageBox.confirm(`确定删除计划「${row.plan_name}」吗？`, '确认删除', { type: 'warning' })
    .then(async () => {
      await deleteFundSchedule(row.id)
      ElMessage.success('已删除')
      await loadHistory()
    })
    .catch(() => {})
}

onMounted(loadHistory)
</script>

<style scoped lang="scss">
.fund-schedule-board {
  padding: 16px 0;
}

.board-card {
  margin-bottom: 16px;
}

.info-form {
  display: flex;
  gap: 40px;
  flex-wrap: wrap;

  .field {
    display: flex;
    align-items: center;
    gap: 12px;

    .field-label {
      font-size: 14px;
      font-weight: 500;
      color: var(--el-text-color-primary);
    }
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-left: 8px;
    font-weight: 400;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }
}

.reserve-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-light);
}

.summary-card {
  .summary-row {
    display: flex;
    gap: 16px;

    .summary-item {
      flex: 1;
      padding: 16px;
      border-radius: 8px;
      background: var(--el-fill-color-light);
      text-align: center;

      .summary-label {
        font-size: 13px;
        color: var(--el-text-color-secondary);
        margin-bottom: 8px;
      }

      .summary-value {
        font-size: 26px;
        font-weight: 700;
      }
    }
  }

  .save-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 16px;

    .hint {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }
}

.empty-state {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 24px 0;
}

.plan-item-list {
  .plan-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;

    .plan-item-name {
      flex: 1;
      font-size: 14px;
    }

    .plan-item-amount {
      font-size: 14px;
      font-weight: 600;
    }
  }
}

.plan-summary {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 500;
}

.selected-preview {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);

  .preview-title {
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 8px;
  }

  .preview-item {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 4px 0;
    font-size: 13px;
  }

  .more-hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-top: 4px;
  }
}
</style>
