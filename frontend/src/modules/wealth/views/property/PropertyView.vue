<!--
  物件资产（v3.60.0，P4-A 一期）

  这个页面回答的**不是**「我有多少钱」（那是 `/wealth/cashflow` 的资产盘点），
  而是：这些家当一共花了我多少钱、现在还在用哪些、哪几件已经用够本了。

  ── 为什么是独立菜单，不进 WealthHub 的页签 ──

  同 `/wealth/survival` 的处理：它盘的是**物**，与「资产盘点」（盘钱）是两件事。
  塞进 WealthHub 的页签会让「资产」这个词在一个页面里指两种东西。

  ── 首屏只回答一个问题 ──

  四张卡 + 一句「不计入净资产」的说明。没有结论条 ——
  本模块**没有**一个「综合得分」之类的产品答案，因为「该不该换」这件事
  系统不知道（见 `property_calc` 的四条口径）。四卡之上不要再造一个分数。

  ── 两个页签，`v-show` 不用 `v-if` ──

   物件台账   我有哪些家当（四卡 + 筛选 + 表格）
   类别维护   我的家当分了哪几类

  ⚠️ `v-if` 会重挂载、丢掉列表的筛选与排序态 —— 而那正是**跨页签的中间态**
     （筛出「已报废」→ 去类别页改个说明 → 回来接着看）。用 `v-show` 保住它。

  🔴 页面上没有一个阈值数字，也没有一处除法：
     折旧、净值、剩余月数、四项合计全部在
     `backend/apps/wealth/services/property_calc.py`（唯一真源），
     口径文案全在 `constants.PROPERTY_METRIC_NOTES`（经 `/property/meta/` 下发）。
     这里补一句「其实就是除一下」，口径就有了两份，改后端时必然漏改。

  ⚠️ 四卡的点击筛选只挂在卡①与卡④（状态这一维）——
     卡②③是金额，点了没有对应的筛选项可切，做成可点会让人以为能筛出「贵的那几件」。
-->
<template>
  <div class="property-view">
    <!-- 头部一行装三样：标题、页签、页面级动作 -->
    <div class="property-view__header">
      <div class="property-view__title-wrap">
        <el-icon class="property-view__title-icon"><Suitcase /></el-icon>
        <span class="property-view__title">物件资产</span>
        <el-tooltip :content="pageSubtitle" placement="bottom">
          <el-icon class="property-view__title-help"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>

      <div v-if="store.available" class="property-view__tabs">
        <div
          v-for="tab in tabs"
          :key="tab.name"
          class="property-view__tab"
          :class="{ active: activeTab === tab.name }"
          @click="activeTab = tab.name"
        >
          <el-icon class="property-view__tab-icon"><component :is="tab.icon" /></el-icon>
          <span>{{ tab.label }}</span>
        </div>
      </div>

      <div class="property-view__actions">
        <el-button
          v-if="store.available"
          size="small"
          type="primary"
          @click="openForm(null)"
        >
          <el-icon><Plus /></el-icon>新增物件
        </el-button>
      </div>
    </div>

    <!-- 迁移没跑 / 表还没建 —— 是可预期的部署状态，不是错误。
         刻意不显示成「一件家当都没有」：那会让人以为数据丢了。 -->
    <el-alert
      v-if="!store.loading && !store.available"
      type="info"
      :closable="false"
      show-icon
      class="property-view__alert"
      title="物件资产的数据还没就绪"
      :description="store.unavailableReason"
    />

    <template v-else>
      <PropertySummaryCards
        :summary="store.summary"
        :meta-by-key="store.metricMetaByKey"
        :active-status="statusFilter"
        @filter-status="onFilterStatus"
      />

      <!-- 固定那一句说明 —— 文案来自后端（唯一来源），前端不另写一份 -->
      <div class="property-view__note">
        <el-icon><InfoFilled /></el-icon>
        <span>{{ store.meta?.not_in_net_worth_note }}</span>
      </div>

      <!-- ① 物件台账 -->
      <div v-show="activeTab === 'ledger'" class="property-view__pane">
        <PropertyTable
          v-model:search="searchFilter"
          v-model:category="categoryFilter"
          v-model:status="statusFilter"
          v-model:condition="conditionFilter"
          :items="store.items"
          @edit="openForm"
          @delete="onDelete"
        />
      </div>

      <!-- ② 类别维护 -->
      <div v-show="activeTab === 'categories'" class="property-view__pane">
        <PropertyCategoryPanel
          @new="openCategoryDialog(null)"
          @edit="openCategoryDialog"
        />
      </div>
    </template>

    <PropertyFormDialog
      v-model:visible="formVisible"
      :item-id="editingItemId"
      :default-category-id="categoryFilter"
      @saved="onSaved"
    />

    <PropertyCategoryDialog
      v-model:visible="categoryDialogVisible"
      :category="editingCategory"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  InfoFilled, Plus, QuestionFilled, Suitcase, Tickets, Collection,
} from '@element-plus/icons-vue'
import PropertySummaryCards from '../../components/property/PropertySummaryCards.vue'
import PropertyTable from '../../components/property/PropertyTable.vue'
import PropertyFormDialog from '../../components/property/PropertyFormDialog.vue'
import PropertyCategoryPanel from '../../components/property/PropertyCategoryPanel.vue'
import PropertyCategoryDialog from '../../components/property/PropertyCategoryDialog.vue'
import { usePropertyStore } from '../../stores/propertyStore'
import { extractApiMessage } from '../../utils/propertyError'
import type { PropertyCategory } from '../../types/propertyTypes'

