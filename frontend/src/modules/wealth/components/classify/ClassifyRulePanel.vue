<template>
  <div class="classify-panel">
    <div class="panel-header">
      <div class="panel-header__left">
        <h3>账单项分类规则</h3>
        <span class="panel-header__hint">
          一张规则表同时管三件事：收入是主动还是被动、支出是固定还是可变、现金流归到五类中的哪一类
        </span>
      </div>
      <div class="panel-header__right">
        <el-select
          :model-value="store.yearmon"
          size="small"
          style="width: 130px"
          @change="handlePeriodChange"
        >
          <el-option label="全周期" value="" />
          <el-option v-for="p in store.periods" :key="p" :label="p" :value="p" />
        </el-select>
        <el-dropdown @command="handleSeed">
          <el-button size="small" :loading="saving">
            初始化规则
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="fill">补齐缺失规则（不动你改过的）</el-dropdown-item>
              <el-dropdown-item command="overwrite" divided>
                重置为默认值（会覆盖你改过的规则）
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" size="small" @click="openDialog()">
          <el-icon><Plus /></el-icon>
          新增规则
        </el-button>
      </div>
    </div>

    <el-alert
      class="explain-alert"
      type="info"
      :closable="false"
      show-icon
    >
      <template #title>
        分类是「当前视角」，不是历史事实 —— 改规则会让往期数字一起变
      </template>
      <div class="explain-alert__body">
        金额是已经发生的事实，分类是「你今天怎么看这笔钱」。所以这里不存分类结果，
        每次都按当前规则实时算。改动前请先点「影响预览」看会动多少；
        若只是想暂时不生效，用「停用」而不是删除。
      </div>
    </el-alert>

    <!-- ── 覆盖率：三个维度各自算账，分母不同 ── -->
    <div v-if="summary" class="coverage-block">
      <div class="coverage-block__title">
        归类覆盖率
        <span class="coverage-block__period">{{ summary.period_label }}</span>
      </div>
      <div class="coverage-grid">
        <div class="coverage-item">
          <div class="coverage-item__head">
            <span>收入性质</span>
            <span class="coverage-item__pct">{{ pct(summary.coverage.income_type) }}</span>
          </div>
          <el-progress
            :percentage="Math.round(summary.coverage.income_type * 100)"
            :stroke-width="8"
            :show-text="false"
            :color="coverageColor(summary.coverage.income_type)"
          />
          <div class="coverage-item__foot">
            分母 = 收入合计 {{ money(summary.income.total) }}；
            未归类 {{ money(summary.income.unclassified) }} / {{ summary.income.count }} 笔
          </div>
        </div>
        <div class="coverage-item">
          <div class="coverage-item__head">
            <span>支出刚性</span>
            <span class="coverage-item__pct">{{ pct(summary.coverage.expense_nature) }}</span>
          </div>
          <el-progress
            :percentage="Math.round(summary.coverage.expense_nature * 100)"
            :stroke-width="8"
            :show-text="false"
            :color="coverageColor(summary.coverage.expense_nature)"
          />
          <div class="coverage-item__foot">
            分母 = 支出合计 {{ money(summary.expense.total) }}；
            未归类 {{ money(summary.expense.unclassified) }} / {{ summary.expense.count }} 笔
          </div>
        </div>
        <div class="coverage-item">
          <div class="coverage-item__head">
            <span>现金流类别</span>
            <span class="coverage-item__pct">{{ pct(summary.coverage.cashflow_class) }}</span>
          </div>
          <el-progress
            :percentage="Math.round(summary.coverage.cashflow_class * 100)"
            :stroke-width="8"
            :show-text="false"
            :color="coverageColor(summary.coverage.cashflow_class)"
          />
          <div class="coverage-item__foot">
            分母 = 收支合计 {{ money(summary.bill_amount) }}；
            未归类 {{ money(summary.cashflow.unclassified) }}
          </div>
        </div>
      </div>
    </div>

    <!-- ── 三维度构成（纯 CSS 条，不走 ECharts）── -->
    <div v-if="summary" class="breakdown-grid">
      <div class="breakdown">
        <div class="breakdown__title">收入性质</div>
        <div
          v-for="t in INCOME_TYPES"
          :key="t"
          class="breakdown__row"
        >
          <span class="breakdown__label">{{ t }}</span>
          <span class="breakdown__bar">
            <i
              class="breakdown__fill"
              :class="`breakdown__fill--income-${incomeIndex(t)}`"
              :style="{ width: barWidth(summary.income.by_type[t], summary.income.total) }"
            />
          </span>
          <span class="breakdown__value">{{ money(summary.income.by_type[t]) }}</span>
        </div>
        <div class="breakdown__row breakdown__row--muted">
          <span class="breakdown__label">未归类</span>
          <span class="breakdown__bar">
            <i
              class="breakdown__fill breakdown__fill--none"
              :style="{ width: barWidth(summary.income.unclassified, summary.income.total) }"
            />
          </span>
          <span class="breakdown__value">{{ money(summary.income.unclassified) }}</span>
        </div>
      </div>

      <div class="breakdown">
        <div class="breakdown__title">支出刚性</div>
        <div
          v-for="n in EXPENSE_NATURES"
          :key="n"
          class="breakdown__row"
        >
          <span class="breakdown__label">{{ n }}</span>
          <span class="breakdown__bar">
            <i
              class="breakdown__fill"
              :class="n === '固定' ? 'breakdown__fill--fixed' : 'breakdown__fill--variable'"
              :style="{ width: barWidth(summary.expense.by_nature[n], summary.expense.total) }"
            />
          </span>
          <span class="breakdown__value">{{ money(summary.expense.by_nature[n]) }}</span>
        </div>
        <div class="breakdown__row breakdown__row--muted">
          <span class="breakdown__label">未归类</span>
          <span class="breakdown__bar">
            <i
              class="breakdown__fill breakdown__fill--none"
              :style="{ width: barWidth(summary.expense.unclassified, summary.expense.total) }"
            />
          </span>
          <span class="breakdown__value">{{ money(summary.expense.unclassified) }}</span>
        </div>
      </div>

      <div class="breakdown">
        <div class="breakdown__title">现金流五类归集</div>
        <div
          v-for="c in CASHFLOW_CLASSES"
          :key="c"
          class="breakdown__row"
        >
          <span class="breakdown__label">{{ c }}</span>
          <span class="breakdown__bar">
            <i
              class="breakdown__fill"
              :class="c === '收入流入' ? 'breakdown__fill--inflow' : 'breakdown__fill--outflow'"
              :style="{ width: barWidth(summary.cashflow[c], summary.bill_amount) }"
            />
          </span>
          <span class="breakdown__value">{{ money(summary.cashflow[c]) }}</span>
        </div>
        <div class="breakdown__row breakdown__row--muted">
          <span class="breakdown__label">未归类</span>
          <span class="breakdown__bar">
            <i
              class="breakdown__fill breakdown__fill--none"
              :style="{ width: barWidth(summary.cashflow.unclassified, summary.bill_amount) }"
            />
          </span>
          <span class="breakdown__value">{{ money(summary.cashflow.unclassified) }}</span>
        </div>
      </div>
    </div>

    <!-- ── 排除项：转入/转出/余额变更 ── -->
    <div v-if="summary && visibleExcluded.length" class="excluded-strip">
      <span class="excluded-strip__label">未计入（账户间搬运与对账修正，不是收支）：</span>
      <el-tag
        v-for="row in visibleExcluded"
        :key="row.transaction_type"
        size="small"
        type="info"
        effect="plain"
      >
        {{ row.transaction_type }} {{ row.count }} 笔 {{ money(row.amount) }}
      </el-tag>
    </div>

    <!-- ── 未归类候选：下一条规则该建在哪儿 ── -->
    <div class="section">
      <div class="section__head">
        <h4>未归类候选</h4>
        <span class="section__hint">
          共 {{ unclassified?.total_count ?? 0 }} 笔 / {{ money(unclassified?.total_amount) }} ——
          按金额降序，在这里直接建规则最划算
        </span>
      </div>
      <el-table
        v-if="unclassified && unclassified.items.length"
        :data="unclassified.items"
        size="small"
        stripe
        style="width: 100%"
      >
        <el-table-column label="分类 / 子分类" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.category || '（无分类）' }}
            <span class="muted"> / {{ row.subcategory || '（无子分类）' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="笔数" width="70" align="right">
          <template #default="{ row }">{{ row.count }}</template>
        </el-table-column>
        <el-table-column label="金额" width="120" align="right">
          <template #default="{ row }">{{ money(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="缺什么" min-width="150">
          <template #default="{ row }">
            <el-tag
              v-for="d in row.missing_dimensions"
              :key="d"
              size="small"
              effect="plain"
              class="inline-tag"
            >{{ DIMENSION_LABELS[d] || d }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="商户样本" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.merchant_samples.length">
              {{ row.merchant_samples.map(maskMerchant).join('、') }}
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialogFromCandidate(row)">
              建规则
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="empty-hint">
        这一期没有未归类的收支项 —— 规则已覆盖全部记录。
      </div>
    </div>

    <!-- ── 规则台账 ── -->
    <div class="section">
      <div class="section__head">
        <h4>规则台账</h4>
        <div class="section__head-right">
          <span v-if="ruleSummary" class="section__hint">
            启用 {{ ruleSummary.active }} / 共 {{ ruleSummary.total }} 条
            （分类 {{ ruleSummary.by_field.category ?? 0 }} ·
            子分类 {{ ruleSummary.by_field.subcategory ?? 0 }} ·
            商户 {{ ruleSummary.by_field.merchant ?? 0 }}）
          </span>
          <el-checkbox
            :model-value="store.includeInactive"
            size="small"
            @change="handleIncludeInactive"
          >显示停用</el-checkbox>
        </div>
      </div>
      <el-table
        :data="store.rules"
        v-loading="loading"
        size="small"
        stripe
        style="width: 100%"
      >
        <el-table-column label="匹配字段" width="90">
          <template #default="{ row }">{{ fieldLabel(row.rule_field) }}</template>
        </el-table-column>
        <el-table-column label="匹配值" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ displayRuleValue(row) }}</template>
        </el-table-column>
        <el-table-column label="收入性质" width="90" align="center">
          <template #default="{ row }">
            <span v-if="row.income_type">{{ row.income_type }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="支出刚性" width="90" align="center">
          <template #default="{ row }">
            <span v-if="row.expense_nature">{{ row.expense_nature }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="现金流类别" width="100">
          <template #default="{ row }">
            <span v-if="row.cashflow_class">{{ row.cashflow_class }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="76" align="right">
          <template #default="{ row }">{{ row.priority }}</template>
        </el-table-column>
        <el-table-column label="状态" width="76" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" size="small" type="success" effect="plain">启用</el-tag>
            <el-tag v-else size="small" type="info" effect="plain">停用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.note">{{ row.note }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button link size="small" @click="handleToggle(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="field-hint mt-8">
        匹配是<b>精确相等</b>，不是模糊包含。优先级数值大者胜；同优先级时
        <b>更具体的字段胜</b>（商户 &gt; 子分类 &gt; 分类）。
      </div>
    </div>

    <!-- ── 规则弹窗 ── -->
    <el-dialog
      v-model="showDialog"
      :title="form.id ? '编辑分类规则' : '新增分类规则'"
      width="620px"
      append-to-body
    >
      <el-form label-width="96px" label-position="right">
        <el-form-item label="匹配字段" required>
          <el-select v-model="form.rule_field" style="width: 180px" @change="onFieldChange">
            <el-option
              v-for="f in CLASSIFY_RULE_FIELDS"
              :key="f.value"
              :label="f.label"
              :value="f.value"
            />
          </el-select>
          <span class="field-hint ml-8">
            {{ FIELD_HINTS[form.rule_field] }}
          </span>
        </el-form-item>
        <el-form-item label="匹配值" required>
          <el-input v-model="form.match_value" placeholder="与账单项该字段完全相等才命中" />
        </el-form-item>

        <el-form-item label="收入性质">
          <el-select v-model="form.income_type" clearable style="width: 180px">
            <el-option v-for="t in INCOME_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
          <span class="field-hint ml-8">只对收入行生效</span>
        </el-form-item>
        <el-form-item label="支出刚性">
          <el-select v-model="form.expense_nature" clearable style="width: 180px">
            <el-option v-for="n in EXPENSE_NATURES" :key="n" :label="n" :value="n" />
          </el-select>
          <span class="field-hint ml-8">只对支出行生效</span>
        </el-form-item>
        <el-form-item label="现金流类别">
          <el-select v-model="form.cashflow_class" clearable style="width: 180px">
            <el-option v-for="c in CASHFLOW_CLASSES" :key="c" :label="c" :value="c" />
          </el-select>
          <span class="field-hint ml-8">按收支方向自动取用对应的一半</span>
        </el-form-item>

        <el-form-item label="优先级">
          <el-input-number
            v-model="form.priority"
            :min="0"
            :max="999"
            :controls="false"
            style="width: 120px"
          />
          <span class="field-hint ml-8">{{ priorityHint }}</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" placeholder="为什么这么设 —— 半年后你会感谢自己" />
        </el-form-item>

        <el-alert
          type="warning"
          :closable="false"
          show-icon
          class="hint-alert"
        >
          三个标签至少要设一个，否则这条规则命中后什么都不会发生。
        </el-alert>

        <!-- 影响预览结果 -->
        <div v-if="preview" class="preview-box">
          <div class="preview-box__head">
            影响预览（{{ preview.period_label }}，未写库）
          </div>
          <div class="preview-box__stats">
            <span>命中 <b>{{ preview.matched_count }}</b> 笔 /
              {{ money(preview.matched_amount) }}</span>
            <span :class="{ 'preview-box__warn': preview.changed_count > 0 }">
              其中会改变标签 <b>{{ preview.changed_count }}</b> 笔 /
              {{ money(preview.changed_amount) }}
            </span>
          </div>
          <el-table
            v-if="preview.samples.length"
            :data="preview.samples"
            size="small"
            max-height="200"
          >
            <el-table-column label="日期" width="110">
              <template #default="{ row }">{{ shortDate(row.date) }}</template>
            </el-table-column>
            <el-table-column label="分类" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.category }}<span class="muted">/{{ row.subcategory }}</span>
              </template>
            </el-table-column>
            <el-table-column label="金额" width="100" align="right">
              <template #default="{ row }">{{ money(row.amount) }}</template>
            </el-table-column>
            <el-table-column label="标签变化" min-width="200">
              <template #default="{ row }">
                <span class="preview-box__before">{{ labelSummary(row.before) }}</span>
                <span class="preview-box__arrow"> → </span>
                <span class="preview-box__after">{{ labelSummary(row.after) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-form>

      <template #footer>
        <el-button :loading="previewing" @click="handlePreview">影响预览</el-button>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, ArrowDown } from '@element-plus/icons-vue'
import { useClassifyStore } from '../../stores/classifyStore'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import { formatAmount } from '@/shared/utils/format'
import {
  CLASSIFY_RULE_FIELDS, INCOME_TYPES, EXPENSE_NATURES, CASHFLOW_CLASSES,
} from '../../types/wealthTypes'
import type {
  ClassifyRuleItem, ClassifyRuleFormData, ClassifyPreview, UnclassifiedGroup,
} from '../../types/wealthTypes'

/**
 * 分类规则面板（P1-C）。
 *
 * 脱敏判据（按项目 §隐私「展示态才掩、输入态不掩」）：
 *   · 金额 —— 一律 `formatAmount`（它自带掩码），这些是按已落库账单算出的展示值；
 *   · **商户** —— 掩。实测商户取值里含地名（福州 / 宁德 / 杭城），属「地点/文本」；
 *     规则匹配值若匹配的是商户，也一并掩；
 *   · **分类 / 子分类名** —— 不掩。那是使用者自建的分类taxonomy
 *     （食品酒水 / 房租 / 学习进修），不是身份信息；掩掉之后面板会完全失去可用性
 *     （认不出该给哪一类建规则），属于「掩码用力过猛」。
 *   · 弹窗内的输入与预览**不掩** —— 正在编辑的值属于输入态。
 */
const store = useClassifyStore()
const { maskText } = usePrivacyMask()

const DIMENSION_LABELS: Record<string, string> = {
  income_type: '收入性质',
  expense_nature: '支出刚性',
  cashflow_class: '现金流类别',
}
const FIELD_HINTS: Record<string, string> = {
  category: '整类一起管 —— 粒度最粗、兜底用',
  subcategory: '把同一分类里性质相反的部分挑出来',
  merchant: '粒度最细 —— 同名商户跨分类时最有用',
}

const summary = computed(() => store.summary)
const unclassified = computed(() => store.unclassified)
const ruleSummary = computed(() => store.ruleSummary)
const loading = computed(() => store.loading)
const saving = computed(() => store.saving)

const visibleExcluded = computed(
  () => (summary.value?.excluded ?? []).filter((row) => row.count > 0),
)

// ─── 展示工具 ───
/** 金额一律走 formatAmount —— 它内部已接隐私开关，展示态无需再判一次 */
function money(value: number | null | undefined): string {
  return `¥${formatAmount(value)}`
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

/** 覆盖率低于 60% 时标成警示色 —— 「大部分钱还没归类」不该看着像健康 */
function coverageColor(value: number): string {
  if (value >= 0.9) return 'var(--el-color-success)'
  if (value >= 0.6) return 'var(--el-color-warning)'
  return 'var(--el-color-danger)'
}

function barWidth(value: number | undefined, total: number | undefined): string {
  const t = Number(total) || 0
  if (!t) return '0%'
  return `${Math.min(100, Math.max(0, ((Number(value) || 0) / t) * 100))}%`
}

function incomeIndex(type: string): number {
  return INCOME_TYPES.indexOf(type as (typeof INCOME_TYPES)[number])
}

function fieldLabel(field: string): string {
  return CLASSIFY_RULE_FIELDS.find((f) => f.value === field)?.label ?? field
}

/** 商户值要掩；分类、子分类值不掩（见文件头说明） */
function maskMerchant(value: string): string {
  return maskText(value)
}

function displayRuleValue(row: ClassifyRuleItem): string {
  return row.rule_field === 'merchant' ? maskMerchant(row.match_value) : row.match_value
}

function shortDate(value: string): string {
  return (value || '').slice(0, 10)
}

function labelSummary(labels: Record<string, string | null> | null): string {
  if (!labels) return '—'
  const parts = [labels.income_type, labels.expense_nature, labels.cashflow_class]
    .filter(Boolean)
  return parts.length ? parts.join(' / ') : '未归类'
}

// ─── 期切换 ───
async function handlePeriodChange(value: string) {
  await store.setPeriod(value)
}

async function handleIncludeInactive(value: string | number | boolean) {
  await store.setIncludeInactive(Boolean(value))
}

// ─── 弹窗 ───
const showDialog = ref(false)
const previewing = ref(false)
const preview = ref<ClassifyPreview | null>(null)

function blankForm(): ClassifyRuleFormData {
  return {
    rule_field: 'subcategory', match_value: '',
    income_type: null, expense_nature: null, cashflow_class: null,
    priority: null, is_active: true, note: '',
  }
}

const form = reactive<ClassifyRuleFormData>(blankForm())

function openDialog(row?: ClassifyRuleItem) {
  Object.assign(form, blankForm())
  preview.value = null
  if (row) {
    Object.assign(form, {
      id: row.id, rule_field: row.rule_field, match_value: row.match_value,
      income_type: row.income_type, expense_nature: row.expense_nature,
      cashflow_class: row.cashflow_class, priority: row.priority,
      is_active: row.is_active, note: row.note,
    })
  }
  showDialog.value = true
}

/** 从未归类候选一键预填 —— 面板的主要用法就是这个按钮 */
function openDialogFromCandidate(row: UnclassifiedGroup) {
  Object.assign(form, blankForm())
  preview.value = null
  form.rule_field = row.suggested_field
  form.match_value = row.suggested_value
  // 缺哪个维度就先给出该维度的选择焦点提示，但不预填猜测值 —— 猜比留白更有害
  showDialog.value = true
}

function onFieldChange() {
  // 换匹配字段时优先级不再适用（默认值按字段派生），清掉让后端重算
  form.priority = null
  preview.value = null
}

const priorityHint = computed(() => {
  const defaults = ruleSummary.value?.default_priority ?? {}
  const field = form.rule_field || 'category'
  const def = defaults[field]
  return def === undefined
    ? '留空则按匹配字段的具体度自动取默认值'
    : `留空 = 按「${fieldLabel(field)}」默认 ${def}；数值大者胜`
})

async function handlePreview() {
  if (!form.rule_field || !form.match_value.trim()) {
    ElMessage.warning('请先填写匹配字段与匹配值')
    return
  }
  previewing.value = true
  try {
    preview.value = await store.previewRule({ ...form })
  } catch (e) {
    ElMessage.error(apiError(e, '预览失败'))
  } finally {
    previewing.value = false
  }
}

async function handleSave() {
  if (!form.match_value.trim()) {
    ElMessage.warning('请填写匹配值')
    return
  }
  if (!form.income_type && !form.expense_nature && !form.cashflow_class) {
    ElMessage.warning('至少要设置一个标签（收入性质 / 支出刚性 / 现金流类别）')
    return
  }
  try {
    await store.saveRule({ ...form })
    showDialog.value = false
    ElMessage.success('已保存 —— 归类结果已按新规则重算')
  } catch (e) {
    ElMessage.error(apiError(e, '保存失败'))
  }
}

// ─── 台账操作 ───
async function handleToggle(row: ClassifyRuleItem) {
  try {
    await store.toggleRule(row)
    ElMessage.success(row.is_active ? '已停用' : '已启用')
  } catch (e) {
    ElMessage.error(apiError(e, '操作失败'))
  }
}

async function handleDelete(row: ClassifyRuleItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除规则「${fieldLabel(row.rule_field)} = ${displayRuleValue(row)}」？\n` +
      '删除后往期报表的分类结果会随之重算；若只是想暂时不生效，建议改为「停用」。',
      '删除规则',
      { type: 'warning', confirmButtonText: '仍然删除', cancelButtonText: '改为停用' },
    )
  } catch {
    return
  }
  try {
    await store.removeRule(row.id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(apiError(e, '删除失败'))
  }
}

async function handleSeed(command: string) {
  const overwrite = command === 'overwrite'
  if (overwrite) {
    try {
      await ElMessageBox.confirm(
        '重置会把所有种子规则的取值覆盖回默认值，你在界面上改过的会被冲掉。确认继续？',
        '重置规则',
        { type: 'warning' },
      )
    } catch {
      return
    }
  }
  try {
    const result = await store.seedRules(overwrite)
    if (result) {
      ElMessage.success(
        `新建 ${result.created} 条，保留 ${result.skipped} 条，覆盖 ${result.updated} 条`,
      )
    }
  } catch (e) {
    ElMessage.error(apiError(e, '初始化失败'))
  }
}

function apiError(e: unknown, fallback: string): string {
  const data = (e as { response?: { data?: unknown } })?.response?.data
  if (typeof data === 'string') return data
  const detail = (data as { detail?: string })?.detail
  if (typeof detail === 'string') return detail
  // 字段级错误（如 {'match_value': ['...']}）也要能显示出来，否则用户只看到「保存失败」
  const firstList = data && typeof data === 'object'
    ? Object.values(data as Record<string, unknown>)[0]
    : null
  if (Array.isArray(firstList) && typeof firstList[0] === 'string') return firstList[0]
  return fallback
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

.explain-alert { margin-bottom: 12px; }
.explain-alert__body {
  font-size: 12px; line-height: 1.6; margin-top: 2px;
  color: var(--el-text-color-regular);
}

.coverage-block { margin-bottom: 14px; }
.coverage-block__title {
  font-size: 13px; font-weight: 600; margin-bottom: 8px;
  display: flex; align-items: baseline; gap: 8px;
}
.coverage-block__period { font-size: 12px; font-weight: 400; color: var(--el-text-color-secondary); }
.coverage-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px; padding: 12px 16px;
  background: var(--el-fill-color-lighter); border-radius: 6px;
}
.coverage-item { display: flex; flex-direction: column; gap: 4px; }
.coverage-item__head {
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12px; color: var(--el-text-color-secondary);
}
.coverage-item__pct {
  font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}
.coverage-item__foot {
  font-size: 11px; color: var(--el-text-color-placeholder); line-height: 1.4;
}

.breakdown-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px; margin-bottom: 12px;
}
.breakdown { display: flex; flex-direction: column; gap: 6px; }
.breakdown__title { font-size: 13px; font-weight: 600; margin-bottom: 2px; }
.breakdown__row {
  display: grid; grid-template-columns: 62px 1fr 96px;
  align-items: center; gap: 8px;
}
.breakdown__row--muted { opacity: 0.75; }
.breakdown__label { font-size: 12px; color: var(--el-text-color-regular); }
.breakdown__bar {
  height: 8px; background: var(--el-fill-color); border-radius: 4px; overflow: hidden;
}
.breakdown__fill { display: block; height: 100%; border-radius: 4px; }
.breakdown__fill--income-0 { background: var(--el-color-primary); opacity: 1; }
.breakdown__fill--income-1 { background: var(--el-color-primary); opacity: 0.7; }
.breakdown__fill--income-2 { background: var(--el-color-primary); opacity: 0.45; }
.breakdown__fill--fixed { background: var(--el-color-success); }
.breakdown__fill--variable { background: var(--el-color-warning); }
.breakdown__fill--inflow { background: var(--el-color-success); }
.breakdown__fill--outflow { background: var(--el-color-primary); opacity: 0.6; }
.breakdown__fill--none { background: var(--el-color-danger); opacity: 0.5; }
.breakdown__value {
  font-size: 12px; text-align: right; font-variant-numeric: tabular-nums;
  color: var(--el-text-color-regular);
}

.excluded-strip {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  padding: 8px 12px; margin-bottom: 12px;
  background: var(--el-fill-color-lighter); border-radius: 6px;
}
.excluded-strip__label { font-size: 12px; color: var(--el-text-color-secondary); }

.section { margin-bottom: 18px; }
.section__head {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 12px; margin-bottom: 8px; flex-wrap: wrap;
}
.section__head h4 { margin: 0; font-size: 14px; font-weight: 600; }
.section__head-right { display: flex; align-items: center; gap: 12px; }
.section__hint { font-size: 12px; color: var(--el-text-color-secondary); }

.inline-tag { margin-right: 4px; }
.muted { color: var(--el-text-color-placeholder); }
.mt-8 { margin-top: 8px; }
.ml-8 { margin-left: 8px; }
.field-hint { font-size: 11px; color: var(--el-text-color-placeholder); line-height: 1.4; }
.empty-hint {
  padding: 20px 0; font-size: 13px; color: var(--el-text-color-secondary);
  text-align: center;
}
.hint-alert { margin-top: 4px; }

.preview-box {
  margin-top: 12px; padding: 10px 12px;
  background: var(--el-fill-color-lighter); border-radius: 6px;
}
.preview-box__head { font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.preview-box__stats {
  display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px;
  color: var(--el-text-color-regular); margin-bottom: 8px;
}
.preview-box__warn { color: var(--el-color-warning); }
.preview-box__before { color: var(--el-text-color-secondary); }
.preview-box__after { color: var(--el-color-primary); font-weight: 600; }
.preview-box__arrow { color: var(--el-text-color-placeholder); }
</style>
