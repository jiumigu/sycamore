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

  ── 分页（v3.60.35） ──

  78 件家当一屏放不下，所以这里分了页。**前端分页，不是后端分页**：
  后端刻意不开 `?ordering=` / `?page=`（理由见上），排序与筛选都在这一层 ⇒
  分页也只能在这一层切「显示」。

  🔴 四条判据（写错任一条都是**静默**的；判据本体与常量统一在
     `utils/survivalPaging.ts` 的文件头，这里只列本表的落点）：
     ① **只切显示** —— `rows` 仍是**全量**结果，计数 / 空态 / 排序都读它，
        切片只发生在 `pageRows` 一处。让计数读切片 ⇒ 统计静默变成「本页的数」
     ② **先排全量、再切片** —— `rows` 已经先筛再排（见它上面的注释），
        切片排在它后面。反过来只排当前页，而**表头箭头照常高亮**
     ③ **筛选一变回第 1 页** + 总页数变小把当前页拉回范围。
        不拉回 ⇒「筛剩 3 件却停在第 3 页」= 一张空表，读作「筛选坏了」
     ④ 勾选跨页保留并念出分布 —— **本表没有勾选**（物件资产没有批量动作），
        所以分页的杀伤半径在这里**只有排序**；哪天加了批量选择，这条要补上

  ⚠️ 与生存资源那四个列表**共用** `utils/survivalPaging.ts` 的常量与判据
     （每页条数选项 / 默认值 / 分页栏显示条件），本组件不再各留一份 ——
     两处各写一份迟早分叉，而分叉是静默的。
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
      <!--
        🔴 计数读的是**全量结果**（`countLabel` 里用 `rows.length`），不是当前页。
           而「有筛选时必须把被筛掉的也念出来」是分页的配套 ——
           筛剩 3 件却只显示「共 3 件」+ 1 页，读作「我库里只有 3 件家当」，
           而实际只是条件把 75 件挡住了。同生存资源清单的 `countLabel`。
      -->
      <span class="property-table__count">{{ countLabel }}</span>
    </div>

    <el-empty
      v-if="!rows.length"
      :description="emptyText"
      :image-size="60"
    />

    <el-table
      v-else
      :data="pageRows"
      size="small"
      class="property-table__grid"
      row-key="id"
      @sort-change="onSortChange"
    >
      <el-table-column label="物件" min-width="180">
        <template #default="{ row }">
          <div class="property-table__name">
            <span>{{ row.name }}</span>
            <!--
              评价徽标 + 行内两秒快记（v3.60.32）。
              ⚠️ 徽标真源在好恶物档案馆，这里**只读**：本模块不加「是不是好东西」字段。
              🔴 「状况」与「评价」是两把正交的尺子：状况正常的东西可以是 👎
                 （型号选错了），状况坏了的东西仍可以是 👍（用了 12 年，值了）。
            -->
            <TreasureQuickMark
              kind="property"
              :target-id="row.id"
              :name="row.name"
              :badge="row.treasure_badge"
              :record-id="row.treasure_record_id"
              :suggest-category="row.treasure_suggest_category"
              :condition="row.condition"
              @saved="emit('treasure-saved')"
            />
          </div>
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

    <!--
      分页 —— 常量与判据走 `utils/survivalPaging.ts`（单一实现）。

      🔴 显示条件 `shouldShowPager(rows.length)` 的判据是「**存在**能让它分页的
         每页条数」、**不是**「当前每页条数下有多页」：写成后者，用户选一次
         「100 条/页」之后 `78 > 100` 为假 ⇒ 分页栏**连同每页条数选择器一起消失**，
         他再也调不回 20 —— 而「选 100」是「一屏看全部」的正常出口，不是误操作。
         **出口不能自己关掉自己。**

      ⚠️ `total` 传的是**全量结果数**（`rows.length`），与 `countLabel` 同源；
         传 `pageRows.length` 会让「第 2 页」根本不存在。

      ⚠️ 分页状态（页码 / 每页条数）**刻意不持久化**：它是查看态、不是数据。
         切到「类别维护」页签再回来由 `v-show` 保住即可（同筛选的处置）。
    -->
    <div v-if="shouldShowPager(rows.length)" class="property-table__pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="PAGE_SIZE_OPTIONS"
        :total="rows.length"
        size="small"
        layout="prev, pager, next, sizes"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { usePropertyStore } from '../../stores/propertyStore'
