<!--
  物件资产 · 台账表（v3.60.0）

  这个面板回答的是「我有哪些家当、每一件现在什么状态」。

  🔴 表里**没有一个前端算出来的数**：已用月数、剩余月数、月折旧、净值、
     `is_overdue` 全部来自后端。这里只把数按 `format.ts` / `propertyFormat.ts`
     说成人话。

  🔴 三条展示纪律（都是踩过的地方）：
     ① **null 显示「—」，绝不显示 0**。`current_value === null` 是「算不出来」
        （缺金额 / 缺日期 / 缺年限），而 `¥0.00` 是「真的不值钱了」。
        界面上必须能分辨 —— 一个该去补数据，其余该考虑换新或处理。
        而且「—」旁边要能点开看**为什么**（issues 那几句），
        否则用户只看得到一个没有出口的破折号。
     ② **超期只做中性标注，不涂色**。「用超了」是事实，不是错误 ——
        它不是红黄绿，也不弹窗、不建议更换。
     ③ **按金额排序时未填金额的恒排最后**（`sortItemsByAmount` 里处理）。
        若按 0 排序，升序时那批「想不起来多少钱」的物件会挤在最前面，
        看起来像一堆破铜烂铁 —— 而实际上它们只是**没填**。

  🔴 「¥0.00」也有**两个来源**（2026-09-26 起），小字按 `zero_reason` 分：
        depreciated → 「已折完」（用够年限了，该换新）
        broken      → 「损坏归 0」（还没到期就坏了，该修或该扔）
     ⚠️ 判断依据是后端下发的 `zero_reason`，**不是** `condition === 'broken'` ——
        在前端判就是第二份口径，下次改口径必然漏一份。

  ⚠️ 排序**在前端做**（后端刻意不开 `?ordering=`）：一旦开到后端，
     `current_value`（派生值、不落库）就会被逼着落库。
     筛选也在前端做 —— 家当量级小，且四卡点击筛选要跟列表**瞬时**联动。

  ⚠️ 「状态」与「状况」是**两列**，不合并：状态决定它进不进四卡与合计，
     状况只影响净值那一格（标了「损坏」就按 0 计，见设计稿 §4.3 订正条）。
-->

