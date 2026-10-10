<template>
  <div class="liability-panel">
    <div class="panel-header">
      <div class="panel-header__left">
        <h3>负债明细台账</h3>
        <span class="panel-header__hint">逐笔登记后才能算出「先还哪一笔」</span>
      </div>
      <el-button type="primary" size="small" @click="openDialog()">
        <el-icon><Plus /></el-icon>
        新增负债
      </el-button>
    </div>

    <!-- 汇总条 -->
    <div v-if="summary" class="summary-strip">
      <div class="summary-strip__item">
        <span class="label">在还笔数</span>
        <span class="value">{{ summary.active_count }}</span>
        <span class="sub">共 {{ summary.count }} 笔</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">剩余本金</span>
        <span class="value">{{ maskAmount(summary.total_outstanding, privacyMode) }}</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">每月应还</span>
        <span class="value">{{ maskAmount(summary.total_monthly_payment, privacyMode) }}</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">加权平均利率</span>
        <span class="value" :class="{ 'is-warn': summary.weighted_avg_rate >= 10 }">
          {{ maskRate(summary.weighted_avg_rate, privacyMode) }}
        </span>
        <span class="sub">按余额加权</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">年利息成本</span>
        <span class="value">{{ maskAmount(summary.annual_interest_cost, privacyMode) }}</span>
      </div>
    </div>

    <!-- 先还哪一笔 -->
    <div v-if="summary && summary.prepay_focus.by_rate" class="focus-line">
      <el-icon><Aim /></el-icon>
      <span>
        先还哪一笔 —— 雪崩法（省息）：
        <b>{{ maskName(summary.prepay_focus.by_rate, privacyMode) }}</b>
        <template v-if="summary.highest_rate_item">
          （{{ maskRate(summary.highest_rate_item.annual_rate, privacyMode) }}）
        </template>
        · 雪球法（先清一笔）：
        <b>{{ maskName(summary.prepay_focus.by_balance, privacyMode) }}</b>
      </span>
    </div>

    <!-- 与快照对账 -->
    <div v-if="summary && summary.borrow_diff !== null" class="reconcile-line" :class="reconcileClass">
      <el-icon><Link /></el-icon>
      <span>
        与最新盘点快照对账：台账 {{ maskAmount(summary.total_outstanding, privacyMode) }}
        vs 快照 {{ maskAmount(summary.snapshot_borrow, privacyMode) }}，
        {{ reconcileText }}
      </span>
    </div>

    <el-table :data="items" v-loading="loading" stripe size="small" style="width: 100%">
      <el-table-column label="优先级" width="76" align="center">
        <template #default="{ row }">
          <el-tag
            v-if="row.priority_by_rate === 1 && row.status === '在还'"
            type="danger"
            size="small"
          >优先</el-tag>
          <span v-else-if="row.status === '在还'" class="rank">{{ row.priority_by_rate }}</span>
          <span v-else class="rank rank--muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="债务名" min-width="130" show-overflow-tooltip>
        <template #default="{ row }">{{ maskName(row.name, privacyMode) }}</template>
      </el-table-column>
      <el-table-column prop="category" label="类型" width="90" />
      <el-table-column label="剩余本金" width="110" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskAmount(row.outstanding, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="年利率" width="90" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskRate(row.annual_rate, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="每月应还" width="110" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskAmount(row.monthly_payment, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="剩余期数" width="90" align="right">
        <template #default="{ row }">
          {{ row.remaining_months === null ? '—' : `${row.remaining_months} 期` }}
        </template>
      </el-table-column>
      <el-table-column label="到期日" width="100">
        <template #default="{ row }">{{ row.due_date || '—' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80" />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm title="确认删除这条负债记录？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-hint">
          还没有负债记录。逐笔录入后，这里会算出加权平均利率与先还哪一笔。
        </div>
      </template>
    </el-table>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="showDialog"
      :title="form.id ? '编辑负债' : '新增负债'"
      width="620px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="96px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="债务名" required>
              <el-input v-model="form.name" placeholder="如 招行信用卡" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负债类型">
              <el-select v-model="form.category" style="width:100%">
                <el-option v-for="c in LIABILITY_CATEGORIES" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="借款本金">
              <el-input-number v-model="form.principal" :precision="2" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="剩余本金">
              <el-input-number v-model="form.outstanding" :precision="2" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="年利率">
              <el-input-number v-model="form.annual_rate" :precision="2" :min="0" :max="100" :step="0.5" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="每月应还">
              <el-input-number v-model="form.monthly_payment" :precision="2" :min="0" :step="500" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="起借日">
              <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="到期日">
              <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="还款方式">
              <el-select v-model="form.repayment_method" style="width:100%">
                <el-option v-for="m in REPAYMENT_METHODS" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width:100%">
                <el-option v-for="s in LIABILITY_STATUSES" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ form.id ? '更新' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Aim, Link } from '@element-plus/icons-vue'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { maskAmount, maskName, maskRate } from '@/shared/utils/privacy'
import { useDebtStore } from '../../stores/debtStore'
import {
  LIABILITY_CATEGORIES, REPAYMENT_METHODS, LIABILITY_STATUSES,
} from '../../types/wealthTypes'
import type { LiabilityItem, LiabilityFormData } from '../../types/wealthTypes'

const store = useDebtStore()
const privacyStore = usePrivacyStore()
const privacyMode = computed(() => privacyStore.privacyMode)

const items = computed(() => store.liabilityList)
const summary = computed(() => store.liabilitySummary)
const loading = computed(() => store.loading)
const saving = computed(() => store.saving)

const showDialog = ref(false)

function blankForm(): LiabilityFormData {
  return {
    name: '', category: '信用卡', principal: 0, outstanding: 0, annual_rate: 0,
    start_date: '', due_date: '', repayment_method: '等额本息',
    monthly_payment: 0, status: '在还', remark: '',
  }
}

const form = reactive<LiabilityFormData>(blankForm())

function openDialog(row?: LiabilityItem) {
  Object.assign(form, blankForm())
  if (row) {
    Object.assign(form, {
      id: row.id, name: row.name, category: row.category,
      principal: row.principal, outstanding: row.outstanding,
      annual_rate: row.annual_rate, start_date: row.start_date || '',
      due_date: row.due_date || '', repayment_method: row.repayment_method,
      monthly_payment: row.monthly_payment, status: row.status, remark: row.remark,
    })
  }
  showDialog.value = true
}

async function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写债务名')
    return
  }
  try {
    await store.saveLiability({
      ...form,
      start_date: form.start_date || null,
      due_date: form.due_date || null,
    })
    showDialog.value = false
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败，请检查日期与金额是否合法')
  }
}