import {
  amountSortHint, formatMoneyOrDash, formatOverdue, formatUsedVsPlanned,
  formatZeroReason, sortItemsByAmount,
} from '../../utils/propertyFormat'
import type {
  AmountSortOrder,
} from '../../utils/propertyFormat'
// 分页常量与判据 —— 与生存资源那四个列表**同一份**（唯一实现）。
// ⚠️ 文件名带 `survival` 是历史（它出生在那一轮），但它服务的是整个 wealth
//    模块的列表；改名要动四个生存组件的 import，属无谓涟漪。
import {
  DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, pageCountOf, pageSlice, shouldShowPager,
} from '../../utils/survivalPaging'
import type { PropertyItem, PropertyOption } from '../../types/propertyTypes'
import TreasureQuickMark from '../common/TreasureQuickMark.vue'

const props = defineProps<{
  /** 全部物件（未筛选）—— 筛选与排序都在这个组件里做 */
  items: PropertyItem[]
}>()

const emit = defineEmits<{
  edit: [id: number]
  delete: [id: number]
  /** 行内快记写成功 ⇒ 父组件刷新列表（徽标要立刻变实色） */
  'treasure-saved': []
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

// ─── 分页（v3.60.35） ───
//
// ⚠️ 先看清 `rows`：它是**全量**结果（先筛再排）。分页只在它之上切一段喂给表格，
//    计数 / 空态 / 排序判据一律仍读 `rows` —— 见文件头判据 ①。
// ⚠️ 下面两个是**纯查看态**：不写 store、不落 URL。切页签由 `v-show` 保住即可。

/** 当前页（1 起） */
const page = ref(1)

/** 每页条数 —— 用户可调；选 100 即等于「不分页」（从第 1 件看到最后一件的出口） */
const pageSize = ref(DEFAULT_PAGE_SIZE)

/** 总页数（至少 1 —— 「一页都没有」不是一个可展示的状态） */
const pageCount = computed(() => pageCountOf(rows.value.length, pageSize.value))

/**
 * 当前页的行 —— 喂给 `el-table` 的**唯一**数据源。
 *
 * 🔴 切片必须发生在**排序之后**（`rows` 已经排好全量）：反过来只排当前页，
 *    而表头箭头照常高亮 —— 看不出错（文件头判据 ②）。
 */
const pageRows = computed<PropertyItem[]>(() => {
  const [start, end] = pageSlice(page.value, pageSize.value)
  return rows.value.slice(start, end)
})

/**
 * 件数标签 —— 有筛选时把**被筛掉的**也念出来。
 *
 * ⚠️ 原先只写「共 N 件」（N = 筛选结果数）：筛剩 2 件时显示「共 2 件」，
 *    配上分页栏的「1 页」，读作「我库里只有 2 件家当」—— 而实际是条件把
 *    另外 76 件挡住了。这是分页的配套（同生存资源清单的 `countLabel`）。
 */
const countLabel = computed(() => {
  const total = props.items.length
  const shown = rows.value.length
  return shown === total ? `共 ${total} 件` : `筛出 ${shown} / 共 ${total} 件`
})

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

/**
 * 筛选一变就回第 1 页。
 *
 * ⚠️ 这四项是 `defineModel` 的 ref（真值由父组件持有 —— 四卡点击要能直接改
 *    「状态」这一项），watch 它们与 watch 本地 ref 同样有效。
 * ⚠️ **不需要 `deep`**：四个都是字符串 / 数字。生存清单那边要 `deep: true`
 *    是因为它的筛选项里有**原地增删的数组**（`.push` / `.splice` 不换引用，
 *    非深度 watch 不触发）—— 这里没有数组，照抄 `deep` 只会掩盖将来真需要它的那天。
 * ⚠️ 不动 `sortOrder`：排序是「我想怎么看」、筛选是「我要看哪些」；
 *    筛一次就把排序方向清掉，等于每次都要重排一遍。
 */
watch([search, category, status, condition], () => {
  page.value = 1
})

/**
 * 结果变少导致当前页越界 ⇒ 拉回最后一页。
 *
 * 上面那条 watch 覆盖了「筛完只剩 1 页」，但**删物件 / store 刷新**不经过筛选，
 * 也会让总页数变小 —— 那条路不能漏（否则停在空页上，读作「列表空了」）。
 */
watch(pageCount, (total) => {
  if (page.value > total) page.value = total
})
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
  display: flex;
  align-items: center;
  gap: 6px;
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
/* 与生存资源四个列表同款（居中 + 上方 10px）—— 同一模块里的分页栏不该长得不一样 */
.property-table__pagination {
  display: flex;
  justify-content: center;
  margin-top: 10px;
}
</style>
