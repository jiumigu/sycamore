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

  ══════════════════════════════════════════════════════════════
  🔴 2026-10-10：检索区重做（物品过 50 件之后「翻不动了」）
  ══════════════════════════════════════════════════════════════

  三类检索需求，性质不同、分开摆：

    ① 找具名的东西   → 关键词（**名字 + 备注**）
    ② 缩到某几类     → 类别**多选** + 计量口径
    ③ 找出要动手的   → 「待办」chip 组（该补货 / 已过期 / 该盘了 / 从未盘点）

  三条判据（不是风格偏好 —— 写错会给出「看着合理」的错结果）：

  1. **维度内 OR、维度间 AND**。待办勾两样 = 「这两类问题我都想看」⇒ 并集；
     类别 × 待办 × 口径 × 关键词之间求交。
     若待办也写成 AND，「该补货 + 已过期」会恒空（一件东西同时占两样极少），
     用户会得出「筛选坏了」。

  2. **chip 上的计数必须在「分面基集」上算** —— 已应用其它条件、
     **未应用待办**的集合。用全量算：筛了「吃」之后 chip 仍显示全量的 5、
     点下去只剩 2，两个数同屏却对不上（静默不一致）。
     用「含待办」的结果集算：勾了「该补货」，「已过期」的数字会跟着缩水 ——
     那答的是「还需多少」，不是「有多少」。

  3. **0 值的 chip 要解释自己**（沿用「恒灰控件必须解释自己」）：
     「该盘了 0」不是「没有要盘的」，是「没有一件设过盘点周期」——
     配置问题，用户能去补。tooltip 说的是后者。

  ⚠️ **「已过期」此前在表格里有标签、却筛不出来** —— 看得见、筛不出，
     是最刺眼的一种不一致（本次补上）。
  ⚠️ 「从未盘点」的判据见 `isNeverStocktaken`：**不能只判 null**。
  ⚠️ 顺带修掉一处从未显形的错：`dueRows` 取的是全量，而按钮文案写「结果里的」。
     当时全库 0 件设过盘点周期 ⇒ `stocktake_due` 恒 false ⇒ 一直没显形。
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
  🔴 2026-10-10（同日）：加分页 —— 50 件一屏放不下
  ══════════════════════════════════════════════════════════════

  实测 50 件（吃 15 / 用 24 / 穿 10 / 数字 1），而单页只看得到 13~15 行
  ⇒ 要滚三屏多。四条判据，写错任一条都是**静默**的：

  1. **分页只切「显示」**。`rows`（结果集）、`dueRows`、`taskCounts`、`countLabel`
     一律仍是全量 —— 一加分页就把它们换成「当前页」，统计卡会静默变成
     「本页的数」（同 TECH-NOTES §57 那一族：分页一上，所有「从列表取全量」
     的地方都会失效）。切片只发生在 `pageRows` 这一处。

  2. **先排全量、再切片**。表头排序必须 `sortable="custom"` + 自己排
     `sortedRows` —— 用 el-table 自带的排序，它排的是**传进去的那一页**，
     于是「按最久没盘排」只在本页内成立、翻页后又是乱的，
     而表头箭头**照常高亮**（界面上看不出错）。

  3. **筛选一变回第 1 页**。否则「筛剩 3 件、却停在第 3 页」= 一张空表，
     读作「筛选坏了」。同理，总页数变小（删物品 / 刷列表）时把当前页拉回范围内。

  4. **勾选跨页保留，并且要说出来**。勾选是「我挑好了要盘的」，不因翻页
     或改筛选而丢（同 `resetFilters` 的判据）；批量挑件的作用域仍是**全部结果**
     （缩到当前页就没法「一次挑 10 件去盘」）—— 代价是它会勾上看不见的行，
     所以 `selectionHint` 必须把分布念出来（本页几件 / 其它页几件 /
     被筛掉几件，且被筛掉的**仍会盘点**）。

  5. **分页栏的显示条件是「存在能让它分页的每页件数」**（`shouldShowPager(...)`），
     而不是「当前每页件数下有多页」。写成后者的话，用户把「100 条/页」选上，
     分页栏会**整个消失** ⇒ 他再也调不回 20（除非物品继续增长）。
     ⚠️ 选 100 是「一屏看全部」的正常用法、不是误操作 —— 出口不能自己关掉自己。
     📌 常量与这条判据已收进 `utils/survivalPaging.ts`（v3.60.26）：
        本模块**四个**列表共用一份，组件里不再各留一套。

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
        <el-button size="small" type="primary" plain @click="emit('new-item', newItemCategory)">
          <el-icon><Plus /></el-icon>新增物品
        </el-button>
      </div>
    </div>

    <!-- 第一行 · 找东西：关键词（名字 + 备注）+ 类别（多选）+ 计量口径 -->
    <div class="survival-ledger__filters">
      <el-input
        v-model="keyword"
        size="small"
        placeholder="搜物品名 / 备注"
        clearable
        class="survival-ledger__search"
      />
      <!-- 多选：单选的年代想看「吃 + 用」得切两次，而筛完「吃」再看「用」，
           前一个条件被顶掉 —— 组合不起来 -->
      <el-select
        v-model="categoryFilter"
        size="small"
        multiple
        collapse-tags
        collapse-tags-tooltip
        clearable
        placeholder="全部类别"
        class="survival-ledger__select survival-ledger__select--multi"
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
        <el-option label="见配方" value="recipe" />
        <el-option label="未填" value="none" />
      </el-select>
      <span class="survival-ledger__count">{{ countLabel }}</span>
      <el-button v-if="hasFilter" link size="small" type="primary" @click="resetFilters">
        清除筛选
      </el-button>
    </div>

    <!--
      第二行 · 只看要处理的。🔴 维度内 OR、维度间 AND（文件头判据 1）；
      chip 上的数字是**分面计数**（判据 2）—— 不筛也知道各有多少件要处理。
    -->
    <div class="survival-ledger__tasks">
      <span class="survival-ledger__tasks-label">只看要处理的：</span>
      <template v-for="task in TASK_FILTERS" :key="task">
        <!-- 0 值 chip 必须解释自己（判据 3）—— 目前只有「该盘了」有可说的原因 -->
        <el-tooltip
          :content="task === 'due' ? noDueHint : ''"
          :disabled="task !== 'due' || taskCounts.due > 0"
          placement="top"
        >
          <span class="survival-ledger__chip-wrap">
            <!-- 已勾选的**永远可点**：计数归零时要能把它取消掉，不能连出口一起灰掉 -->
            <el-check-tag
              :checked="taskFilters.includes(task)"
              :disabled="taskCounts[task] === 0 && !taskFilters.includes(task)"
              @change="toggleTask(task)"
            >
              {{ TASK_LABELS[task] }}
              <span class="survival-ledger__chip-count">{{ taskCounts[task] }}</span>
            </el-check-tag>
          </span>
        </el-tooltip>
      </template>
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
      <!--
        已勾选项的分布 —— 分页之后才可能出现「跨页」这一种处境，
        见文件头 2026-10-10 判据 4。只在有跨页 / 有被筛掉时渲染。
      -->
      <span v-if="selectionHint" class="survival-ledger__selection">{{ selectionHint }}</span>
    </div>

    <el-empty
      v-if="!rows.length"
      description="没有符合条件的物品 —— 换个筛选条件，或者先新增物品"
      :image-size="60"
    />

    <el-table
      v-else
      :data="pageRows"
      size="small"
      class="survival-ledger__table"
      row-key="id"
      @row-click="toggleRow"
      @sort-change="onSortChange"
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
          <!--
            🔴 配餐类的果腹/调味/饮水：口径**不在这件物品上**，在配方里。
               原先这里只判 `life_mode`，于是这些物品一律显示「未填」——
               而「未填」在别处**一律意味着「缺配置、去补」**（明细页的
               「问题」列、缺口对账的 unknown），等于把「口径在别处」
               说成了「你没填」。用户顺着这一列找原因，会得出
               「快照不可信是因为没填计量口径」这种**错**的结论
               （实测真因是孤儿食材，与口径无关）。
          -->
          <el-tooltip
            v-if="row.uses_recipe"
            content="时长由配方里的「每餐用量」决定，不在这件物品上填"
            placement="top"
          >
            <el-tag size="small" effect="plain">见配方</el-tag>
          </el-tooltip>
          <el-tag v-else-if="row.life_mode === 'cycle'" size="small" effect="plain">按次</el-tag>
          <el-tag v-else-if="row.life_mode === 'day'" size="small" effect="plain">按天</el-tag>
          <el-tag v-else size="small" type="info" effect="plain">未填</el-tag>
          <span v-if="row.life_mode === 'cycle'" class="survival-ledger__cycle">
            {{ formatUseCycle(row.use_cycle_num, row.use_cycle_unit_label, row.use_times) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="一份可用" width="100">
        <template #default="{ row }">
          <!-- 同上一列：口径在配方里时，这里也说「见配方」而不是「未填」 -->
          <span v-if="row.uses_recipe" class="survival-ledger__by-recipe">见配方</span>
          <template v-else>{{ formatDays(row.days_per_unit_effective, '未填') }}</template>
        </template>
      </el-table-column>
      <!--
        可排序：升序 = 最近盘过的在前，降序 = 最久没盘的在前（「从未盘点」恒排最前）。
        ⚠️ 排序只影响**看的顺序**，不影响「勾上最久没盘的前 N 件」——
           那个挑件判据自己排一次，与当前显示顺序无关。
        🔴 `sortable="custom"`：el-table 在 custom 模式下**不排数据**，只发事件；
           真正排序的是 `sortedRows`（先排全量、再切片）。用自带排序的话，
           它排的是传进来那一页 ⇒ 只在本页内有序，而箭头照常高亮（看不出错）。
      -->
      <el-table-column
        label="上次盘点"
        width="150"
        prop="days_since_stocktake"
        sortable="custom"
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

    <!--
      分页 —— 判据见文件头 2026-10-10。每页件数选 100 即等于「不分页」，
      这是「从第 1 件看到最后一件」的出口。
      🔴 显示条件走 `shouldShowPager(rows.length)`（`utils/survivalPaging.ts` 单一实现），
         判据是「**存在**能让它分页的每页条数」、**不是**「当前每页条数下有多页」：
         后者会在选上「100 条/页」之后把分页栏整个藏掉，用户再也调不回 20
         —— 而选 100 是正常用法，不是误操作。
      ⚠️ 本模块四个列表共用这一套常量与判据（v3.60.26 起），组件里不再各留一份。
    -->
    <div v-if="shouldShowPager(rows.length)" class="survival-ledger__pagination">
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
import { Plus } from '@element-plus/icons-vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import {
  formatDays, formatLastStocktake, formatQuantity, formatUseCycle,
} from '../../utils/survivalFormat'
import {
  STALEST_PICK_COUNT, hasAnyCycle, pickStalestIds, sortRowsByStaleness,
} from '../../utils/survivalStocktake'
import {
  DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, pageCountOf, pageSlice, shouldShowPager,
} from '../../utils/survivalPaging'
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
  /**
   * 这件物品**在盘点工作表里**（v3.60.23）。
   *
   * ⚠️ 存在的唯一理由是给「从未盘点」做判据（见 `isNeverStocktaken`）：
   *    `days_since_stocktake === null` 同时意味着「工作表里没这件」，
   *    只判它会把「取不到」说成「从未盘过」。
   */
  in_worksheet: boolean
  last_stocktake_date: string | null
  days_since_stocktake: number | null
  stocktake_due: boolean
  stocktake_cycle_days: number | null
  below_threshold: boolean
}

