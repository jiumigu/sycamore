<!--
  物品清单 · 跨类别台账（v3.59.3；v3.60.2 成为**唯一的挑选入口**）

  这个面板回答的是**第三个问题**：我到底有哪些东西。
  一期二期都只给「按类别摊开」的视图 —— 想知道「我手上所有东西」
  得一个个 tab 点过去，而盘点时恰恰需要一份**不分类的总账**。

  四件事在这里合并：

  ① **清单**：跨类别的全量物品，能搜、能筛、能改、能删。
     编辑必须带上物品**自己**的类别 —— 不能沿用当前 tab 的类别：
     物品「卫生巾」在「用」这一类里，而当前 tab 可能停在「吃」，
     传错了会让弹窗按错类别的消耗模式显隐字段（配餐类根本不显示单件天数）。
  ② **挑要盘的（v3.60.2 起是唯一入口）**：勾选 → 「盘点选中的 N 件」
     带着这批 id 打开盘点弹窗。盘点弹窗里那一份**全量表格已经撤掉**了 ——
     挑选只在筛得动的地方做一次（见设计稿 §五 岔路口 1）。
  ③ **单件盘点**：每行一个「盘一下」→ 只对这一件填一个数。
     实测用法是「一次盘一两件」（7 天 6 次、共 8 行），
     而在此之前想改一件的数量，得走「编辑物品」（那是改主数据）或翻 43 行。
  ④ **随时间变的列**（上次盘点 / 该不该盘 / 是否低于补货线）**一律取自工作表**，
     不从 `items` 里自己判 —— 「没设周期就不催」这条规则在后端，
     在这里重写一遍迟早会漏，然后所有物品一起标红。

  ══════════════════════════════════════════════════════════════
  🔴 2026-09-29：「勾上该盘的 N 件」为什么过去永远是灰的
  ══════════════════════════════════════════════════════════════

  `stocktake_due` 的判据是「设了盘点周期、且距上次盘点已达到这个周期」。
  实测 43 件物品里 **0 件**设了周期 ⇒ 恒 false ⇒ 那枚按钮**永远是灰的**，
  批量入口实际上不存在，而它旁边一个字的解释都没有 —— 用户看到的是
  「按钮坏了」。

  根因不是判据错（把「从未盘过」也算该盘会让 43 件全标红 = 没有标），
  而是那个字段在问一个用户答不上来的问题：「牛奶，多久该盘一次？」
  同一个弹窗里的「补货线」有 5 件填了，因为那个问题有答案。

  ⇒ 处置：**另加一条不依赖任何配置的批量入口** ——「勾上最久没盘的前 N 件」，
    并在原按钮位置**说出为什么没有「该盘的」**（恒空必须被解释）。

  ⚠️ 天数是推导值、不是隐私项，**不掩码**（同二期快照面板的判据）。
     物品备注是自由文本，才走 `maskFreeText`。