async function handleDelete(row: LiabilityItem) {
  try {
    await store.removeLiability(row.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

/** 差额 0 视为「已对平」；非 0 提示哪一边需要更新，不自动改数据 */
const reconcileClass = computed(() => {
  const d = summary.value?.borrow_diff
  if (d === null || d === undefined || d === 0) return 'reconcile-line--ok'
  return 'reconcile-line--diff'
})

const reconcileText = computed(() => {
  const d = summary.value?.borrow_diff ?? 0
  if (d === 0) return '已对平'
  const abs = Math.abs(d)
  return d > 0
    ? `台账比快照多 ${maskAmount(abs, privacyMode.value)}，快照待更新`
    : `台账比快照少 ${maskAmount(abs, privacyMode.value)}，可能有未登记的负债`
})
</script>

<style scoped>
.panel-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
}
.panel-header__left { display: flex; align-items: baseline; gap: 8px; }
.panel-header__left h3 { margin: 0; font-size: 16px; font-weight: 600; }
.panel-header__hint { font-size: 12px; color: var(--el-text-color-secondary); }

.summary-strip {
  display: flex; flex-wrap: wrap; gap: 24px;
  padding: 12px 16px; margin-bottom: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.summary-strip__item { display: flex; flex-direction: column; gap: 2px; }
.summary-strip__item .label { font-size: 12px; color: var(--el-text-color-secondary); }
.summary-strip__item .value { font-size: 17px; font-weight: 600; font-variant-numeric: tabular-nums; }
.summary-strip__item .value.is-warn { color: var(--el-color-danger); }
.summary-strip__item .sub { font-size: 11px; color: var(--el-text-color-placeholder); }

.focus-line, .reconcile-line {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; margin-bottom: 8px;
}
.focus-line { color: var(--el-text-color-regular); }
.reconcile-line--ok { color: var(--el-color-success); }
.reconcile-line--diff { color: var(--el-color-warning); }

.rank { font-variant-numeric: tabular-nums; color: var(--el-text-color-regular); }
.rank--muted { color: var(--el-text-color-placeholder); }

.empty-hint {
  padding: 20px 0; font-size: 13px; color: var(--el-text-color-secondary);
}

.action-btns {
  display: flex; gap: 4px; flex-wrap: nowrap; white-space: nowrap;
  :deep(.el-button) { padding: 4px 8px; font-size: 12px; flex-shrink: 0; }
}
.col-amount { white-space: nowrap; }
</style>