/** 待办筛选项。数组顺序即界面顺序 */
const TASK_FILTERS = ['restock', 'expired', 'due', 'never'] as const
type TaskFilter = (typeof TASK_FILTERS)[number]
/** 标签真源。放这里而不是模板里内联三元 —— 模板里散着一串字面量，改文案要翻三处 */
const TASK_LABELS: Record<TaskFilter, string> = {
  restock: '该补货',
  expired: '已过期',
  due: '该盘了',
  never: '从未盘点',
}

const keyword = ref('')
/**
 * 类别**多选**（v3.60.23）。
 *
 * ⚠️ 初值与 `clearable` 清空后都是 `[]`，**不是 null** ——
 *    多选模式下 `el-select` 只会给数组，写 `null` 会在 `.includes` 上炸。
 */
const categoryFilter = ref<number[]>([])
const lifeModeFilter = ref<string>('')
/** 待办维度多选；维度内取并集、与其它维度取交，见 `matchesTask` */
const taskFilters = ref<TaskFilter[]>([])
const selectedIds = ref<number[]>([])

/**
 * 分页状态（v3.60.24）。
 *
 * ⚠️ 筛选一变就回第 1 页（watch 见文件末）—— 否则「筛剩 3 件、却停在第 3 页」
 *    会看到一张**空表**，读作「筛选坏了」。
 * ⚠️ 每页件数用户可调：选 100 就等于「不分页」，这是「从第 1 件看到最后一件」
 *    的出口。
 */
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)

