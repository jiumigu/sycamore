<template>
  <div class="receivable-panel">
    <div class="panel-header">
      <div class="panel-header__left">
        <h3>应收借出台账</h3>
        <span class="panel-header__hint">账龄越久越靠前，未填借出日的排在最后</span>
      </div>
      <el-button type="primary" size="small" @click="openDialog()">
        <el-icon><Plus /></el-icon>
        新增借出
      </el-button>
    </div>

    <!-- 汇总条 -->
    <div v-if="summary" class="summary-strip">
      <div class="summary-strip__item">
        <span class="label">未收回</span>
        <span class="value">{{ maskAmount(summary.total_outstanding, privacyMode) }}</span>
        <span class="sub">{{ summary.active_count }} 笔在借</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">已收回</span>
        <span class="value">{{ maskAmount(summary.total_received, privacyMode) }}</span>
        <span class="sub">回收率 {{ maskRate(summary.recovery_ratio, privacyMode) }}</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">逾期</span>
        <span class="value" :class="{ 'is-warn': summary.overdue_count > 0 }">
          {{ summary.overdue_count }} 笔
        </span>
        <span class="sub">
          {{ summary.overdue_count > 0
            ? `${maskAmount(summary.overdue_amount, privacyMode)} · 最长 ${summary.max_overdue_days} 天`
            : '无逾期' }}
        </span>
      </div>
      <div class="summary-strip__item">
        <span class="label">长期挂账</span>
        <span class="value" :class="{ 'is-warn': summary.long_aging_count > 0 }">
          {{ summary.long_aging_count }} 笔
        </span>
        <span class="sub">账龄 ≥ 365 天</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">无息借出</span>
        <span class="value">{{ maskAmount(summary.interest_free_amount, privacyMode) }}</span>
        <span class="sub">占在借 {{ maskRate(summary.interest_free_ratio, privacyMode) }}</span>
      </div>
      <div v-if="summary.bad_debt_count > 0" class="summary-strip__item">
        <span class="label">呆账</span>
        <span class="value is-warn">{{ maskAmount(summary.bad_debt_amount, privacyMode) }}</span>
        <span class="sub">{{ summary.bad_debt_count }} 笔</span>
      </div>
    </div>

    <!-- 账龄分布：纯 CSS 条形，不走 ECharts
         （ECharts 需要 resize 重算 option、且 valueFormatter 不随隐私开关刷新） -->
    <div v-if="visibleBuckets.length" class="aging-block">
      <div class="aging-block__title">账龄分布（按未收回金额）</div>
      <div v-for="b in visibleBuckets" :key="b.bucket" class="aging-row">
        <span class="aging-row__label">{{ b.bucket }}</span>
        <div class="aging-row__track">
          <div
            class="aging-row__bar"
            :style="{ width: Math.max(b.share, 1.5) + '%', background: bucketColor(b.bucket) }"
          />
        </div>
        <span class="aging-row__amount">{{ maskAmount(b.amount, privacyMode) }}</span>
        <span class="aging-row__meta">{{ b.count }} 笔 · {{ maskRate(b.share, privacyMode) }}</span>
      </div>
    </div>

    <!-- 与快照对账 -->
    <div v-if="summary && summary.lend_diff !== null" class="reconcile-line" :class="reconcileClass">
      <el-icon><Link /></el-icon>
      <span>
        与最新盘点快照对账：台账 {{ maskAmount(summary.total_outstanding, privacyMode) }}
        vs 快照 {{ maskAmount(summary.snapshot_lend, privacyMode) }}，
        {{ reconcileText }}
      </span>
    </div>

    <el-table :data="items" v-loading="loading" stripe size="small" style="width: 100%">
      <el-table-column label="对方" width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ maskName(row.counterparty, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="借出本金" width="110" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskAmount(row.principal, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="已收回" width="110" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskAmount(row.received, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="未收回" width="110" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskAmount(row.outstanding, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="借出日" width="100">
        <template #default="{ row }">{{ row.lend_date || '未填' }}</template>
      </el-table-column>
      <el-table-column label="账龄" width="130">
        <template #default="{ row }">
          <el-tag
            size="small"
            :style="{ color: bucketColor(row.aging_bucket), borderColor: bucketColor(row.aging_bucket) }"
            effect="plain"
          >
            {{ row.aging_days === null ? row.aging_bucket : `${row.aging_days} 天 · ${row.aging_bucket}` }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="约定还款日" width="110">
        <template #default="{ row }">{{ row.due_date || '—' }}</template>
      </el-table-column>
      <el-table-column label="逾期" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.is_overdue" type="danger" size="small">
            {{ row.overdue_days }} 天
          </el-tag>
          <span v-else class="rank--muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="年利率" width="90" align="right" class-name="col-amount">
        <template #default="{ row }">
          {{ row.annual_rate > 0 ? maskRate(row.annual_rate, privacyMode) : '无息' }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80" />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm title="确认删除这条借出记录？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-hint">
          还没有应收借出记录。录入后这里会给出账龄分布与逾期提醒。
        </div>
      </template>
    </el-table>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="showDialog"
      :title="form.id ? '编辑应收借出' : '新增应收借出'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="104px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="对方" required>
              <el-input v-model="form.counterparty" placeholder="人名或称呼" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width:100%">
                <el-option v-for="s in RECEIVABLE_STATUSES" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="借出本金">
              <el-input-number v-model="form.principal" :precision="2" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="已收回">
              <el-input-number v-model="form.received" :precision="2" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="借出日">
              <el-date-picker v-model="form.lend_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="约定还款日">
              <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="年利率">
          <el-input-number v-model="form.annual_rate" :precision="2" :min="0" :max="100" :step="0.5" style="width:100%" />
          <div class="form-hint">0 表示无息借出；填日期才会计账龄与逾期</div>
        </el-form-item>

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
import { Plus, Link } from '@element-plus/icons-vue'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { maskAmount, maskName, maskRate } from '@/shared/utils/privacy'
import { useDebtStore } from '../../stores/debtStore'
import { RECEIVABLE_STATUSES, AGING_UNKNOWN_BUCKET } from '../../types/wealthTypes'
import type { ReceivableItem, ReceivableFormData } from '../../types/wealthTypes'

const store = useDebtStore()
const privacyStore = usePrivacyStore()
const privacyMode = computed(() => privacyStore.privacyMode)

const items = computed(() => store.receivableList)
const summary = computed(() => store.receivableSummary)
const loading = computed(() => store.loading)
const saving = computed(() => store.saving)

/** 零笔数的桶不渲染 —— 6 行里通常只有 2~3 行有数 */
const visibleBuckets = computed(
  () => (summary.value?.aging ?? []).filter((b) => b.count > 0),
)

/** 账龄风险色阶（越久越红）；「未填借出日」用中性灰，表示数据缺口而非风险 */
const BUCKET_COLORS: Record<string, string> = {
  '30天内': '#10B981',
  '31-90天': '#3B82F6',
  '91-180天': '#F59E0B',
  '181-365天': '#F97316',
  '365天以上': '#EF4444',
  [AGING_UNKNOWN_BUCKET]: '#9CA3AF',
}

function bucketColor(bucket: string): string {
  return BUCKET_COLORS[bucket] || '#9CA3AF'
}

const showDialog = ref(false)

function blankForm(): ReceivableFormData {
  return {
    counterparty: '', principal: 0, received: 0,
    lend_date: '', due_date: '', annual_rate: 0, status: '在借', remark: '',
  }
}

const form = reactive<ReceivableFormData>(blankForm())

function openDialog(row?: ReceivableItem) {
  Object.assign(form, blankForm())
  if (row) {
    Object.assign(form, {
      id: row.id, counterparty: row.counterparty,
      principal: row.principal, received: row.received,
      lend_date: row.lend_date || '', due_date: row.due_date || '',
      annual_rate: row.annual_rate, status: row.status, remark: row.remark,
    })
  }
  showDialog.value = true
}

async function handleSave() {
  if (!form.counterparty.trim()) {
    ElMessage.warning('请填写对方')
    return
  }
  try {
    await store.saveReceivable({
      ...form,
      lend_date: form.lend_date || null,
      due_date: form.due_date || null,
    })
    showDialog.value = false
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败，请检查日期与金额是否合法')
  }
}

async function handleDelete(row: ReceivableItem) {
  try {
    await store.removeReceivable(row.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

const reconcileClass = computed(() => {
  const d = summary.value?.lend_diff
  if (d === null || d === undefined || d === 0) return 'reconcile-line--ok'
  return 'reconcile-line--diff'
})

const reconcileText = computed(() => {
  const d = summary.value?.lend_diff ?? 0
  if (d === 0) return '已对平'
  const abs = Math.abs(d)
  return d > 0
    ? `台账比快照多 ${maskAmount(abs, privacyMode.value)}，快照待更新`
    : `台账比快照少 ${maskAmount(abs, privacyMode.value)}，可能有未登记的借出`
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

.aging-block { margin-bottom: 12px; }
.aging-block__title {
  font-size: 13px; font-weight: 600; color: var(--el-text-color-regular); margin-bottom: 8px;
}
.aging-row {
  display: flex; align-items: center; gap: 10px;
  font-size: 12px; margin-bottom: 6px;
}
.aging-row__label { width: 84px; color: var(--el-text-color-secondary); flex-shrink: 0; }
.aging-row__track {
  flex: 1; height: 10px; border-radius: 5px;
  background: var(--el-fill-color-light); overflow: hidden; min-width: 60px;
}
.aging-row__bar { height: 100%; border-radius: 5px; transition: width 0.3s; }
.aging-row__amount {
  width: 110px; text-align: right; font-variant-numeric: tabular-nums; flex-shrink: 0;
}
.aging-row__meta {
  width: 130px; text-align: right; color: var(--el-text-color-placeholder); flex-shrink: 0;
}

.reconcile-line {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; margin-bottom: 12px;
}
.reconcile-line--ok { color: var(--el-color-success); }
.reconcile-line--diff { color: var(--el-color-warning); }

.rank--muted { color: var(--el-text-color-placeholder); }
.form-hint { font-size: 11px; color: var(--el-text-color-placeholder); line-height: 1.6; }
.empty-hint { padding: 20px 0; font-size: 13px; color: var(--el-text-color-secondary); }

.action-btns {
  display: flex; gap: 4px; flex-wrap: nowrap; white-space: nowrap;
  :deep(.el-button) { padding: 4px 8px; font-size: 12px; flex-shrink: 0; }
}
.col-amount { white-space: nowrap; }
</style>
