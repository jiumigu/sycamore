<template>
  <div class="mapping-editor">
    <div class="page-header">
      <el-button size="small" @click="$router.push('/temporal')">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <h2>🧩 分类映射编辑器</h2>
      <el-tag type="info" size="small">L1 归因 / L2 类型 / L3 task_name</el-tag>
      <div class="header-right">
        <el-button size="small" text type="primary" :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>
    <p class="page-desc">
      全量 task_name 台账：按时长审阅分类质量，可就地改 L1 归因 / L2 类型（作用于该任务名下的全部记录，不逐条改）。
    </p>

    <!-- 概要：全量口径，不随筛选变化 -->
    <el-card class="panel-card summary-card" shadow="never">
      <div class="summary-strip">
        <div class="sum-item">
          <div class="sum-label">任务名</div>
          <div class="sum-value">{{ summary.total }}<small>个</small></div>
        </div>
        <div class="sum-item">
          <div class="sum-label">已归类</div>
          <div class="sum-value">{{ summary.classified }}<small>个</small></div>
        </div>
        <div class="sum-item" :class="{ 'is-ok': !summary.unclassified }">
          <div class="sum-label">未归类</div>
          <div class="sum-value">{{ summary.unclassified }}<small>个</small></div>
          <div class="sum-note">{{ summary.unclassified ? '待指定 L2 类型' : '已全部归类 🎉' }}</div>
        </div>
        <div class="sum-item">
          <div class="sum-label">台账总时长</div>
          <div class="sum-value">{{ summary.total_hours.toFixed(1) }}<small>h</small></div>
          <div class="sum-note" :class="{ muted: !summary.unclassified_hours }">
            含未归类 {{ summary.unclassified_hours.toFixed(1) }}h
          </div>
        </div>
      </div>

      <div class="attr-chips">
        <span class="chips-label">L1 归因小计</span>
        <span
          v-for="a in ATTRIBUTION_OPTIONS"
          :key="a"
          class="chip"
          :class="{ active: filter.attribution === a, dim: !!filter.attribution && filter.attribution !== a }"
          @click="toggleAttrFilter(a)"
        >
          <i class="dot" :style="{ background: attrColor(a) }" />
          <span class="chip-name">{{ a }}</span>
          <b class="chip-hours">{{ (summary.by_attribution[a] || 0).toFixed(1) }}h</b>
          <em class="chip-pct">{{ attrPct(a) }}%</em>
        </span>
        <span
          v-if="summary.unclassified"
          class="chip chip--unclassified"
          :class="{ active: filter.unclassifiedOnly }"
          @click="toggleUnclassifiedFilter"
        >
          <i class="dot" style="background: #CBD5E1" />
          <span class="chip-name">未归类</span>
          <b class="chip-hours">{{ summary.unclassified_hours.toFixed(1) }}h</b>
          <em class="chip-pct">{{ attrPct('__unclassified__') }}%</em>
        </span>
      </div>
    </el-card>

    <el-alert
      v-if="summary.unclassified"
      type="warning" :closable="false" show-icon class="hint-alert"
      title="未归类任务不参与记录完整度计算"
    >
      请为其指定 <b>L2 活动类型</b>；若带价值归因，可一并指定 <b>L1 归因</b>（会自动写入赎回期归因规则）。
    </el-alert>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="filter.search" placeholder="搜索任务名" clearable size="small" style="width:180px"
        @keyup.enter="load" @clear="load"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-model="filter.activityType" placeholder="L2 活动类型" clearable size="small" style="width:150px" @change="load">
        <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
      </el-select>
      <el-select v-model="filter.attribution" placeholder="L1 归因" clearable size="small" style="width:120px" @change="load">
        <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
      </el-select>
      <el-checkbox v-model="filter.unclassifiedOnly" size="small" @change="load">仅未归类</el-checkbox>
      <el-button size="small" @click="load">查询</el-button>
      <el-button size="small" @click="resetFilter">重置</el-button>
      <span class="filter-count">共 {{ items.length }} / {{ summary.total }} 个任务名</span>
    </div>

    <!-- 批量操作条 -->
    <div class="bulk-bar" v-if="selectedNames.length">
      <span>已选 {{ selectedNames.length }} 个任务名</span>
      <el-button size="small" type="primary" @click="openBulk">批量改 L2 类型 / L1 归因</el-button>
      <el-button size="small" @click="clearSelection">取消选择</el-button>
      <span class="bulk-hint">按 task_name 生效：该任务名下的全部记录一次性归类</span>
    </div>

    <el-card class="panel-card table-card" shadow="never">
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="items"
        stripe size="small" max-height="560" row-key="task_name"
        :default-sort="defaultSort"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="40" reserve-selection />
        <el-table-column label="任务名（L3）" prop="task_name" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'is-unclassified': row.is_unclassified }">{{ row.task_name }}</span>
          </template>
        </el-table-column>

        <el-table-column label="L1 归因" width="150">
          <template #default="{ row }">
            <el-select
              :key="`attr-${row.task_name}-${rev}`"
              :model-value="row.effective_attribution"
              size="small" style="width:100%"
              :disabled="savingRow === row.task_name"
              @click.stop @change="onAttrChange(row, $event)"
            >
              <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
              <el-option
                v-if="row.attribution_source === 'rule'"
                :label="'撤销覆盖（回默认）'" :value="ATTR_CLEAR"
              />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="L2 类型" width="150">
          <template #default="{ row }">
            <el-select
              :model-value="row.activity_type"
              size="small" style="width:100%"
              :disabled="savingRow === row.task_name"
              @click.stop @change="onTypeChange(row, $event)"
            >
              <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
            </el-select>
          </template>
        </el-table-column>

        <el-table-column label="累计时长" prop="total_hours" width="130" sortable>
          <template #default="{ row }">
            <div class="hours-cell">
              <span class="hours-num">{{ row.total_hours.toFixed(1) }}h</span>
              <span class="hours-bar"><i :style="barStyle(row)" /></span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="记录次数" prop="record_count" width="94" sortable align="right" />
        <el-table-column label="单次均时" prop="avg_minutes" width="96" sortable align="right">
          <template #default="{ row }">
            <span :title="`${row.avg_minutes} 分钟`">{{ fmtAvg(row.avg_minutes) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近使用" prop="last_used" width="108" sortable>
          <template #default="{ row }">
            <span :class="{ muted: !row.last_used }">{{ row.last_used || '无记录' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="归因来源" width="108">
          <template #default="{ row }">
            <el-tooltip :content="sourceTip(row)" placement="top">
              <el-tag size="small" :style="sourceStyle(row)" effect="plain">
                {{ sourceLabel(row) }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && !items.length"
        :description="emptyText"
        :image-size="70"
      />
    </el-card>

    <!-- 批量设置 -->
    <el-dialog v-model="bulkVisible" title="批量设置 L2 类型 / L1 归因" width="480px">
      <el-form label-width="110px" size="small">
        <el-form-item label="L2 活动类型" required>
          <el-select v-model="bulkForm.activity_type" style="width:100%">
            <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="L1 价值归因">
          <el-select v-model="bulkForm.attribution" style="width:100%">
            <el-option label="不修改（保留现状）" :value="ATTR_KEEP" />
            <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="`设为 ${a}`" :value="a" />
            <el-option label="撤销覆盖（回到类型默认）" :value="ATTR_CLEAR" />
          </el-select>
        </el-form-item>
        <div class="bulk-tip">
          影响 {{ selectedNames.length }} 个任务名下的全部记录：
          {{ selectedNames.slice(0, 6).join('、') }}{{ selectedNames.length > 6 ? ' 等' : '' }}
        </div>
      </el-form>
      <template #footer>
        <el-button size="small" @click="bulkVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="applyBulk">应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh, Search } from '@element-plus/icons-vue'
import * as temporalApi from '../api/temporalApi'
import { useTemporalStore } from '../stores/temporalStore'
import {
  ACTIVITY_TYPE_OPTIONS, ATTR_CLEAR, ATTR_SOURCE_MAP, ATTRIBUTION_COLOR_MAP, ATTRIBUTION_OPTIONS,
  RULE_FIELD_LABEL, ruleIsRowScoped,
} from '../types/temporalTypes'
import type { AttrRuleField, AttributionSource, MetaLedgerItem, MetaLedgerSummary } from '../types/temporalTypes'

/** 批量弹窗的「不修改」哨兵（与 ATTR_CLEAR 区分：前者保留现状，后者撤销覆盖） */
const ATTR_KEEP = '__keep__'

const store = useTemporalStore()

const items = ref<MetaLedgerItem[]>([])
const loading = ref(false)
const saving = ref(false)
const savingRow = ref<string | null>(null)
/**
 * 行内下拉的「强制重建」计数器。
 *
 * 归因下拉是**受控**写法（`:model-value` 而非 `v-model`）：用户点选后若流程被取消
 * （确认框取消 / 命中 L2 规则被拦截），数据没变 → prop 值没变 → el-select 仍显示
 * 用户刚点的那个假值。递增本值可让 key 变化、重建组件，显示回到行数据的真实归因。
 */
const rev = ref(0)
const tableRef = ref<any>(null)
const selectedNames = ref<string[]>([])

const filter = reactive<{ search: string; activityType: string; attribution: string; unclassifiedOnly: boolean }>({
  search: '', activityType: '', attribution: '', unclassifiedOnly: false,
})

const EMPTY_SUMMARY: MetaLedgerSummary = {
  total: 0, classified: 0, unclassified: 0, total_hours: 0, unclassified_hours: 0,
  by_attribution: { 成长: 0, 关系: 0, 维持: 0, 谋生: 0, 流失: 0 },
}
const summary = ref<MetaLedgerSummary>({ ...EMPTY_SUMMARY })

const bulkVisible = ref(false)
const bulkForm = reactive<{ activity_type: string; attribution: string }>({
  activity_type: '', attribution: ATTR_KEEP,
})

const maxHours = computed(() => Math.max(...items.value.map(i => i.total_hours), 1))

const emptyText = computed(() => {
  if (filter.unclassifiedOnly) return '全部已归类 🎉 新任务名会在 CSV 导入后落到这里'
  if (filter.search || filter.activityType || filter.attribution) return '没有匹配的任务名'
  return '暂无任务名'
})

const defaultSort = { prop: 'total_hours', order: 'descending' as const }

function attrColor(name: string) { return ATTRIBUTION_COLOR_MAP[name] || '#94A3B8' }

function attrPct(key: string) {
  const total = summary.value.total_hours
  if (!total) return '0.0'
  const v = key === '__unclassified__' ? summary.value.unclassified_hours : (summary.value.by_attribution[key] || 0)
  return ((v / total) * 100).toFixed(1)
}

function fmtAvg(minutes: number) {
  if (!minutes) return '—'
  return minutes >= 60 ? `${(minutes / 60).toFixed(1)}h` : `${Math.round(minutes)}min`
}

function barStyle(row: MetaLedgerItem) {
  return { width: `${Math.max((row.total_hours / maxHours.value) * 100, 2)}%`, background: attrColor(row.effective_attribution || '') }
}

function sourceLabel(row: MetaLedgerItem) {
  const s = row.attribution_source as AttributionSource | null
  if (!s) return '—'
  // 规则来源再细分维度：让「这条撤不掉」肉眼可见，而不是点了撤销才发现
  if (s === 'rule' && row.rule_field && !ruleIsRowScoped(row.rule_field)) {
    return row.rule_field === 'activity_type' ? 'L2 规则' : '任务类型规则'
  }
  return ATTR_SOURCE_MAP[s].label
}

function sourceTip(row: MetaLedgerItem) {
  const s = row.attribution_source as AttributionSource | null
  if (!s) return '无归因信息'
  const base = `${ATTR_SOURCE_MAP[s].tip} 当前生效：${row.effective_attribution}`
  if (s === 'rule' && row.rule_field) {
    const where = `${RULE_FIELD_LABEL[row.rule_field]} = ${row.rule_value}`
    const tail = ruleIsRowScoped(row.rule_field)
      ? '可在本页撤销覆盖'
      : '该规则会同时覆盖同一维度下的其他任务名，需到赎回期「归因规则」页停用'
    return `来自规则：${where}。${base}。${tail}`
  }
  return base
}

function sourceStyle(row: MetaLedgerItem) {
  const s = row.attribution_source as AttributionSource | null
  const c = s ? ATTR_SOURCE_MAP[s].color : '#CBD5E1'
  return { color: c, borderColor: `${c}55`, background: `${c}14` }
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {}
    if (filter.search.trim()) params.search = filter.search.trim()
    if (filter.activityType) params.activity_type = filter.activityType
    if (filter.attribution) params.attribution = filter.attribution
    if (filter.unclassifiedOnly) params.unclassified_only = '1'
    const res = await temporalApi.getMetaLedger(params)
    items.value = res.data.items || []
    summary.value = res.data.summary || { ...EMPTY_SUMMARY }
  } catch { items.value = [] } finally { loading.value = false }
}

function resetFilter() {
  filter.search = ''; filter.activityType = ''; filter.attribution = ''; filter.unclassifiedOnly = false
  load()
}

function toggleAttrFilter(a: string) {
  filter.attribution = filter.attribution === a ? '' : a
  filter.unclassifiedOnly = false
  load()
}

function toggleUnclassifiedFilter() {
  filter.unclassifiedOnly = !filter.unclassifiedOnly
  filter.attribution = ''
  load()
}

function onSelectionChange(rows: MetaLedgerItem[]) {
  selectedNames.value = rows.map(r => r.task_name)
}

function clearSelection() {
  selectedNames.value = []
  tableRef.value?.clearSelection()
}

/** 批量/单行统一的落库入口：keep_default 保留原归因、clear_rule 撤销覆盖 */
async function setMeta(taskNames: string[], activityType: string, attr: string) {
  const payload: Record<string, unknown> = { task_names: taskNames, activity_type: activityType }
  if (attr === ATTR_KEEP) {
    payload.keep_default = true
  } else if (attr === ATTR_CLEAR) {
    payload.keep_default = true
    payload.clear_rule = true
  } else {
    payload.attribution = attr
  }
  return store.batchSetMeta(payload)
}

/** 取消 / 被拦截后，把行内下拉的显示拉回数据真实值（受控 prop 未变，须靠 key 重建） */
function resetRowSelect() {
  rev.value += 1
}

async function onAttrChange(row: MetaLedgerItem, value: string) {
  if (value === row.effective_attribution && row.attribution_source !== 'fallback') return
  if (value === ATTR_CLEAR) {
    // 归因来自 L2 活动类型 / 任务类型的规则：这类规则同时覆盖同一维度下的其他任务名，
    // 单行「撤销」既撤不掉、也不该撤（会连坐）。如实说明并指路，不发出请求。
    if (row.attribution_source === 'rule' && row.rule_field && !ruleIsRowScoped(row.rule_field)) {
      const where = `${RULE_FIELD_LABEL[row.rule_field]}「${row.rule_value}」`
      ElMessageBox.alert(
        `「${row.task_name}」的归因来自一条按${where}的规则，该规则同时覆盖同一维度下的其他任务名，`
        + '不能在这里按单行撤销。如需调整，请到「赎回期 → 归因规则」停用或删除该规则。',
        '这条覆盖撤不掉', { type: 'warning', confirmButtonText: '知道了' },
      ).catch(() => {})
      resetRowSelect()
      return
    }
    const ok = await confirmClear(row)
    if (!ok) {
      resetRowSelect()
      return
    }
  }
  savingRow.value = row.task_name
  try {
    const res = await setMeta([row.task_name], row.activity_type, value)
    if (value !== ATTR_CLEAR) {
      ElMessage.success(`已将「${row.task_name}」的 L1 归因设为 ${value}（同时写入赎回期规则）`)
    } else {
      // 后端在撤销**之后**重新解析真实状态：同名规则撤掉了、也可能被 L2 规则接管，
      // 此时再报「已撤销」就是假成功 —— 有 blocked 就必须如实说清还剩什么在生效。
      const b = ((res as { data?: { blocked?: Array<Record<string, unknown>> } })?.data?.blocked || [])[0]
      if (b) {
        const field = RULE_FIELD_LABEL[b.rule_field as AttrRuleField] ?? String(b.rule_field)
        ElMessage.warning(
          `已停用按任务名的覆盖${b.cleared ? '' : '（本就没有按任务名的规则）'}；`
          + `但「${b.task_name}」仍命中按${field}「${b.rule_value}」的规则，归因仍为 ${b.attribution}。`
          + '需到「赎回期 → 归因规则」停用该规则。',
        )
      } else {
        ElMessage.success(`已撤销「${row.task_name}」的归因覆盖，回到类型默认`)
      }
    }
    await load()
  } catch { ElMessage.error('保存失败') } finally { savingRow.value = null }
}

function confirmClear(row: MetaLedgerItem) {
  return ElMessageBox.confirm(
    `撤销「${row.task_name}」的赎回期归因覆盖后，该任务名将回到类型默认（${row.default_attribution || '兜底成长'}）。规则会被停用而非删除，可追溯。`,
    '撤销归因覆盖', { type: 'warning', confirmButtonText: '撤销覆盖', cancelButtonText: '取消' },
  ).then(() => true).catch(() => false)
}

async function onTypeChange(row: MetaLedgerItem, value: string) {
  if (value === row.activity_type) return
  savingRow.value = row.task_name
  try {
    // 只改 L2：保留原默认归因与已有规则，不产生归因副作用
    await setMeta([row.task_name], value, ATTR_KEEP)
    ElMessage.success(`已将「${row.task_name}」的 L2 类型改为 ${value}`)
    await load()
  } catch { ElMessage.error('保存失败') } finally { savingRow.value = null }
}

function openBulk() {
  bulkForm.activity_type = ''
  bulkForm.attribution = ATTR_KEEP
  bulkVisible.value = true
}

async function applyBulk() {
  if (!selectedNames.value.length || !bulkForm.activity_type) return
  saving.value = true
  try {
    const res = await setMeta([...selectedNames.value], bulkForm.activity_type, bulkForm.attribution)
    // ⚠️ 取数层级：setMeta 返回的是 axios response，后端的 updated/cleared/blocked 在 res.data 上
    // （曾误写成 res.cleared，恒为 undefined → 撤销条数永远不显示）
    const d = (res as {
      data?: { updated?: number; cleared?: number; blocked?: Array<Record<string, unknown>> }
    })?.data || {}
    const blocked = d.blocked || []
    let msg = `已更新 ${d.updated ?? 0} 个任务名`
    if (bulkForm.attribution === ATTR_CLEAR) {
      if (d.cleared) msg += `，撤销 ${d.cleared} 条归因覆盖`
      if (blocked.length) {
        msg += `；仍有 ${blocked.length} 个任务名被按 L2/任务类型的规则覆盖，需到「赎回期 → 归因规则」停用`
      }
    }
    if (blocked.length) ElMessage.warning(msg)
    else ElMessage.success(msg)
    bulkVisible.value = false
    clearSelection()
    await load()
  } catch { ElMessage.error('批量失败') } finally { saving.value = false }
}

onMounted(load)
</script>

<style scoped lang="scss">
.mapping-editor { padding: 20px; background: #F5F7FA; min-height: 100vh;
  .page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
    h2 { margin: 0; font-size: 20px; }
    .header-right { margin-left: auto; } }
  .page-desc { margin: 0 0 12px; font-size: 12px; color: #64748B; }
  .hint-alert { margin-bottom: 14px; }

  .panel-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    :deep(.el-card__body) { padding: 0; } }
  .summary-card { margin-bottom: 14px;
    :deep(.el-card__body) { padding: 14px 16px 12px; } }

  .summary-strip { display: flex; gap: 12px; flex-wrap: wrap;
    .sum-item { flex: 1 1 150px; min-width: 130px; padding: 8px 12px; border-radius: 8px; background: #F8FAFC;
      .sum-label { font-size: 12px; color: #64748B; }
      .sum-value { font-size: 22px; font-weight: 600; color: #1F2937; line-height: 1.4;
        small { font-size: 12px; font-weight: 400; color: #94A3B8; margin-left: 2px; } }
      .sum-note { font-size: 11px; color: #94A3B8;
        &.muted { color: #CBD5E1; } }
      &.is-ok .sum-note { color: #10B981; } } }

  .attr-chips { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 12px;
    .chips-label { font-size: 12px; color: #64748B; margin-right: 2px; }
    .chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 14px;
      background: #F1F5F9; border: 1px solid transparent; cursor: pointer; font-size: 12px; color: #334155;
      transition: all .15s;
      &:hover { background: #E2E8F0; }
      &.active { background: #EEF2FF; border-color: #6366F1; color: #4338CA; }
      &.dim { opacity: .45; }
      .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
      .chip-hours { font-weight: 600; }
      .chip-pct { color: #94A3B8; font-style: normal; font-size: 11px; } } }

  .filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
    .filter-count { font-size: 12px; color: #94A3B8; } }
  .bulk-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; font-size: 13px; color: #4b5563;
    .bulk-hint { font-size: 12px; color: #9CA3AF; } }

  .table-card { :deep(.el-card__body) { padding: 6px 8px 12px; } }
  .hours-cell { display: flex; flex-direction: column; gap: 3px;
    .hours-num { font-size: 13px; }
    .hours-bar { display: block; height: 3px; border-radius: 2px; background: #EEF2F7;
      i { display: block; height: 100%; border-radius: 2px; } } }

  .muted { color: #b8bcc4; }
  .is-unclassified { color: #94A3B8; }
  .bulk-tip { font-size: 12px; color: #94A3B8; padding-left: 110px; line-height: 1.6; }
}
</style>