/**
 * 「上次盘点」列的排序方向（v3.60.24）。
 *
 * ⚠️ `null` = 不排序、保持 `store.items` 的原序（后端给的默认序）——
 *    与 el-table 表头的箭头状态同源，否则会出现「箭头指着升序、数据没动」。
 */
const stalenessSort = ref<'asc' | 'desc' | null>(null)

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
    // ⚠️ 判「在不在表里」用 `!== undefined`，不能用 `?.x ?? null` ——
    //    后者把「行不在」与「行在但值为空」抹成同一个结果
    in_worksheet: worksheetMap.value[item.id] !== undefined,
    last_stocktake_date: worksheetMap.value[item.id]?.last_stocktake_date ?? null,
    days_since_stocktake: worksheetMap.value[item.id]?.days_since_stocktake ?? null,
    stocktake_due: worksheetMap.value[item.id]?.stocktake_due ?? false,
    stocktake_cycle_days: worksheetMap.value[item.id]?.stocktake_cycle_days ?? null,
    below_threshold: worksheetMap.value[item.id]?.below_threshold ?? false,
  })),
)

/**
 * 关键词匹配：**名字 + 备注**（v3.60.23）。
 *
 * 备注里写的常是定位信息（「放阳台柜」「到期前先用」），而它就在表格里
 * 显示着 —— 搜不到等于让人肉翻 50 行。
 *
 * ⚠️ 匹配的是**未掩码**的原文：掩码后只剩「阳***」，按它搜永远搜不到。
 *    隐私模式约束的是「别让旁人看见屏幕」，不是拒绝本人检索 ——
 *    但这确实意味着隐私模式下搜出来的那行看不出匹配在哪儿（既有矛盾，未动）。
 */