-->
<template>
  <div class="survival-ledger">
    <div class="survival-ledger__head">
      <div class="survival-ledger__title-wrap">
        <span class="survival-ledger__title">物品清单</span>
        <span class="survival-ledger__subtitle">
          跨类别的全量台账 —— 勾选要盘的，再开盘点
        </span>
      </div>
      <div class="survival-ledger__actions">
        <el-button
          size="small"
          type="primary"
          :disabled="!selectedIds.length"
          @click="emit('stocktake', [...selectedIds])"
        >
          盘点选中的 {{ selectedIds.length }} 件
        </el-button>
        <el-button size="small" type="primary" plain @click="emit('new-item', categoryFilter ?? undefined)">
          <el-icon><Plus /></el-icon>新增物品
        </el-button>
      </div>
    </div>

    <div class="survival-ledger__filters">
      <el-input
        v-model="keyword"
        size="small"
        placeholder="搜物品名"
        clearable
        class="survival-ledger__search"
      />
      <el-select
        v-model="categoryFilter"
        size="small"
        clearable
        placeholder="全部类别"
        class="survival-ledger__select"
      >
        <el-option
          v-for="category in store.categories"
          :key="category.id"
          :label="category.name"
          :value="category.id"
        />
      </el-select>
      <el-select
        v-model="lifeModeFilter"
        size="small"
        clearable
        placeholder="计量口径"
        class="survival-ledger__select"
      >
        <el-option label="按次" value="cycle" />
        <el-option label="按天" value="day" />
        <el-option label="未填" value="none" />
      </el-select>
      <el-checkbox v-model="onlyDue">只看该盘的</el-checkbox>
      <el-checkbox v-model="onlyRestock">只看该补货的</el-checkbox>
      <span class="survival-ledger__count">共 {{ rows.length }} 件</span>
    </div>

    <!-- 批量挑件：两条路，一条不依赖任何配置 -->
    <div class="survival-ledger__pick">
      <span class="survival-ledger__pick-label">批量挑：</span>
      <el-button
        link
        size="small"
        type="primary"
        :disabled="!rows.length"
        @click="selectStalest"
      >
        勾上最久没盘的前 {{ STALEST_PICK_COUNT }} 件
      </el-button>
      <el-button
        v-if="dueRows.length"
        link
        size="small"
        type="primary"
        @click="selectDue"
      >
        勾上结果里的 {{ dueRows.length }} 件应盘项
      </el-button>
      <!--
        ⚠️ 这段说明是**必须的**、不是装饰：
           没有它，用户看到的就是一枚静默灰掉的按钮（见文件头）。
      -->
      <span v-else class="survival-ledger__pick-hint">{{ noDueHint }}</span>
    </div>

    <el-empty
      v-if="!rows.length"
      description="没有符合条件的物品 —— 换个筛选条件，或者先新增物品"
      :image-size="60"
    />

    <el-table
      v-else
      :data="rows"
      size="small"
      class="survival-ledger__table"
      row-key="id"
      @row-click="toggleRow"
    >
      <el-table-column width="46">
        <template #default="{ row }">
          <el-checkbox
            :model-value="selectedIds.includes(row.id)"
            @click.stop
            @change="toggleRow(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="物品" min-width="140">
        <template #default="{ row }">
          <span class="survival-ledger__name">{{ row.name }}</span>
          <span v-if="row.notes" class="survival-ledger__notes">
            {{ maskFreeText(row.notes) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="category_name" label="类别" width="90" />
      <el-table-column label="数量" width="110">
        <template #default="{ row }">
          {{ formatQuantity(row.quantity, row.unit_name) }}
        </template>
      </el-table-column>
      <el-table-column label="计量口径" min-width="160">
        <template #default="{ row }">
          <el-tag v-if="row.life_mode === 'cycle'" size="small" effect="plain">按次</el-tag>
          <el-tag v-else-if="row.life_mode === 'day'" size="small" effect="plain">按天</el-tag>
          <el-tag v-else size="small" type="info" effect="plain">未填</el-tag>
          <span v-if="row.life_mode === 'cycle'" class="survival-ledger__cycle">
            {{ formatUseCycle(row.use_cycle_num, row.use_cycle_unit_label, row.use_times) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="一份可用" width="100">
        <template #default="{ row }">
          {{ formatDays(row.days_per_unit_effective, '未填') }}
        </template>
      </el-table-column>
      <!--
        可排序：升序 = 最近盘过的在前，降序 = 最久没盘的在前（「从未盘点」恒排最前）。
        ⚠️ 排序只影响**看的顺序**，不影响「勾上最久没盘的前 N 件」——
           那个挑件判据自己排一次，与当前显示顺序无关。
      -->
      <el-table-column
        label="上次盘点"
        width="150"
        prop="days_since_stocktake"
        sortable
        :sort-method="sortByStaleness"
      >
        <template #default="{ row }">
          {{ formatLastStocktake(row.last_stocktake_date, row.days_since_stocktake) }}
        </template>
      </el-table-column>
      <el-table-column label="提醒" min-width="150">
        <template #default="{ row }">
          <el-tag v-if="row.stocktake_due" type="warning" size="small" effect="plain">
            该盘了
          </el-tag>
          <el-tag v-if="row.below_threshold" type="danger" size="small" effect="plain">
            该补货
          </el-tag>
          <el-tag v-if="row.status === 'expired'" type="info" size="small" effect="plain">
            已过期
          </el-tag>
          <span
            v-if="!row.stocktake_due && !row.below_threshold && row.status !== 'expired'"
            class="survival-ledger__ok"
          >—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <!-- stop：行点击是勾选，点这些按钮不该顺带把它勾上 -->
          <!-- 🔴 消耗登记长在**物品上**（v3.60.18）：用户想「我吃了一罐」时，
               眼睛盯的是这一行，不是流水页 —— 流水页只负责「查」，不放登记按钮。
               两个动作都只填**一个数**（变化量），「还剩几件」由服务端算。 -->
          <el-button link size="small" @click.stop="emit('use-up', row.id)">
            用掉
          </el-button>
          <el-button link size="small" @click.stop="emit('restock', row.id)">
            入库
          </el-button>
          <el-button link size="small" @click.stop="emit('stocktake-one', row.id)">
            盘一下
          </el-button>
          <el-button link size="small" @click.stop="emit('edit-item', row.id, row.category_id)">
            编辑
          </el-button>
          <el-button link size="small" type="danger" @click.stop="emit('delete-item', row.id)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import {
  formatDays, formatLastStocktake, formatQuantity, formatUseCycle,
} from '../../utils/survivalFormat'
import {
  STALEST_PICK_COUNT, hasAnyCycle, pickStalestIds,
} from '../../utils/survivalStocktake'
import type { SurvivalItem } from '../../types/survivalTypes'

const emit = defineEmits<{
  /**
   * 带上清单**当前筛的类别**作为新增默认值。
   *
   * 按「穿」筛着列表点「新增物品」，新增的默认就该是「穿」——
   * 弹窗虽然能改类别，但默认值应该是用户眼前这份列表的那一类。
   */
  'new-item': [categoryId?: number]
  /** 编辑时必须把物品自己的类别带出去 —— 见文件头 ① */
  'edit-item': [id: number, categoryId: number]
  'delete-item': [id: number]
  stocktake: [itemIds: number[]]
  /** 单件盘点（v3.60.2）—— 只盘这一件，不再翻全量弹窗 */
  'stocktake-one': [itemId: number]
  /** 用掉 / 入库（v3.60.18）—— 变更量登记，由父级弹极简浮层 */
  'use-up': [itemId: number]
  restock: [itemId: number]
}>()

const store = useSurvivalStore()
const { maskFreeText } = usePrivacyMask()

/** 清单行 = 主数据 + 工作表里那几列随时间变的字段 */
interface LedgerRow extends SurvivalItem {
  /**
   * ⚠️ 与盘点工作表**统一键名**的别名（值 = `id`）。
   *    清单的行来自 `SurvivalItem`（主键叫 `id`），工作表的行叫 `item_id` ——
   *    加这一个字段，两种行模型就能共用同一份盘点判据
   *    （`utils/survivalStocktake.ts`），不必先统一模型。
   */
  item_id: number
  last_stocktake_date: string | null
  days_since_stocktake: number | null
  stocktake_due: boolean
  stocktake_cycle_days: number | null
  below_threshold: boolean
}

const keyword = ref('')
const categoryFilter = ref<number | null>(null)
const lifeModeFilter = ref<string>('')
const onlyDue = ref(false)
const onlyRestock = ref(false)
const selectedIds = ref<number[]>([])

/**
 * 工作表按物品 id 索引。
 *
 * ⚠️ 它可能**不含**某件物品（没建单位、单位不可比之类），
 *    那样这些列就整片落空 —— 所以每处都必须容 null，
 *    不能写成 `worksheetMap[row.id].days_since_stocktake`。
 */
const worksheetMap = computed<Record<number, {
  last_stocktake_date: string | null
  days_since_stocktake: number | null
  stocktake_due: boolean
  stocktake_cycle_days: number | null
  below_threshold: boolean
}>>(() => {
  const map: Record<number, {
    last_stocktake_date: string | null
    days_since_stocktake: number | null
    stocktake_due: boolean
    stocktake_cycle_days: number | null
    below_threshold: boolean
  }> = {}
  for (const row of store.worksheet) {
    map[row.item_id] = {
      last_stocktake_date: row.last_stocktake_date,
      days_since_stocktake: row.days_since_stocktake,
      stocktake_due: row.stocktake_due,
      stocktake_cycle_days: row.stocktake_cycle_days,
      below_threshold: row.below_threshold,
    }
  }
  return map
})

const allRows = computed<LedgerRow[]>(() =>
  store.items.map((item) => ({
    ...item,
    item_id: item.id,
    last_stocktake_date: worksheetMap.value[item.id]?.last_stocktake_date ?? null,
    days_since_stocktake: worksheetMap.value[item.id]?.days_since_stocktake ?? null,
    stocktake_due: worksheetMap.value[item.id]?.stocktake_due ?? false,
    stocktake_cycle_days: worksheetMap.value[item.id]?.stocktake_cycle_days ?? null,
    below_threshold: worksheetMap.value[item.id]?.below_threshold ?? false,
  })),
)

/** 先筛「该盘的」，才有「勾上应盘项」这个动作的落点 */
const dueRows = computed(() => allRows.value.filter((row) => row.stocktake_due))

const rows = computed<LedgerRow[]>(() => {
  const text = keyword.value.trim().toLowerCase()
  return allRows.value.filter((row) => {
    if (text && !row.name.toLowerCase().includes(text)) return false
    if (categoryFilter.value !== null && row.category_id !== categoryFilter.value) return false
    if (lifeModeFilter.value === 'none' && row.life_mode) return false
    if (lifeModeFilter.value && lifeModeFilter.value !== 'none' && row.life_mode !== lifeModeFilter.value) {
      return false
    }
    if (onlyDue.value && !row.stocktake_due) return false
    if (onlyRestock.value && !row.below_threshold) return false
    return true
  })
})

/**
 * 「为什么没有该盘的」—— 恒空必须被解释。
 *
 * 两种情况要说不同的话：**没设过周期**（配置问题，用户能去补）
 * 与**设了但都没到期**（正常状态，什么都不用做）。
 * 合成一句「暂无」就分不出该补哪个。
 */
const noDueHint = computed(() => {
  if (!allRows.value.length) return ''
  if (!hasAnyCycle(allRows.value)) {
    return '没有一件设过盘点周期，所以没有「该盘的」（设了才会催）—— 用「最久没盘」挑即可'
  }
  return '设过周期的物品里暂时没有到期的 —— 也可以按「最久没盘」挑'
})

function toggleRow(row: { id: number }) {
  const index = selectedIds.value.indexOf(row.id)
  if (index >= 0) selectedIds.value.splice(index, 1)
  else selectedIds.value.push(row.id)
}

/** 只在**当前筛选结果**里勾 —— 看不见的行被悄悄勾上是说不清的 */
function selectDue() {
  for (const row of dueRows.value) {
    if (!selectedIds.value.includes(row.id)) selectedIds.value.push(row.id)
  }
}

/**
 * 零配置的批量挑件：勾上**当前筛选结果**里最久没盘的前 N 件。
 *
 * 判据在 `utils/survivalStocktake.ts`（单一实现）——
 * 与「该盘了」是两件事，见那个模块的说明。
 */
function selectStalest() {
  for (const id of pickStalestIds(rows.value)) {
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  }
}

/**
 * 「上次盘点」列的排序：升序 = 最近盘过的在前，降序 = 最久没盘的在前。
 *
 * ⚠️ `null`（从未盘点）当作正无穷 —— 它在降序里排最前，而那是**对的**：
 *    从未数过的，就是离上次盘点最远的。把它当 0 会把它排到最后。
 */
function sortByStaleness(a: LedgerRow, b: LedgerRow): number {
  const av = a.days_since_stocktake === null ? Number.POSITIVE_INFINITY : a.days_since_stocktake
  const bv = b.days_since_stocktake === null ? Number.POSITIVE_INFINITY : b.days_since_stocktake
  return av - bv
}
</script>

<style scoped>
.survival-ledger {
  margin-top: 16px;
  padding: 12px 14px 4px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
}
.survival-ledger__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.survival-ledger__title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.survival-ledger__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.survival-ledger__subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-ledger__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.survival-ledger__filters {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.survival-ledger__pick {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.survival-ledger__pick-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-ledger__pick-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-ledger__search {
  width: 180px;
}
.survival-ledger__select {
  width: 130px;
}
.survival-ledger__count {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-ledger__table {
  width: 100%;
}
.survival-ledger__name {
  font-weight: 600;
}
.survival-ledger__notes {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-ledger__cycle {
  margin-left: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-ledger__ok {
  color: var(--el-text-color-placeholder);
}
</style>
