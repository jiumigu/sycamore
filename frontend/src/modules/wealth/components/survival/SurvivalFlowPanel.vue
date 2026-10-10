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

  ⚠️ 筛选下拉的选项**从实际数据里聚合**，不硬编码一份：
     硬编码的选项列表迟早与后端枚举分叉，而分叉是静默的 ——
     下拉里有一个选了永远查不到东西的项。
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
        @change="loadFlows"
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
        @change="loadFlows"
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
        @keyup.enter="loadFlows"
        @clear="loadFlows"
      />
      <el-button size="small" :loading="flowStore.loading" @click="loadFlows">查询</el-button>
      <!-- 🔴 「取不到」不能写成「最近 0 条」：那是在用数字说一件没发生的事 -->
      <span v-if="listError" class="flow-panel__count is-error">取不到流水</span>
      <span v-else class="flow-panel__count">最近 {{ flows.length }} 条</span>
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

    <!-- 空态：说真话，且不补造历史 -->
    <el-empty
      v-if="!flowStore.loading && flowStore.loaded && !flows.length"
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
import type { SurvivalFlow } from '../../types/survivalTypes'

const flowStore = useSurvivalFlowStore()
const survivalStore = useSurvivalStore()

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
 * 渠道下拉的选项**从已加载的流水里聚合**（不硬编码一份）。
 *
 * ⚠️ 硬编码的代价是静默分叉：后端加了新渠道，前端下拉里没有，
 *    用户就永远筛不到那批记录 —— 而界面上看不出任何异常。
 *    从数据里聚合，至少「出现的都能筛」。
 */
const channelOptions = computed(() => {
  const seen = new Map<string, string>()
  flows.value.forEach((row) => {
    if (row.channel && !seen.has(row.channel)) seen.set(row.channel, row.channel_label)
  })
  return [...seen.entries()].map(([value, label]) => ({ value, label }))
})

function loadFlows() {
  return flowStore.fetchFlows({
    category_name: filters.category_name || undefined,
    channel: filters.channel || undefined,
    keyword: filters.keyword.trim() || undefined,
  })
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