function matchesKeyword(row: LedgerRow, text: string): boolean {
  return (
    row.name.toLowerCase().includes(text)
    || (row.notes ?? '').toLowerCase().includes(text)
  )
}

/**
 * 「从未盘点」—— 🔴 **不能只判 `days_since_stocktake === null`**。
 *
 * 那个 null 有两个来源：
 *   ① 真的没盘过（工作表里有它、`last_stocktake_date` 为空）；
 *   ② 工作表里**根本没有它**（前端 `worksheetMap` 缺项，见上面的说明）。
 * 只判 null 会把 ② 也算成「从未盘点」—— 而显示层（`formatStocktakeGap`）
 * 把两种情况渲染成同一句话，所以这个区别**在界面上看不出来**，只能在这里守住。
 */
function isNeverStocktaken(row: LedgerRow): boolean {
  return row.in_worksheet && row.last_stocktake_date === null
}

/**
 * 一行是否命中某个待办项 —— **判据只在这里一份**。
 *
 * ⚠️ 「已过期」用的是 `status`，与表格「提醒」列那个标签同源：
 *    这里是补上「看得见却筛不出来」的那个缺口。
 */
function matchesTask(row: LedgerRow, task: TaskFilter): boolean {
  if (task === 'restock') return row.below_threshold
  if (task === 'expired') return row.status === 'expired'
  if (task === 'due') return row.stocktake_due
  return isNeverStocktaken(row)
}

/**
 * **分面基集**：已应用「关键词 / 类别 / 口径」、**未应用待办**的行。
 *
 * 待办的计数与筛选都从它派生 —— 见文件头判据 2（计数既不能用全量，
 * 也不能用含待办的结果集）。
 */
