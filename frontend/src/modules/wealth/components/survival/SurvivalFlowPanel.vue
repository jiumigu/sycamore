<!--
  库存流水 · 页签（v3.60.18 · P0）

  这个页签只回答一个问题：**这东西是怎么变少的。**

  🔴 **这里只「看」，不「登」。** 登记入口长在物品上（清单 / 明细 / 盘点工作表的每行），
     因为这个页签**不放登记按钮** —— 那会把「查流水」变成「又要先选一次物品」，
     而用户想「我吃了一罐」时，眼睛盯的是那件物品，不是这一页。

  ── 三个刻意的取舍 ──

  ① **不上涨红跌绿。**「吃掉」不是亏损、「入库」不是盈利 ——
     它们只是方向不同。方向只用符号区分（`−` / `+`），颜色保持中性。
     （同项目判据：盘盈盘亏不套价格语义。）

  ② **汇总不给「总消耗 X 件」。** 「用掉 3 斤米 + 2 罐罐头」加起来没有意义，
     不同单位不可通约。所以按单位分桶列，桶内才求和 ——
     那个合计数看起来最像答案，其实是最没有意义的数。

  ③ **空态要说真话，而且「查不出来」有两种，不能合口。** 功能上线之前的库存变化
     **没有留痕**，不补造一条假的「期初基线」（同项目判据：查不出来就承认查不出来）。
        · 「取到了，一条都没有」 → 「这个月还没有流水」
        · 「这次没取到」（迁移没跑 / 接口 500） → 「取不到」，且明说
          **列表为空不代表没有流水**。
     只写前一句的后果：一次 500 被读成「我这月没吃任何东西」——
     把系统的失败记到了用户的账上（同项目「迁移没跑 ≠ 数据为空」）。
     ⚠️ 汇总卡片这里是**一条 `v-if` 链上的四态**（失败 / 在取 / 有桶 / 空），
        拆成两条独立 `v-if` 就会同时命中两种，实测过。

  ⚠️ 渠道下拉的选项**走 `/survival/meta/` 下发**（`meta.flow_channels`）——
     既**不硬编码**一份，也**不从流水数据里聚合**：
       · 硬编码的代价是静默分叉：后端加了渠道、前端下拉里没有，
         用户就永远筛不到那批记录，而界面上看不出任何异常；
       · 从数据聚合（v3.60.26 之前的写法）在本页加分页之后会**更糟**：
         `flows` 只剩当前页那几条 ⇒ 渠道选项**随翻页出现和消失** ——
         第 1 页有「手工登记」，翻到第 2 页它就不见了，用户想筛回去却找不到。
     ⇒ 枚举的单一出口就是 `/survival/meta/`（与后端 `_clean_channel` 读同一个常量）。

  ══════════════════════════════════════════════════════════════
  🔴 2026-10-10：改真分页（v3.60.26）—— 先修「取不全」，再谈「放不下」
  ══════════════════════════════════════════════════════════════

  实测 13 条就往下溢出 2.4 行（900px 视口，内部滚动容器可视 794px）。
  但比分页更硬的问题是**取不全**：后端 `list_flows` 的 `limit` 默认 **30**，
  而前端**从来不传** limit ⇒ 第 31 笔起前端**够不着**，
  界面却写着「共 N 笔」= 实际取回来那几条 —— 它**没说被截断了**。
  ⇒ 光加分页栏不够，得让取数**真的能翻**。

  ⇒ 改成**后端真分页**：`list_flows` 带 `offset`，并新增 `count_flows` 出总数；
    列表接口的返回从**裸数组**变成**显式的 `{rows, total}`**。

  四条判据（写错任一条都是**静默**的；常量与分页栏那两条见
  `utils/survivalPaging.ts` 的文件头）：

  1. **`total` 必须是「筛选之后」的数，而且要与「取这一页」走同一套筛选。**
     ⇒ 后端把筛选条件抽成 `_flow_queryset()`，`list_flows`（取一页）与
     `count_flows`（数总数）**共用同一份**。两处各写一遍的两种症状都不报错：
     总数偏大 ⇒ 页码比实际页数多，**翻到最后一页是空表**；
     总数偏小 ⇒ 末尾几笔**永远翻不到**（而那几笔确实在库里）。
  2. **筛选一变回第 1 页**，否则「筛剩 3 笔、却停在第 3 页」= 一张空表。
  3. **页码越界要夹回来**（结果变少时）。本页唯一会让结果变少的路径是
     改筛选（已由判据 2 覆盖）；别处记了一笔走的是刷新信号，也回第 1 页。
     剩下由 `el-pagination` 自己在 `total` 变化时夹 —— 它是受控的。
  4. **形状对不上要说出来，不能当成空。** 旧代码的兜底是「不是数组就当空数组」
     —— 那是为「被 DRF 包了」写的防线。形状一换成 `{rows, total}`，
     同一条兜底会**反过来**把「前后端版本不一致」静默说成「没有流水」，
     而这恰是本项目最贵的一类错（**把系统的失败记到用户的账上**）。
     ⚠️ 这个 `{rows, total}` 与「被 DRF 全局分页包成 `{count, results}`」
        **不是一回事**：那个是**意外**包装（前端按数组消费即「假 0」），
        这个是**有意**的结构；字段名刻意取得不同，就是为了不被当成同一种东西。

  ⚠️ 翻页/改每页条数是**两次请求**（`el-pagination` 会同时 emit
     `size-change` 与 `current-change`，见 `onSizeChange` 的注释）——
     所以 store 里有一道**请求序号守卫**：只有最后发出的那次有权写状态。
     没有它，「连点两下页码」的旧响应会盖住新响应，而界面上看不出。