<template>
  <div class="property-table">
    <div class="property-table__filters">
      <el-input
        v-model="search"
        size="small"
        placeholder="搜物件名"
        clearable
        class="property-table__search"
      />
      <el-select
        v-model="category"
        size="small"
        clearable
        placeholder="全部类别"
        class="property-table__select"
      >
        <el-option
          v-for="option in categories"
          :key="option.id"
          :label="option.name"
          :value="option.id"
        />
      </el-select>
      <el-select
        v-model="status"
        size="small"
        clearable
        placeholder="全部状态"
        class="property-table__select"
      >
        <el-option
          v-for="option in statusOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-select
        v-model="condition"
        size="small"
        clearable
        placeholder="全部状况"
        class="property-table__select"
      >
        <el-option
          v-for="option in conditionOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-button
        v-if="hasFilter"
        link
        size="small"
        type="primary"
        @click="clearFilters"
      >
        清空筛选
      </el-button>
      <span v-if="sortHint" class="property-table__sort-hint">{{ sortHint }}</span>
      <span class="property-table__count">共 {{ rows.length }} 件</span>
    </div>

    <el-empty
      v-if="!rows.length"
      :description="emptyText"
      :image-size="60"
    />

    <el-table
      v-else
      :data="rows"
      size="small"
      class="property-table__grid"
      row-key="id"
      @sort-change="onSortChange"
    >
      <el-table-column label="物件" min-width="180">
        <template #default="{ row }">
          <div class="property-table__name">{{ row.name }}</div>
          <div v-if="row.spec || row.location" class="property-table__meta">
            <span v-if="row.spec">{{ row.spec }}</span>
            <span v-if="row.spec && row.location"> · </span>
            <span v-if="row.location">{{ row.location }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="category_name" label="类别" width="84" />

      <el-table-column
        prop="purchase_amount"
        label="金额"
        width="118"
        sortable="custom"
        align="right"
      >
        <template #default="{ row }">
          <!-- 未填金额不是「便宜」，所以单独给一个淡一点的样式 + 悬停解释 -->
          <span v-if="row.purchase_amount === null" class="property-table__unpriced">未填</span>
          <span v-else class="property-table__money">
            {{ formatMoneyOrDash(row.purchase_amount) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="购买日期" width="106">
        <template #default="{ row }">
          <span v-if="row.purchase_date">{{ row.purchase_date }}</span>
          <span v-else class="property-table__unpriced">—</span>
        </template>
      </el-table-column>

      <el-table-column label="已用 / 计划" min-width="150">
        <template #default="{ row }">
          <div>{{ formatUsedVsPlanned(row.age_months, row.lifespan_months) }}</div>
          <!-- 中性标注：不涂色、不加图标、不建议更换 -->
          <div v-if="row.is_overdue" class="property-table__overdue">
            {{ formatOverdue(row.overdue_months) }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="净值" width="118" align="right">
        <template #default="{ row }">
          <template v-if="row.current_value !== null">
            <span class="property-table__money">{{ formatMoneyOrDash(row.current_value) }}</span>
            <!-- 「¥0.00」是**结论**、不是缺数据，所以带一行小字说清是哪个结论 -->
            <div v-if="zeroReasonLabel(row)" class="property-table__zero">
              {{ zeroReasonLabel(row) }}
            </div>
          </template>
          <!-- 🔴 绝不显示 0 —— 「—」旁边必须能点开看为什么 -->
          <el-tooltip
            v-else
            :content="explain(row)"
            placement="top"
            :show-after="120"
            :disabled="!row.issues.length"
          >
            <span class="property-table__dash">—</span>
          </el-tooltip>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="88">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small" effect="plain">
            {{ store.statusLabels[row.status] ?? row.status }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="状况" width="80">
        <template #default="{ row }">
          <el-tag
            v-if="row.condition === 'broken'"
            type="warning"
            size="small"
            effect="plain"
          >
            {{ store.conditionLabels[row.condition] ?? row.condition }}
          </el-tag>
          <span v-else class="property-table__ok">
            {{ store.conditionLabels[row.condition] ?? row.condition }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="104" fixed="right">
        <template #default="{ row }">
          <el-button link size="small" @click="emit('edit', row.id)">编辑</el-button>
          <el-button link size="small" type="danger" @click="emit('delete', row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { usePropertyStore } from '../../stores/propertyStore'
import {
  amountSortHint, formatMoneyOrDash, formatOverdue, formatUsedVsPlanned,
  formatZeroReason, sortItemsByAmount,
} from '../../utils/propertyFormat'
import type {
  AmountSortOrder,
} from '../../utils/propertyFormat'
import type { PropertyItem, PropertyOption } from '../../types/propertyTypes'

const props = defineProps<{
  /** 全部物件（未筛选）—— 筛选与排序都在这个组件里做 */
  items: PropertyItem[]
}>()

const emit = defineEmits<{
  edit: [id: number]
  delete: [id: number]
}>()

const store = usePropertyStore()

// ─── 筛选项（`defineModel`：四卡点击要能直接改状态这一项） ───
const search = defineModel<string>('search', { default: '' })
const category = defineModel<number | null>('category', { default: null })
const status = defineModel<string>('status', { default: '' })
const condition = defineModel<string>('condition', { default: '' })

const categories = computed(() => store.categories)
const statusOptions = computed<PropertyOption[]>(() => store.statusOptions)
const conditionOptions = computed<PropertyOption[]>(() => store.conditionOptions)

/** 排序方向 —— ⚠️ **不写回 store**：store 里那份永远保持后端给的默认序 */
const sortOrder = ref<AmountSortOrder>(null)

const hasFilter = computed(
  () => !!search.value || category.value !== null || !!status.value || !!condition.value,
)

const emptyText = computed(() =>
  hasFilter.value
    ? '没有符合条件的物件 —— 换个筛选条件，或者清空筛选'
    : '还没有登记任何家当 —— 点右上角「新增物件」开始盘',
)

/**
 * ⚠️ 顺序要紧：**先筛再排**。
 *    反过来（先排再筛）在结果上等价，但一旦以后有人给「筛选」加上
 *    「按当前排序取前 N 件」这类语义，两种写法就会分叉 —— 先把集合收敛好再排序，
 *    这个顺序不依赖任何隐含前提。
 */
const rows = computed<PropertyItem[]>(() => {
  const text = search.value.trim().toLowerCase()
  const filtered = props.items.filter((item) => {
    if (text && !item.name.toLowerCase().includes(text)) return false
    if (category.value !== null && item.category_id !== category.value) return false
    if (status.value && item.status !== status.value) return false
    if (condition.value && item.condition !== condition.value) return false
    return true
  })
  return sortItemsByAmount(filtered, sortOrder.value)
})

const sortHint = computed(() => amountSortHint(sortOrder.value))

function onSortChange(payload: { prop: string | null; order: string | null }) {
  if (payload.prop !== 'purchase_amount') return
  // element-plus 的 order 是 'ascending' / 'descending' / null
  if (payload.order === 'ascending') sortOrder.value = 'asc'
  else if (payload.order === 'descending') sortOrder.value = 'desc'
  else sortOrder.value = null
}

function clearFilters() {
  search.value = ''
  category.value = null
  status.value = ''
  condition.value = ''
}

/**
 * 净值为 0 时的小字 —— 「已折完」或「损坏归 0」，**取不到就返回空串**（不渲染）。
 *
 * 🔴 判断依据是后端下发的 `zero_reason`，不是 `row.condition === 'broken'`：
 *    在后端判是口径，在前端判是第二份口径 —— 两份迟早不一致，且不一致是静默的
 *    （「坏了的」被写成「用够了的」，两句话看着都对）。
 */
function zeroReasonLabel(row: PropertyItem): string {
  return formatZeroReason(row.zero_reason)
}

/** 算不出的原因，一句话 —— 气泡直接渲染它 */
function explain(row: PropertyItem): string {
  return store.explain(row)
}

/**
 * 状态标签的类型。
 *
 * ⚠️ 「已报废」**不用红色**：报废是正常生命周期的一部分（东西用坏了就该报废），
 *    把它涂成错误色会让「我淘汰过什么」这件正常的事看起来像出了故障。
 *    同项目「盘盈盘亏只按『要不要留意』上色」的判据。
 */
function statusTagType(value: string): 'success' | 'info' | 'primary' | 'warning' {
  if (value === 'in_use') return 'success'
  if (value === 'idle') return 'info'
  if (value === 'scrapped') return 'info'
  return 'primary'
}
</script>

<style scoped>
.property-table__filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.property-table__search {
  width: 180px;
}
.property-table__select {
  width: 128px;
}
.property-table__sort-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-table__count {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-table__grid {
  width: 100%;
}
.property-table__name {
  font-weight: 600;
}
.property-table__meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-table__money {
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}
.property-table__unpriced {
  color: var(--el-text-color-placeholder);
}
.property-table__dash {
  color: var(--el-text-color-placeholder);
  cursor: default;
}
.property-table__overdue {
  /* 中性标注：事实，不是错误 —— 所以只是灰字，没有图标、没有颜色 */
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-table__zero {
  /* 中性标注：是结论、不是错误 —— 所以只是灰字，没有图标、没有颜色 */
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-table__ok {
  color: var(--el-text-color-secondary);
}
</style>