const baseRows = computed<LedgerRow[]>(() => {
  const text = keyword.value.trim().toLowerCase()
  return allRows.value.filter((row) => {
    if (text && !matchesKeyword(row, text)) return false
    if (categoryFilter.value.length && !categoryFilter.value.includes(row.category_id)) {
      return false
    }
    // ⚠️ 「未填」与「见配方」必须互斥：配餐类的 `life_mode` 也是 null，
    //    只判 life_mode 会让「未填」筛出一大堆配餐物品 —— 而那恰恰是
    //    本次要消除的那层误解（口径在配方里，不是没填）。
    if (lifeModeFilter.value === 'none') {
      if (row.life_mode || row.uses_recipe) return false
    } else if (lifeModeFilter.value === 'recipe') {
      if (!row.uses_recipe) return false
    } else if (lifeModeFilter.value && row.life_mode !== lifeModeFilter.value) {
      return false
    }
    return true
  })
})

/**
 * 各待办项的件数 —— 在**分面基集**上算（判据 2）。
 *
 * 勾了「该补货」之后，「已过期」的数字不会跟着缩水：
 * 它答的是「有多少」，不是「还需多少」。
 */
const taskCounts = computed<Record<TaskFilter, number>>(() => {
  const counts: Record<TaskFilter, number> = { restock: 0, expired: 0, due: 0, never: 0 }
  for (const row of baseRows.value) {
    for (const task of TASK_FILTERS) {
      if (matchesTask(row, task)) counts[task] += 1
    }
  }
  return counts
})

/** 结果集 = 基集 ∩ 待办（维度内取并集 —— 判据 1） */
const rows = computed<LedgerRow[]>(() => {
  if (!taskFilters.value.length) return baseRows.value
  return baseRows.value.filter((row) =>
    taskFilters.value.some((task) => matchesTask(row, task)),
  )
})

/**
 * 全量结果**排好序**的列表 —— `pageRows` 在它之上切片。
 *
 * 🔴 顺序要紧：**先排全量、再切片**。反过来（切片后排序）只排当前页，
 *    而表头箭头照常高亮 ⇒ 静默的错（文件头判据 2）。
 *
 * ⚠️ 排序判据复用 `sortRowsByStaleness`（`utils/survivalStocktake.ts` 单一实现）：
 *    它已经处理了「从未盘点（`null`）恒排最前」与「同天用 `item_id` 兜底」，
 *    在这里再写一份比较器就是第二份口径。
 */
const sortedRows = computed<LedgerRow[]>(() => {
  const direction = stalenessSort.value
  if (!direction) return rows.value
  return sortRowsByStaleness(rows.value, direction)
})

/** 总页数（至少 1 —— 「一页都没有」不是一个可展示的状态） */
const pageCount = computed(() => pageCountOf(rows.value.length, pageSize.value))

/** 当前页的行 —— 喂给 `el-table` 的**唯一**数据源 */
const pageRows = computed<LedgerRow[]>(() => {
  const [start, end] = pageSlice(page.value, pageSize.value)
  return sortedRows.value.slice(start, end)
})

/**
 * 已勾选项的分布（v3.60.24）—— **只在需要解释时**才有一句话。
 *
 * 分页之后，「已勾选」有三种处境：本页看得见 / 在其它页 / 被当前筛选挡掉。
 * 后两种用户**看不见**，但它们**都会被真的盘点**
 * （`emit('stocktake', [...selectedIds])` 与筛选、分页都无关）
 * ⇒ 不念出来就是「我只勾了 3 件，怎么去盘 10 件」。
 *
 * ⚠️ 只在「有跨页 / 有被筛掉」时返回内容：不出事就不加噪音
 *    （`盘点选中的 N 件` 按钮上已经有总数）。
 * ⚠️ 已删除物品的 id 仍在 `selectedIds` 里（改筛选 / 清筛选都不动勾选），
 *    它既不在 `rows` 也不在 `allRows` ⇒ 这里**刻意不计入**任何一段：
 *    那不是「被筛选隐藏」，是「这件东西没了」。既有行为，未动。
 */