-->
<template>
  <div class="flow-panel">
    <!-- ── 月度汇总：回答「这个月吃掉多少」 ── -->
    <div class="flow-panel__summary">
      <div class="flow-panel__summary-head">
        <el-date-picker
          v-model="month"
          type="month"
          size="small"
          value-format="YYYY-MM"
          :clearable="false"
          class="flow-panel__month"
          @change="loadSummary"
        />
        <span v-if="summary" class="flow-panel__summary-range">
          {{ summary.date_from }} ~ {{ summary.date_to }} · 共 {{ summary.count }} 笔
          （出 {{ summary.consumed_count }} / 入 {{ summary.gained_count }}）
        </span>
      </div>

      <!--
        🔴 **一条链，不能拆成两条。** 这里四态互斥，必须挂在同一个 `v-if` 链上：
             取不到（失败） / 还没取（正在取） / 有桶（正常） / 取到了但空
           拆成两条独立 `v-if` 的后果实测过：桶渲染的同时，
           下面那条 `v-else` 也会命中「这个月还没有流水」——
           于是同一张卡片一边列着「罐 出 2 净 −2」，一边说「还没有流水」。
      -->
      <div v-if="summaryError" class="flow-panel__summary-empty is-error">
        取不到这个月的汇总 —— {{ summaryError }}
      </div>
      <div v-else-if="!summaryLoaded" class="flow-panel__summary-empty">正在取这个月的汇总…</div>
      <div v-else-if="summary && summary.by_unit.length" class="flow-panel__buckets">
        <div v-for="bucket in summary.by_unit" :key="bucket.unit_name" class="flow-panel__bucket">
          <span class="flow-panel__bucket-unit">{{ bucket.unit_name || '（无单位）' }}</span>
          <span class="flow-panel__bucket-num">出 {{ bucket.consumed }}</span>
          <span class="flow-panel__bucket-num">入 {{ bucket.gained }}</span>
          <span class="flow-panel__bucket-net">
            净 {{ bucket.net > 0 ? '+' : '' }}{{ bucket.net }}
          </span>
        </div>
      </div>
      <div v-else class="flow-panel__summary-empty">这个月还没有流水</div>

      <!-- 这句话不是装饰：不写出来，用户会以为「总消耗」被漏做了 -->
      <div class="flow-panel__summary-note">
        按单位分别统计 ——「3 斤米」与「2 罐罐头」不可通约，所以不相加
      </div>
    </div>

    <!-- ── 筛选 ── -->
    <div class="flow-panel__filters">
      <el-select
        v-model="filters.category_name"
        size="small"
        placeholder="全部类别"
        clearable
        class="flow-panel__filter"
        @change="onFilterChange"
      >
        <el-option
          v-for="name in categoryNames"
          :key="name"
          :label="name"
          :value="name"
        />
      </el-select>
      <el-select
        v-model="filters.channel"
        size="small"
        placeholder="全部渠道"
        clearable
        class="flow-panel__filter"
        @change="onFilterChange"
      >
        <el-option
          v-for="opt in channelOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-input
        v-model="filters.keyword"
        size="small"
        placeholder="搜物品名或备注"
        clearable
        class="flow-panel__search"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-button size="small" :loading="flowStore.loading" @click="onFilterChange">查询</el-button>
      <!--
        🔴 「取不到」不能写成「共 0 笔」：那是在用数字说一件没发生的事。
        ⚠️ 这里给的是**筛选之后的总笔数**（`flowStore.total`），**不是** `flows.length`
           —— `flows` 只是这一页，拿它当总数的话页码永远只有 1 页，
           而分页栏照常渲染，看起来完全正常。
      -->
      <span v-if="listError" class="flow-panel__count is-error">取不到流水</span>
      <span v-else class="flow-panel__count">共 {{ flowStore.total }} 笔</span>
    </div>

    <!-- 取列表失败：说清楚是系统的问题、列表为空不是「没有记录」，并给一个重试的口 -->
    <el-alert
      v-if="listError"
      :title="listError"
      type="error"
      :closable="false"
      show-icon
      class="flow-panel__error"
    >
      <template #default>
        <span class="flow-panel__error-sub">
          列表是空的，但<b>这不代表没有流水</b> —— 只是这次没取到。
          若刚升级过，先确认数据库迁移已执行，然后
          <el-button link size="small" @click="loadFlows">重试</el-button>
        </span>
      </template>
    </el-alert>

    <!-- ── 列表 ── -->
    <el-table
      v-loading="flowStore.loading"
      :data="flows"
      size="small"
      class="flow-panel__table"
      empty-text=" "
    >
      <el-table-column label="时间" width="140">
        <template #default="{ row }">{{ formatTime(row.occurred_at) }}</template>
      </el-table-column>
      <el-table-column label="物品" min-width="140">
        <template #default="{ row }">
          <span>{{ row.item_name }}</span>
          <!-- 物品删了，历史仍在：标出来，而不是让它看着像一件现存的物品 -->
          <el-tag v-if="row.item_missing" size="small" type="info" class="flow-panel__tag">
            已删除
          </el-tag>
          <el-tag v-if="row.category_name" size="small" class="flow-panel__tag" effect="plain">
            {{ row.category_name }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="变化" width="110">
        <!-- 中性色：方向只用符号区分，不套「涨红跌绿」 -->
        <template #default="{ row }">{{ deltaText(row) }}</template>
      </el-table-column>
      <el-table-column label="原因" width="90">
        <template #default="{ row }">{{ row.reason_label || '—' }}</template>
      </el-table-column>
      <el-table-column label="渠道" width="110">
        <template #default="{ row }">{{ row.channel_label }}</template>
      </el-table-column>
      <el-table-column label="备注" min-width="120">
        <template #default="{ row }">
          <span class="flow-panel__note-text">{{ row.note || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <!-- 已撤销的行**不再显示按钮** —— 让它可点、点完报错，是对用户的一次白跑 -->
          <span v-if="row.reverted" class="flow-panel__reverted">已撤销</span>
          <el-button
            v-else
            link
            size="small"
            @click="onReverse(row)"
          >撤销</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!--
      分页 —— 判据见文件头 2026-10-10。这里是**真分页**：
      每页条数与页码都要送到后端（`limit` / `offset`），不是在前端切一份全量。
      ⇒ 每页条数选 100 就是「一次尽可能多看」的出口（但后端上限 500）。

      🔴 显示条件走 `shouldShowPager(flowStore.total)`（`utils/survivalPaging.ts` 单一实现），
         判据是「**存在**能让它分页的每页条数」、**不是**「当前每页条数下有多页」——
         后者会在选上「100 条/页」之后把分页栏整个藏掉，用户再也调不回 20
         （而选 100 是「一屏看全部」的正常用法，不是误操作）。
      🔴 `:total` 必须是**筛选之后的总笔数**（`flowStore.total`），**不是** `flows.length`
         —— `flows` 只是这一页：拿它当总数，页码永远只有 1 页，而分页栏照常渲染。
      ⚠️ 本模块四个列表共用同一套常量与判据（v3.60.26 起），组件里不再各留一份。
    -->
    <div v-if="shouldShowPager(flowStore.total)" class="flow-panel__pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="PAGE_SIZE_OPTIONS"
        :total="flowStore.total"
        size="small"
        layout="prev, pager, next, sizes"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>

    <!-- 空态：说真话，且不补造历史 -->
    <el-empty
      v-if="!flowStore.loading && flowStore.loaded && !flowStore.total"
      :image-size="70"
      description="还没有流水记录"
      class="flow-panel__empty"
    >
      <template #description>
        <div class="flow-panel__empty-text">
          <div>还没有流水记录</div>
          <div class="flow-panel__empty-sub">
            流水从本功能上线起开始记录 —— 在这之前的库存变化没有留痕，也不补造。
            以后在物品上点「用掉 / 入库」、提交盘点或改数量，都会自动留下一笔。
          </div>
        </div>
      </template>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSurvivalFlowStore } from '../../stores/survivalFlowStore'
import { useSurvivalStore } from '../../stores/survivalStore'
import {
  DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, shouldShowPager,
} from '../../utils/survivalPaging'
import type { SurvivalFlow } from '../../types/survivalTypes'

const flowStore = useSurvivalFlowStore()
const survivalStore = useSurvivalStore()

/**
 * 这一页的流水。
 *
 * 🔴 v3.60.26 起是**真分页**：store 里放的就是后端这一页，
 *    所以这里**不需要再切一刀**（切了就是「在 20 条里再取前 20 条」，
 *    翻到第 2 页会看到一片空白，而分页栏照常显示）。
 * ⚠️ 因此凡是「从流水列表取全量」的派生量，**都不能读它** ——
 *    总数读 `flowStore.total`（后端给的、筛选之后的数）。
 */
const flows = computed(() => flowStore.flows)
const summary = computed(() => flowStore.summary)
/** 「取不到」的三个状态位（空串 = 没失败）—— 与「一条都没有」严格分开 */
const listError = computed(() => flowStore.listError)
const summaryError = computed(() => flowStore.summaryError)
const summaryLoaded = computed(() => flowStore.summaryLoaded)

/** 默认看本月 —— 「这个月吃掉多少」是最常问的那一句 */
function thisMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

const month = ref(thisMonth())

const filters = reactive({
  category_name: '',
  channel: '',
  keyword: '',
})

const categoryNames = computed(
  () => survivalStore.categories.map((c) => c.name).filter(Boolean),
)

/**
 * 分页状态（v3.60.26）。
 *
 * ⚠️ 这两个数与 `filters` 是**同一类东西**：都决定「后端该给我哪一段」。
 *    所以它们不进 URL、也不跨页签保留 —— 与筛选条件同进同出。
 * ⚠️ 每页条数用共享默认值（`DEFAULT_PAGE_SIZE`）：本模块四个列表一致，
 *    用户不必记「哪一块默认多少」。
 */
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)

/**
 * 渠道下拉的选项 —— 走 `/survival/meta/` 下发（`meta.flow_channels`）。
 *
 * 🔴 **不能从 `flows` 里聚合**（v3.60.26 之前就是这么写的）：流水一加分页，
 *    `flows` 只剩**当前页**那几条 ⇒ 渠道选项会**随翻页出现和消失**：
 *    第 1 页有「手工登记」，翻到第 2 页它就不见了，用户想筛回去却找不到那个选项。
 * ⚠️ 与类别下拉**不同源**：类别是**用户可增删的数据**（走 `/survival/categories/`），
 *    渠道是**后端枚举**（走 meta）—— 后者没有第二个来源，也不该有。
 * ⚠️ meta 里**全量下发所有渠道**（不做分面过滤）：渠道只有 6 个、且是枚举；
 *    若按当前筛选结果缩减，筛了「吃掉」之后就只剩一个可选项，等于把用户锁死。
 * ⚠️ meta 还没取到时这里是空数组、下拉里没有选项 —— 这**不是**「没有这个渠道」，
 *    只是这次没取到；所以不写「无匹配项」之类的解释性文案（那会替它下结论）。
 */
const channelOptions = computed(() => survivalStore.meta?.flow_channels ?? [])

/**
 * 取一页流水。
 *
 * 🔴 `limit` / `offset` 必须**每次都送**：不送 limit 的话后端用默认值 **30**，
 *    于是「共 N 笔」里超过 30 的那部分**永远够不着**，而界面上没有任何提示
 *    ——那正是本次要修的那个坑，别把它写回来。
 */
function loadFlows() {
  return flowStore.fetchFlows({
    category_name: filters.category_name || undefined,
    channel: filters.channel || undefined,
    keyword: filters.keyword.trim() || undefined,
    limit: pageSize.value,
    offset: (page.value - 1) * pageSize.value,
  })
}

/**
 * 筛选变了 —— **先回第 1 页，再取数**。
 *
 * 🔴 顺序不能反：反了的话请求带的是**旧页**的 offset，
 *    而结果集已经变小 ⇒ 用户拿到一张空表，读作「筛选坏了」。
 * ⚠️ 置 `page` 本身**不会**触发 `current-change`（v-model 是受控的、
 *    这次写入没有经过 `el-pagination`）⇒ 取数只能由这里自己发起，
 *    不能指望分页栏替我们做。
 */
function onFilterChange() {
  page.value = 1
  return loadFlows()
}

/** 翻页 —— `v-model` 已经把 `page` 更新好了（`el-pagination` 先 emit update、再 emit change） */
function onPageChange() {
  return loadFlows()
}

/**
 * 改每页条数。
 *
 * 🔴 同样**先回第 1 页再取数**：否则请求带的是旧页的 offset，
 *    而每页条数已经变了 ⇒ 用户看到的那一段既不是第 1 页、也不是他原来那页。
 *
 * ⚠️ `el-pagination` 在 `handleSizeChange` 里先 emit `size-change`，
 *    **之后**若当前页超出新的总页数，还会 `emit('current-change')`
 *    （`element-plus/es/components/pagination/src/pagination.mjs` 的
 *    `currentPageBridge` setter）。
 *    **实测（2026-10-10，真实浏览器）**：在第 3 页把每页条数
 *    从「10 条/页」改成「20 条/页」，只发出**一次**请求
 *    （`limit=20&offset=0`，无重复）—— 因为这里先把页码置成 1，
 *    紧接着那句 `if (currentPageBridge.value > newPageCount)` 就不成立。
 *    ⇒ 不为「可能双发」加谦让逻辑（那会让某一次**该做的取数没做**）。
 *    即便它真的双发，两次请求带的是**同一组参数**、结果相同；
 *    而 store 里的请求序号守卫（见 `survivalFlowStore.fetchFlows`）
 *    保证只有最后一次有权写状态。
 */
function onSizeChange() {
  page.value = 1
  return loadFlows()
}

/** 汇总取不到不该把整页打空 —— 下面的列表仍然可用（失败原因记在 store 里） */
function loadSummary() {
  return flowStore.fetchSummary(month.value)
}

/**
 * 变化量的显示。
 *
 * 🔴 **只有符号，没有颜色。** 「−2 罐」与「+3 罐」都是事实陈述，
 *    给它们上「亏损红 / 收益绿」等于替用户判定好坏：
 *    入库也可能是一次恐慌性囤货，消耗也可能是一次必要的治疗。
 */
function deltaText(row: SurvivalFlow): string {
  const sign = row.delta > 0 ? '+' : '−'
  // 直接用数字拼字符串：`2.0` 会自然渲染成 `2`，不用再手工去尾零
  return `${sign}${Math.abs(row.delta)} ${row.unit_name}`.trim()
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    + ` ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * 撤销（v3.60.18）。
 *
 * 🔴 它**不是删除**：点下去会补一条反向流水，账自动正回来、历史全留。
 *    所以确认文案必须把这个说清楚 —— 用户以为在「删记录」时，
 *    他会期待「东西消失」；实际是「多出一条冲销记录」，两者差别很大。
 */
async function onReverse(row: SurvivalFlow) {
  try {
    await ElMessageBox.confirm(
      `撤销「${row.item_name} ${deltaText(row)}」这一笔？`
      + '会补一条反向流水把账正回来，两条记录都会保留（不会删除任何东西）。',
      '撤销这一笔',
      { type: 'warning', confirmButtonText: '撤销', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await flowStore.reverse(row.id)
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '撤销失败')
    return
  }
  ElMessage.success('已撤销（补了一条反向流水）')
  /**
   * 🔴 **先回第 1 页**（v3.60.26）。两件事都逼着这一句存在：
   *    ① 撤销**不是删除** —— 它新增一条反向流水 ⇒ 总数 +1、且它按时间排在最上面；
   *       留在原页的话，用户**看不到自己刚造成的那条记录**，
   *       而列表还整体错位一行（原页的最后一行被挤到下一页）。
   *    ② 那句话刚跟他说「补了一条反向流水」—— 说完就得让他能核对，
   *       否则它和「删掉了」在界面上没有区别。
   */
  page.value = 1
  await Promise.all([loadFlows(), loadSummary(), survivalStore.refreshAll()])
}

/**
 * 别处记了一笔（清单上的「用掉 / 入库」）之后重新取数。
 *
 * ⚠️ 用**信号**而不是让父级替本页签取数：这里的筛选条件是本页签自己的，
 *    父级替它取会静默重置筛选 —— 而重置之后界面看起来一切正常。
 * ⚠️ 页签用 `v-show` 切换（项目判据），所以本组件不会重新挂载，
 *    没有这个 watch 就会一直显示进来时那一份。
 */
watch(() => flowStore.refreshToken, async () => {
  /**
   * 🔴 回第 1 页（v3.60.26）：这个信号意味着**刚刚有人记了一笔**，
   *    而那笔按时间排在最上面 —— 留在第 3 页的话，他记完回来看见的是
   *    一份**跟刚才一模一样**的列表，会以为「没记上」而再记一遍。
   */
  page.value = 1
  await Promise.all([loadFlows(), loadSummary()])
})

onMounted(async () => {
  await Promise.all([loadFlows(), loadSummary()])
})

onUnmounted(() => {
  flowStore.resetState()
})
</script>

<style scoped>
.flow-panel {
  padding: 4px 0;
}

/* ── 月度汇总 ── */
.flow-panel__summary {
  padding: 12px 14px;
  margin-bottom: 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}
.flow-panel__summary-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.flow-panel__month {
  width: 140px;
}
.flow-panel__summary-range {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.flow-panel__buckets {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
}
/* 一个桶 = 一个单位。桶内才有意义，桶之间刻意不合并 */
.flow-panel__bucket {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 6px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 20px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.flow-panel__bucket-unit {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.flow-panel__bucket-net {
  color: var(--el-text-color-secondary);
}
.flow-panel__summary-empty {
  margin-top: 10px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
/* 「取不到」不是常态提示，用警示色 —— 它和「这个月没有」必须一眼分得开 */
.flow-panel__summary-empty.is-error {
  color: var(--el-color-danger);
}
.flow-panel__summary-note {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

/* ── 筛选 ── */
.flow-panel__filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.flow-panel__filter {
  width: 140px;
}
.flow-panel__search {
  width: 200px;
}
.flow-panel__count {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.flow-panel__count.is-error {
  color: var(--el-color-danger);
}

/* ── 取不到（≠ 没有） ── */
.flow-panel__error {
  margin-bottom: 10px;
}
.flow-panel__error-sub {
  font-size: 12px;
  line-height: 1.7;
}

.flow-panel__table {
  width: 100%;
}
/* 分页栏 —— 与物品清单同一套摆法（居中、贴表格下方 10px），四处行为一致 */
.flow-panel__pagination {
  display: flex;
  justify-content: center;
  margin-top: 10px;
}
.flow-panel__tag {
  margin-left: 6px;
}
.flow-panel__note-text {
  color: var(--el-text-color-secondary);
}
/* 「已撤销」是状态说明，不是可点的操作 —— 用灰字而不是灰按钮 */
.flow-panel__reverted {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

/* ── 空态 ── */
.flow-panel__empty {
  padding: 24px 0;
}
.flow-panel__empty-text {
  text-align: center;
}
.flow-panel__empty-sub {
  max-width: 460px;
  margin: 6px auto 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}
</style>
