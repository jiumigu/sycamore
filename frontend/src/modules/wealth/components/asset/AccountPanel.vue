<template>
  <div class="account-panel">
    <div class="panel-header">
      <div class="panel-header__left">
        <h3>资产科目主数据</h3>
        <span class="panel-header__hint">
          科目在这里增删 —— 加「证券账户」「保险现金价值」不用改表结构
        </span>
      </div>
      <div class="panel-header__right">
        <el-dropdown @command="handleSeed">
          <el-button size="small" :loading="saving">
            初始化科目
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="fill">补齐缺失科目（不动已改的）</el-dropdown-item>
              <el-dropdown-item command="overwrite" divided>
                重置为默认值（会覆盖已改的类别与流动性）
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" size="small" @click="openDialog()">
          <el-icon><Plus /></el-icon>
          新增科目
        </el-button>
      </div>
    </div>

    <!-- 结构汇总 -->
    <div v-if="summary" class="summary-strip">
      <div class="summary-strip__item">
        <span class="label">启用科目</span>
        <span class="value">{{ summary.active_count }}</span>
        <span class="sub">共 {{ summary.total }} 个</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">T+0 可取</span>
        <span class="value">{{ summary.liquid_count }}</span>
        <span class="sub">计入应急金分子</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">计入资产负债表</span>
        <span class="value">{{ summary.counted_count }}</span>
      </div>
      <div class="summary-strip__item">
        <span class="label">不计入</span>
        <span class="value">{{ summary.excluded_count }}</span>
        <span class="sub">仍进明细，只是不参与合计</span>
      </div>
    </div>

    <!-- 类别分布 -->
    <div v-if="summary" class="category-strip">
      <el-tag
        v-for="c in summary.by_category"
        :key="c.category"
        size="small"
        effect="plain"
        class="category-tag"
      >
        {{ c.category }} {{ c.count }}
        <span class="category-tag__sub">（计表 {{ c.counted }} · 可取 {{ c.liquid }}）</span>
      </el-tag>
    </div>

    <el-table :data="accounts" v-loading="loading" stripe size="small" style="width: 100%">
      <el-table-column label="科目名" min-width="130" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.name }}
          <el-tag v-if="!row.is_active" size="small" type="info" class="inline-tag">已停用</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="映射码" width="130" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.code" class="code">{{ row.code }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="类别" width="86" />
      <el-table-column prop="account_kind" label="形态" width="100" />
      <el-table-column label="机构" width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.institution || '—' }}</template>
      </el-table-column>
      <el-table-column label="T+0 可取" width="88" align="center">
        <template #default="{ row }">
          <el-icon v-if="row.is_liquid" class="yes"><CircleCheck /></el-icon>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="计入资产" width="88" align="center">
        <template #default="{ row }">
          <el-icon v-if="row.include_in_balance_sheet" class="yes"><CircleCheck /></el-icon>
          <span v-else class="muted" title="只进明细，不参与任何合计">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="sort" label="排序" width="70" align="right" />
      <el-table-column label="被引用" width="90" align="right">
        <template #default="{ row }">
          <span v-if="row.used_snapshot_count > 0">{{ row.used_snapshot_count }} 期</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button
              v-if="row.used_snapshot_count === 0"
              size="small"
              type="danger"
              @click="handleDelete(row)"
            >删除</el-button>
            <el-button v-else size="small" @click="handleToggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-hint">
          还没有资产科目。点「初始化科目」按旧表的 9 个科目（含借出款）生成一套，
          或点「新增科目」手工添加。
        </div>
      </template>
    </el-table>

    <!-- 新增/编辑 -->
    <el-dialog
      v-model="showDialog"
      :title="form.id ? '编辑科目' : '新增科目'"
      width="620px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="科目名" required>
              <el-input v-model="form.name" placeholder="如 证券账户" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产类别">
              <el-select v-model="form.category" style="width:100%" @change="applyDefaultExclude">
                <el-option v-for="c in ASSET_CATEGORIES" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="账户形态">
              <el-select v-model="form.account_kind" style="width:100%">
                <el-option v-for="k in ASSET_ACCOUNT_KINDS" :key="k" :label="k" :value="k" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="机构">
              <el-input v-model="form.institution" placeholder="如 华泰证券" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="映射码">
          <el-input v-model="form.code" placeholder="旧表列名（zplay / jianbank …）；手工新增可留空" />
          <div class="field-hint">
            记录这个科目对应旧表的哪一列 —— 回填历史快照时靠它对应。手工新增的科目留空即可。
          </div>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="T+0 可取">
              <el-switch v-model="form.is_liquid" />
              <div class="field-hint">决定它算不算应急金</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计入资产负债表">
              <el-switch v-model="form.include_in_balance_sheet" />
              <div class="field-hint">自用资产（房/车）建议关掉</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :step="10" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" :rows="2" placeholder="可选" />
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, ArrowDown, CircleCheck } from '@element-plus/icons-vue'
import { useAssetStore } from '../../stores/assetStore'
import {
  ASSET_CATEGORIES, ASSET_ACCOUNT_KINDS, ASSET_DEFAULT_EXCLUDE_CATEGORIES,
} from '../../types/wealthTypes'
import type { AssetAccountItem, AssetAccountFormData } from '../../types/wealthTypes'