const selectionHint = computed(() => {
  if (!selectedIds.value.length) return ''
  const onPage = new Set(pageRows.value.map((row) => row.id))
  const inResult = new Set(rows.value.map((row) => row.id))
  const existing = new Set(allRows.value.map((row) => row.id))
  let onPageCount = 0
  let offPageCount = 0
  let hiddenCount = 0
  for (const id of selectedIds.value) {
    if (!inResult.has(id)) {
      if (existing.has(id)) hiddenCount += 1
    } else if (onPage.has(id)) onPageCount += 1
    else offPageCount += 1
  }
  if (!offPageCount && !hiddenCount) return ''
  const bits = [`已勾选 ${selectedIds.value.length} 件 · 本页 ${onPageCount} 件`]
  if (offPageCount) bits.push(`其它页 ${offPageCount} 件`)
  if (hiddenCount) bits.push(`被筛选隐藏 ${hiddenCount} 件`)
  const text = bits.join(' · ')
  return hiddenCount ? `${text}（被隐藏的仍会盘点）` : text
})

/**
 * 当前**筛选结果**里的应盘项 —— 「勾上结果里的 N 件应盘项」的落点。
 *
 * ⚠️ 取的是**整个筛选结果**（不切片），**不是当前页** —— 分页只切显示，
 *    这个数答的是「结果里一共有多少该盘的」（同 `countLabel` / `taskCounts`）。
 *
 * ⚠️ 2026-10-10 修正：原先取的是 `allRows`（全量），而按钮文案写的是
 *    「结果里的」。当时全库 43 件里 0 件设过盘点周期 ⇒ `stocktake_due`
 *    恒 false ⇒ 这个不一致一直**没有显形**。现在待办 chip 能把该盘的
 *    筛出来了，再取全量就会「说 3 件、却勾上 8 件」。
 */
const dueRows = computed(() => rows.value.filter((row) => row.stocktake_due))

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

/** 有筛选时把「筛剩多少」也说出来 —— 只显示结果数，看不出被筛掉了多少 */
const countLabel = computed(() => {
  const total = allRows.value.length
  const shown = rows.value.length
  return shown === total ? `共 ${total} 件` : `筛出 ${shown} / 共 ${total} 件`
})

const hasFilter = computed(
  () =>
    !!keyword.value.trim()
    || categoryFilter.value.length > 0
    || !!lifeModeFilter.value
    || taskFilters.value.length > 0,
)

/**
 * 清空筛选 —— **不动勾选**。
 *
 * 勾选是「我挑好了要盘的」这个动作的结果，筛选只是看它的方式；
 * 清一次筛选就把挑好的丢掉，是让人从头挑一遍。
 */
function resetFilters() {
  keyword.value = ''
  categoryFilter.value = []
  lifeModeFilter.value = ''
  taskFilters.value = []
}

function toggleTask(task: TaskFilter) {
  const index = taskFilters.value.indexOf(task)
  if (index >= 0) taskFilters.value.splice(index, 1)
  else taskFilters.value.push(task)
}

/**
 * 新增物品的默认类别：**只在恰好筛了一个类别时**给。
 *
 * 筛了「吃 + 用」时替用户挑一个就是猜 —— 他可能正要加第三类。
 * 多选时留空，让弹窗走它自己的默认。
 */
const newItemCategory = computed(() =>
  categoryFilter.value.length === 1 ? categoryFilter.value[0] : undefined,
)

function toggleRow(row: { id: number }) {
  const index = selectedIds.value.indexOf(row.id)
  if (index >= 0) selectedIds.value.splice(index, 1)
  else selectedIds.value.push(row.id)
}

/**
 * 「勾上结果里的 N 件应盘项」—— 作用域是**全部筛选结果**，不是当前页。
 *
 * 🔴 分页之后它会勾到**看不见的行**（在其它页）。原先那条
 *    「看不见的行被悄悄勾上是说不清的」判据，解法是 `selectionHint`
 *    **把分布念出来**（本页几件 / 其它页几件），而不是把作用域缩到当前页 ——
 *    缩了之后「一次挑 N 件去盘」就做不到，而那正是这个按钮存在的理由。
 */