const store = usePropertyStore()

/**
 * 页头副标题 —— 一次性的图例，收进标题旁的 ⓘ。
 *
 * ⚠️ 优先用**后端**那一句（`meta.subtitle`）：它同时说明了这个模块与
 *    「资产盘点」的边界。取不到时退回本地兜底 —— 副标题缺失不该让页面空白。
 */
const pageSubtitle = computed(
  () => store.meta?.subtitle ?? '管的是物件：家电 / 家具 / 数码，不是钱',
)

const tabs: { name: string; label: string; icon: Component }[] = [
  { name: 'ledger', label: '物件台账', icon: Tickets },
  { name: 'categories', label: '类别维护', icon: Collection },
]

const activeTab = ref('ledger')

// ─── 筛选（放在页面这一级：四卡点击要能直接改状态这一项） ───
//
// ⚠️ 筛选在**前端**做（`PropertyTable` 内部过滤）：家当量级小，
//    且四卡点击筛选必须跟列表**瞬时**联动 —— 走一趟接口会有可见的延迟。
//    后端那几个 query 参数仍然可用（供脚本 / 将来用），只是界面不走它们。
const searchFilter = ref('')
const categoryFilter = ref<number | null>(null)
const statusFilter = ref('')
const conditionFilter = ref('')

/** 点四卡：再点一次同一张 = 取消筛选（同生存资源盘点的交互习惯） */
function onFilterStatus(value: string) {
  statusFilter.value = value
}

// ─── 弹窗 ───
const formVisible = ref(false)
const editingItemId = ref<number | null>(null)

const categoryDialogVisible = ref(false)
const editingCategory = ref<PropertyCategory | null>(null)

function openForm(id: number | null) {
  editingItemId.value = id
  formVisible.value = true
}

function openCategoryDialog(category: PropertyCategory | null) {
  editingCategory.value = category
  categoryDialogVisible.value = true
}

function onSaved() {
  // 四卡与列表都由 store 的 refreshAll 重拉 —— 这里不需要再做任何事
}

/**
 * 删除一件物件 —— **物理删除**，没有回收站。
 *
 * ⚠️ 确认框里要把「不可恢复」说出来：报废已经承担了「不用了」的语义，
 *    所以删除只用于**录错**。不说清的话，用户会把删除当软删用，
 *    然后发现「淘汰过什么」这份记录少了几条，而那是找不回来的。
 */
async function onDelete(id: number) {
  const target = store.items.find((item) => item.id === id)
  if (!target) return
  try {
    await ElMessageBox.confirm(
      `确认删除「${target.name}」？这是永久删除，没有回收站。`
      + '如果只是不用了，请把状态改成「已报废」—— 那会保留记录，也保留「我淘汰过什么」。',
      '删除物件',
      { type: 'warning', confirmButtonText: '永久删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeItem(id)
    ElMessage.success(`已删除「${target.name}」`)
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '删除失败'))
  }
}

onMounted(() => {
  store.fetchAll()
})
</script>

<style scoped>
.property-view {
  padding: 16px 18px 24px;
}
.property-view__header {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.property-view__title-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}
.property-view__title-icon {
  color: var(--el-color-primary);
}
.property-view__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.property-view__title-help {
  color: var(--el-text-color-secondary);
  cursor: help;
}
.property-view__tabs {
  display: flex;
  align-items: center;
  gap: 4px;
}
.property-view__tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 14px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s;
}
.property-view__tab:hover {
  background: var(--el-fill-color-light);
}
.property-view__tab.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}
.property-view__tab-icon {
  font-size: 13px;
}
.property-view__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.property-view__alert {
  margin-bottom: 12px;
}
.property-view__note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 0 14px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.property-view__pane {
  margin-top: 4px;
}
</style>