/**
 * 科目主数据面板。
 *
 * 这里**不接脱敏** —— 科目名（支付宝/建行）与机构名都不是隐私项，
 * 而金额根本不在主数据里（金额住在快照明细行）。别顺手加一层掩码。
 */
const store = useAssetStore()

const accounts = computed(() => store.accounts)
const summary = computed(() => store.accountSummary)
const loading = computed(() => store.loading)
const saving = computed(() => store.saving)

const showDialog = ref(false)

function blankForm(): AssetAccountFormData {
  return {
    name: '', code: '', category: '流动性', account_kind: '储蓄卡', institution: '',
    is_liquid: true, include_in_balance_sheet: true, sort: 0, is_active: true, note: '',
  }
}

const form = reactive<AssetAccountFormData>(blankForm())

function openDialog(row?: AssetAccountItem) {
  Object.assign(form, blankForm())
  if (row) {
    Object.assign(form, {
      id: row.id, code: row.code || '', name: row.name, category: row.category,
      account_kind: row.account_kind, institution: row.institution,
      is_liquid: row.is_liquid, include_in_balance_sheet: row.include_in_balance_sheet,
      sort: row.sort, is_active: row.is_active, note: row.note,
    })
  } else if (ASSET_DEFAULT_EXCLUDE_CATEGORIES.includes(form.category!)) {
    form.include_in_balance_sheet = false
  }
  showDialog.value = true
}

/** 类别切换时联动「计入资产」的默认值 —— 仅在新填时给建议，不覆盖用户的显式选择 */
function applyDefaultExclude() {
  if (ASSET_DEFAULT_EXCLUDE_CATEGORIES.includes(form.category!)) {
    form.include_in_balance_sheet = false
  }
}

async function handleSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写科目名')
    return
  }
  try {
    await store.saveAccount({ ...form, code: form.code || null })
    showDialog.value = false
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(apiError(e, '保存失败'))
  }
}

async function handleDelete(row: AssetAccountItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除科目「${row.name}」？`, '删除科目', { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await store.removeAccount(row.id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(apiError(e, '删除失败'))
  }
}

async function handleToggleActive(row: AssetAccountItem) {
  const next = !row.is_active
  try {
    await store.saveAccount({ id: row.id, name: row.name, is_active: next })
    ElMessage.success(next ? '已启用' : '已停用（历史快照不受影响）')
  } catch (e) {
    ElMessage.error(apiError(e, '操作失败'))
  }
}

async function handleSeed(command: string) {
  const overwrite = command === 'overwrite'
  if (overwrite) {
    try {
      await ElMessageBox.confirm(
        '重置会把已有科目的类别、T+0 标记、机构等改回种子默认值。'
        + '你自己改过的设置会丢失。确认继续？',
        '重置为默认值',
        { type: 'warning', confirmButtonText: '确认重置' },
      )
    } catch {
      return
    }
  }
  try {
    const result = await store.seedAccounts(overwrite) as {
      created: number; kept: number; updated: number
    }
    ElMessage.success(
      overwrite
        ? `已重置：${result.updated} 个科目`
        : `补齐完成：新建 ${result.created} 个，保留 ${result.kept} 个`,
    )
  } catch (e) {
    ElMessage.error(apiError(e, '初始化失败'))
  }
}

/** 取后端返回的 detail 文案（如「该科目已被历史快照引用，不能删除…」） */
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

.summary-strip {
  display: flex; flex-wrap: wrap; gap: 24px;
  padding: 12px 16px; margin-bottom: 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.summary-strip__item { display: flex; flex-direction: column; gap: 2px; }
.summary-strip__item .label { font-size: 12px; color: var(--el-text-color-secondary); }
.summary-strip__item .value { font-size: 17px; font-weight: 600; font-variant-numeric: tabular-nums; }
.summary-strip__item .sub { font-size: 11px; color: var(--el-text-color-placeholder); }

.category-strip {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;
}
.category-tag__sub { color: var(--el-text-color-secondary); font-size: 11px; }

.inline-tag { margin-left: 6px; }
.code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px; color: var(--el-text-color-regular);
}
.muted { color: var(--el-text-color-placeholder); }
.yes { color: var(--el-color-success); }

.field-hint { font-size: 11px; color: var(--el-text-color-placeholder); line-height: 1.4; }

.empty-hint { padding: 20px 0; font-size: 13px; color: var(--el-text-color-secondary); }

.action-btns {
  display: flex; gap: 4px; flex-wrap: nowrap; white-space: nowrap;
  :deep(.el-button) { padding: 4px 8px; font-size: 12px; flex-shrink: 0; }
}
</style>