function selectDue() {
  for (const row of dueRows.value) {
    if (!selectedIds.value.includes(row.id)) selectedIds.value.push(row.id)
  }
}

/**
 * 零配置的批量挑件：勾上**全部筛选结果**里最久没盘的前 N 件。
 *
 * 判据在 `utils/survivalStocktake.ts`（单一实现）——
 * 与「该盘了」是两件事，见那个模块的说明。
 * ⚠️ 作用域同样是全量结果（可能跨页），分布由 `selectionHint` 念出来，
 *    理由见 `selectDue`。
 */
function selectStalest() {
  for (const id of pickStalestIds(rows.value)) {
    if (!selectedIds.value.includes(id)) selectedIds.value.push(id)
  }
}

/**
 * 表头点击 → 记下排序方向（v3.60.24）。
 *
 * ⚠️ element-plus 给的 `order` 是 `'ascending' | 'descending' | null`，
 *    与我们的 `'asc' | 'desc'` **不是一套字面量** —— 直接拿来存会**静默不排序**
 *    （箭头会动、列表不动）。
 * ⚠️ `sortable="custom"` 下 el-table 不排数据、只发这个事件；
 *    真正排序的是 `sortedRows`。
 */
function onSortChange(payload: { prop: string | null; order: string | null }) {
  if (payload.prop !== 'days_since_stocktake') return
  if (payload.order === 'ascending') stalenessSort.value = 'asc'
  else if (payload.order === 'descending') stalenessSort.value = 'desc'
  else stalenessSort.value = null
}

/**
 * 筛选一变就回第 1 页。
 *
 * ⚠️ `deep: true` 是**必需的**：`taskFilters` / `categoryFilter` 是**原地**
 *    增删元素的数组（`.push` / `.splice`），引用没换 ⇒ 非深度 watch 不触发
 *    ⇒「勾了待办 chip、结果只剩 3 件，却停在第 3 页」= 一张空表。
 * ⚠️ 不动 `selectedIds`：勾选是「我挑好了要盘的」，筛选只是看它的方式
 *    （同 `resetFilters` 的判据）。
 */
watch(
  [keyword, categoryFilter, lifeModeFilter, taskFilters],
  () => {
    page.value = 1
  },
  { deep: true },
)

/**
 * 结果变少导致当前页越界 ⇒ 拉回最后一页。
 *
 * 筛选那条 watch 覆盖了「筛完只剩 1 页」，但**删物品 / 刷新列表**不经过筛选，
 * 也会让总页数变小 —— 那条路不能漏（否则停在空页上，读作「列表空了」）。
 */
watch(pageCount, (total) => {
  if (page.value > total) page.value = total
})
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
/* 待办 chip 行 —— 与上面那行同宽，读作一组「看什么」 */
.survival-ledger__tasks {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.survival-ledger__tasks-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
/* tooltip 要一个能 hover 的元素包住 chip：disabled 的控件本身收不到鼠标事件 */
.survival-ledger__chip-wrap {
  display: inline-flex;
}
/* chip 上的件数：跟在标签后面、轻一点 —— 别抢「标签」本身的读法 */
.survival-ledger__chip-count {
  margin-left: 5px;
  font-size: 11px;
  opacity: 0.7;
}
/* 多选类别要更宽：收起成「吃 +1」时也得放得下两个标签 */
.survival-ledger__select--multi {
  width: 200px;
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
/* 「见配方」用次要色：它是**正常状态**（口径在配方里），不该像「未填」那样
   抢眼 —— 但也不能与一串天数长得一样，否则读起来会以为是数值。 */
.survival-ledger__by-recipe {
  color: var(--el-text-color-secondary);
}
.survival-ledger__ok {
  color: var(--el-text-color-placeholder);
}
/* 分页栏：沿用 Wealth 模块惯例（small + 居中 + 上边距），见 BillListView.vue */
.survival-ledger__pagination {
  display: flex;
  justify-content: center;
  margin-top: 10px;
}
/* 勾选分布：只在「有跨页 / 有被筛掉」时出现 ⇒ 样式要轻，它是解释、不是警告 */
.survival-ledger__selection {
  margin-left: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
