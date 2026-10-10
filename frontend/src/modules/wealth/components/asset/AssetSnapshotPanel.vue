<template>
  <div class="asset-snapshot-panel">
    <div class="panel-header">
      <div class="panel-header__left">
        <h3>资产快照（按科目）</h3>
        <span class="panel-header__hint">
          每月一期、明细按科目录入 —— 科目可增删，加「证券账户」不用改表结构
        </span>
      </div>
      <div class="panel-header__right">
        <el-select
          v-model="limit"
          size="small"
          style="width:118px"
          @change="handleLimitChange"
        >
          <el-option :value="12" label="最近 12 期" />
          <el-option :value="24" label="最近 24 期" />
          <el-option :value="60" label="最近 60 期" />
        </el-select>
        <el-button type="primary" size="small" @click="openDialog()">
          <el-icon><Plus /></el-icon>
          新增盘点
        </el-button>
      </div>
    </div>

    <el-table :data="snapshots" v-loading="loading" stripe size="small" style="width: 100%">
      <el-table-column prop="yearmon" label="年月" width="92" />
      <el-table-column label="盘点日" width="104">
        <template #default="{ row }">{{ row.snapshot_date || '—' }}</template>
      </el-table-column>
      <el-table-column label="T+0 可取" width="106" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskAmount(row.liquid_total, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="金融资产" width="106" align="right" class-name="col-amount">
        <template #default="{ row }">
          {{ maskAmount(row.financial_assets, privacyMode) }}
          <el-tooltip v-if="row.self_use_total > 0" placement="top">
            <template #content>
              含自用资产 {{ maskAmount(row.self_use_total, privacyMode) }}，
              已计入总资产但不计入「可变现」
            </template>
            <el-icon class="info-icon"><WarningFilled /></el-icon>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="总资产" width="106" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskAmount(row.total_assets, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="负债" width="98" align="right" class-name="col-amount">
        <template #default="{ row }">{{ maskAmount(row.borrow, privacyMode) }}</template>
      </el-table-column>
      <el-table-column label="净资产" width="106" align="right" class-name="col-amount">
        <template #default="{ row }">
          <span :class="{ 'is-negative': row.net_worth < 0 }">
            {{ maskAmount(row.net_worth, privacyMode) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="可变现净值" width="112" align="right" class-name="col-amount">
        <template #default="{ row }">
          <el-tooltip placement="top">
            <template #content>剔除自用资产后的净资产 —— 能真正变成钱的部分</template>
            <span :class="{ 'is-negative': row.available_net_worth < 0 }">
              {{ maskAmount(row.available_net_worth, privacyMode) }}
            </span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="科目数" width="76" align="right">
        <template #default="{ row }">{{ row.item_count }}</template>
      </el-table-column>
      <el-table-column label="备注" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ maskFreeText(row.remarks, privacyMode) || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-popconfirm title="确认删除这一期快照？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-hint">
          还没有按科目的快照。先点右上角「口径配置」→「资产科目」→「初始化科目」，
          再点「新增盘点」按科目录入当月余额。
        </div>
      </template>
    </el-table>

    <!-- 应收回款差额提示 -->
    <div v-if="gapRows.length" class="gap-line">
      <el-icon><WarningFilled /></el-icon>
      <span>
        以下期次的应收类科目合计与快照头借出数不一致（只提示，不自动改数据）：
        <b v-for="r in gapRows" :key="r.id" class="gap-item">
          {{ r.yearmon }} 差 {{ maskAmount(Math.abs(r.receivable_gap), privacyMode) }}
        </b>
      </span>
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="showDialog"
      :title="editingId ? '编辑资产快照' : '新增资产快照'"
      width="760px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="88px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="年月" required>
              <el-date-picker
                v-model="form.yearmon"
                type="month"
                value-format="YYYY-MM"
                style="width:100%"
                :disabled="!!editingId"
              />
              <div v-if="editingId" class="field-hint">
                年月是这一期的身份，不可修改；要换期请删除后重建
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="盘点日期">
              <el-date-picker
                v-model="form.snapshot_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width:100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="负债合计">
              <el-input-number v-model="form.borrow" :precision="2" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="借出合计">
              <el-input-number v-model="form.lend" :precision="2" :min="0" :step="1000" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <el-input v-model="form.remarks" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>

        <el-divider content-position="left">
          各科目余额
          <el-button v-if="!editingId" link size="small" @click="prefillFromLatest">
            带入最近一期
          </el-button>
        </el-divider>

        <div v-if="!activeAccounts.length" class="empty-hint">
          还没有启用的科目 —— 请点右上角「口径配置」→「资产科目」新增或初始化科目。
        </div>

        <div v-for="group in groupedAccounts" :key="group.category" class="entry-group">
          <div class="entry-group__title">{{ group.category }}</div>
          <el-row :gutter="12">
            <el-col
              v-for="acct in group.accounts"
              :key="acct.id"
              :xs="24" :sm="12" :md="8"
            >
              <el-form-item class="entry-item">
                <template #label>
                  <span class="entry-item__label">
                    {{ acct.name }}
                    <el-tooltip v-if="!acct.include_in_balance_sheet" placement="top">
                      <template #content>
                        不计入资产负债表：只进明细，不参与总资产与净资产
                      </template>
                      <el-icon class="info-icon"><WarningFilled /></el-icon>
                    </el-tooltip>
                  </span>
                </template>
                <el-input-number
                  v-model="entries[acct.id]"
                  :precision="2"
                  :min="0"
                  :step="1000"
                  controls-position="right"
                  style="width:100%"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <!-- 实时预览（输入态派生值，按口径刻意**不脱敏**） -->
        <div class="preview-strip">
          <span class="preview-strip__item">
            T+0 可取 <b>{{ plainAmount(preview.liquid_total) }}</b>
          </span>
          <span class="preview-strip__item">
            金融资产 <b>{{ plainAmount(preview.financial_assets) }}</b>
          </span>
          <span class="preview-strip__item">
            总资产 <b>{{ plainAmount(preview.total_assets) }}</b>
          </span>
          <span class="preview-strip__item">
            净资产 <b>{{ plainAmount(preview.net_worth) }}</b>
          </span>
          <span class="preview-strip__item">
            可变现 <b>{{ plainAmount(preview.available_net_worth) }}</b>
          </span>
          <span v-if="preview.excluded_total > 0" class="preview-strip__item is-muted">
            另有不计入资产 <b>{{ plainAmount(preview.excluded_total) }}</b>
          </span>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ editingId ? '更新' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, WarningFilled } from '@element-plus/icons-vue'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { maskAmount, maskFreeText } from '@/shared/utils/privacy'
import { formatAmount } from '@/shared/utils/format'
import { useAssetStore } from '../../stores/assetStore'
import { ASSET_CATEGORIES } from '../../types/wealthTypes'
import type {
  AssetAccountItem, AssetSnapshotRow, AssetSnapshotFormData,
} from '../../types/wealthTypes'

/**
 * 资产快照面板（P1-B）。
 *
 * 脱敏边界（与 v3.58.18 定的判据一致）：
 *   · 已落库数据的呈现（列表行、应收差额提示）→ 一律掩码；
 *   · 正在输入或由输入实时派生的值（弹窗里的实时预览）→ **刻意不掩** ——
 *     边录边掩等于让人闭着眼记账。
 * 汇总恒等式一律由后端算，这里不做任何除法，只做展示时的加总预览。
 */
const store = useAssetStore()
const privacyStore = usePrivacyStore()
const privacyMode = computed(() => privacyStore.privacyMode)

const snapshots = computed(() => store.snapshots)
const loading = computed(() => store.loading)
const saving = computed(() => store.saving)
const accounts = computed(() => store.accounts)

const limit = ref(store.snapshotLimit)
const showDialog = ref(false)
const editingId = ref<number | null>(null)

const form = reactive({
  yearmon: '',
  snapshot_date: '' as string,
  borrow: 0,
  lend: 0,
  remarks: '',
})

/** account_id → 金额（输入态，不脱敏） */
const entries = reactive<Record<number, number>>({})

const activeAccounts = computed(() => accounts.value.filter(a => a.is_active))

const groupedAccounts = computed(() =>
  ASSET_CATEGORIES
    .map(category => ({
      category,
      accounts: activeAccounts.value.filter(a => a.category === category),
    }))
    .filter(g => g.accounts.length > 0),
)

/** 应收类科目合计 − 快照头借出：非 0 的期次（只提示，不改数据） */
const gapRows = computed(() =>
  snapshots.value.filter(r => Math.abs(r.receivable_gap) > 0.01),
)

// ─── 输入态实时预览（口径与后端 rollup_items 一致，仅用于填数字时的心算校验）───
const preview = computed(() => {
  const catTotals: Record<string, number> = {}
  ASSET_CATEGORIES.forEach(c => { catTotals[c] = 0 })
  let liquid = 0
  let excluded = 0
  for (const acct of activeAccounts.value) {
    const amt = Number(entries[acct.id] ?? 0)
    if (!acct.include_in_balance_sheet) {
      excluded += amt
      continue
    }
    catTotals[acct.category] = (catTotals[acct.category] ?? 0) + amt
    if (acct.is_liquid) liquid += amt
  }
  const financial = ASSET_CATEGORIES
    .filter(c => c !== '自用')
    .reduce((sum, c) => sum + (catTotals[c] ?? 0), 0)
  const selfUse = catTotals['自用'] ?? 0
  const total = financial + selfUse
  const borrow = Number(form.borrow || 0)
  return {
    liquid_total: liquid,
    financial_assets: financial,
    total_assets: total,
    net_worth: total - borrow,
    available_net_worth: financial - borrow,
    excluded_total: excluded,
  }
})

function plainAmount(v: number): string {
  return `¥${formatAmount(v, 0)}`
}

function resetEntries() {
  Object.keys(entries).forEach(k => delete entries[Number(k)])
  activeAccounts.value.forEach(a => { entries[a.id] = 0 })
}

function openDialog(row?: AssetSnapshotRow) {
  editingId.value = row?.id ?? null
  form.yearmon = row?.yearmon ?? currentYearmon()
  form.snapshot_date = row?.snapshot_date ?? ''
  form.borrow = row?.borrow ?? 0
  form.lend = row?.lend ?? 0
  form.remarks = row?.remarks ?? ''
  resetEntries()

  if (row) {
    // 明细要单独取（列表刻意不带 items）
    store.loadSnapshot(row.id).then(detail => {
      if (!detail?.items) return
      detail.items.forEach(i => { entries[i.account_id] = i.amount })
    })
  }
  showDialog.value = true
}

function currentYearmon(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

/** 带入最近一期的金额 —— 每月盘点多为增量修改，从上一期起手比从零起手快 */
async function prefillFromLatest() {
  const latest = snapshots.value[0]
  if (!latest) {
    ElMessage.info('还没有可带入的历史期')
    return
  }
  const detail = await store.loadSnapshot(latest.id)
  if (!detail?.items) {
    ElMessage.warning('最近一期没有明细')
    return
  }
  detail.items.forEach(i => { entries[i.account_id] = i.amount })
  form.borrow = detail.borrow
  form.lend = detail.lend
  ElMessage.success(`已带入 ${detail.yearmon} 的余额`)
}

async function handleSave() {
  if (!/^\d{4}-\d{2}$/.test(form.yearmon)) {
    ElMessage.warning('请选择年月')
    return
  }
  const payload: AssetSnapshotFormData = {
    yearmon: form.yearmon,
    snapshot_date: form.snapshot_date || null,
    borrow: form.borrow,
    lend: form.lend,
    remarks: form.remarks,
    items: activeAccounts.value.map(a => ({
      account_id: a.id,
      amount: Number(entries[a.id] ?? 0),
    })),
  }
  try {
    await store.saveSnapshot(payload, editingId.value)
    showDialog.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(apiError(e, '保存失败，请检查年月与金额'))
  }
}

async function handleDelete(row: AssetSnapshotRow) {
  try {
    await store.removeSnapshot(row.id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(apiError(e, '删除失败'))
  }
}

function handleLimitChange(val: number) {
  store.snapshotLimit = val
  store.fetchSnapshots()
}

/** 供页面「刷新」按钮调用 —— 面板自持列表，父组件不该直接摸 store */
function refresh() {
  store.fetchSnapshots()
}

/**
 * `openDialog` 对外开放：页头的「新增盘点」按钮调它。
 * 入口只有一个，但可以有两个按钮指向同一条链。
 */
defineExpose({ openDialog, refresh })

/** 取后端返回的 detail 文案 */
function apiError(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
</script>

<style scoped>
.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px; margin-bottom: 12px; flex-wrap: wrap;
}
.panel-header__left { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.panel-header__left h3 { margin: 0; font-size: 16px; font-weight: 600; }
.panel-header__hint { font-size: 12px; color: var(--el-text-color-secondary); }
.panel-header__right { display: flex; align-items: center; gap: 8px; }

.gap-line {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; margin-bottom: 10px; flex-wrap: wrap;
  color: var(--el-color-warning);
}
.gap-item { margin-right: 12px; font-variant-numeric: tabular-nums; }

.entry-group { margin-bottom: 4px; }
.entry-group__title {
  font-size: 12px; font-weight: 600; color: var(--el-text-color-secondary);
  margin: 8px 0 6px; padding-left: 2px;
  border-left: 3px solid var(--el-color-primary);
  padding-left: 8px;
}
.entry-item { margin-bottom: 12px; }
.entry-item__label { font-size: 13px; }

.info-icon { color: var(--el-color-warning); margin-left: 2px; }

.preview-strip {
  display: flex; flex-wrap: wrap; gap: 18px;
  padding: 10px 14px; margin-top: 4px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  font-size: 13px; color: var(--el-text-color-secondary);
}
.preview-strip__item b {
  color: var(--el-text-color-primary); font-variant-numeric: tabular-nums;
}
.preview-strip__item.is-muted b { color: var(--el-text-color-secondary); }

.field-hint { font-size: 11px; color: var(--el-text-color-placeholder); line-height: 1.4; }
.muted { color: var(--el-text-color-placeholder); }
.is-negative { color: var(--el-color-danger); }
.empty-hint { padding: 16px 0; font-size: 13px; color: var(--el-text-color-secondary); }

.action-btns {
  display: flex; gap: 4px; flex-wrap: nowrap; white-space: nowrap;
  :deep(.el-button) { padding: 4px 8px; font-size: 12px; flex-shrink: 0; }
}
.col-amount { white-space: nowrap; }
</style>
