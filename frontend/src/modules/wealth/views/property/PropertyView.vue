<!--
  物件资产（v3.60.0，P4-A 一期）+ 身上之物（v3.62.4，第三个页签）

  这个页面回答的**不是**「我有多少钱」（那是 `/wealth/cashflow` 的资产盘点），
  而是两件事，分成两个页签：

    物件台账   我有哪些家当、每一件现在什么状态   （已经买回来的）
    类别维护   我的家当分了哪几类
    身上之物   我该有什么、找到了没有             （还**没**找到的）

  ── 为什么「身上之物」不新开一个菜单项 ──

  照「作品」的先例：先做结果页，真成了主战场再提级（侧边栏稳定在 46 项）。
  而且它与物件资产是**同一个问题的两面** —— 「找到了」的收尾动作就是挂到物件资产，
  同页最顺（设计稿 §5.5、§10 第 3 条）。

  ── 三个页签，`v-show` 不用 `v-if` ──

  ⚠️ `v-if` 会重挂载、丢掉列表的筛选与排序态 —— 而那正是**跨页签的中间态**
     （筛出「已报废」→ 去类别页改个说明 → 回来接着看）。用 `v-show` 保住它。

  🔴 合计卡与那句「不计入净资产」的说明**必须收在台账这个 pane 里面**。
     它们原先在两个页签之外、不随页签变 —— 加上第三个页签后，
     切到「身上之物」会看到**物件资产的合计卡**，那是**口径串台**（静默的错）。
     页头那个按钮同理：切到哪个页签就只服务哪个页签（同一块内容只许一条路径）。

  🔴 页面上没有一个阈值数字，也没有一处除法：
     折旧 / 净值 / 四项合计在 `property_calc`，`satisfaction_blank_reason` / 计数在
     `body_calc`（各自唯一真源），口径文案全在 `constants.py`（经 meta 接口下发）。
     这里补一句「其实就是……」，口径就有了两份，改后端时必然漏改。
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

      <!--
        🔴 页头按钮**按页签分流** —— 它不再是一个「两个含义共用一个样子」的按钮：
           在台账页是「新增物件」，在「身上之物」页是「新增一位」。
           一个按钮两种含义，用户按下去之前没法预判会发生什么。
      -->
      <div class="property-view__actions">
        <el-button
          v-if="activeTab === 'body' && bodyStore.available"
          size="small"
          type="primary"
          @click="openNeedForm(null)"
        >
          <el-icon><Plus /></el-icon>新增一位
        </el-button>
        <el-button
          v-else-if="store.available"
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
      <el-alert
        v-if="activeTab === 'body' && !bodyStore.loading && !bodyStore.available"
        type="info"
        :closable="false"
        show-icon
        class="property-view__alert"
        title="身上之物的数据还没就绪"
        :description="bodyStore.unavailableReason"
      />

      <!-- ① 物件台账 -->
      <div v-show="activeTab === 'ledger'" class="property-view__pane">
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

        <PropertyTable
          v-model:search="searchFilter"
          v-model:category="categoryFilter"
          v-model:status="statusFilter"
          v-model:condition="conditionFilter"
          :items="store.items"
          @edit="openForm"
          @delete="onDelete"
          @treasure-saved="store.fetchAll()"
        />
      </div>

      <!-- ② 类别维护 -->
      <div v-show="activeTab === 'categories'" class="property-view__pane">
        <PropertyCategoryPanel
          @new="openCategoryDialog(null)"
          @edit="openCategoryDialog"
        />
      </div>

      <!-- ③ 身上之物 —— 我该有什么、找到了没有 -->
      <div v-show="activeTab === 'body'" class="property-view__pane">
        <template v-if="bodyStore.available">
          <div class="property-view__body-top">
            <BodyNeedSummary
              :summary="bodyStore.summary"
              :meta-by-key="bodyStore.metricMetaByKey"
              :active="bodyActiveFilter"
              @filter="onBodyFilter"
            />
            <!-- 部位维护是低频动作 ⇒ 收成一个右侧入口，不占常态版面 -->
            <el-button
              link
              size="small"
              type="primary"
              class="property-view__body-parts-entry"
              @click="partDialogVisible = true"
            >
              部位维护
            </el-button>
          </div>

          <BodyNeedTable
            v-model:search="bodySearch"
            v-model:part="bodyPartFilter"
            v-model:status="bodyStatusFilter"
            v-model:pending="bodyPending"
            :needs="bodyStore.needs"
            :meta-by-key="bodyStore.metricMetaByKey"
            @edit="openNeedForm"
            @delete="onDeleteNeed"
          />
        </template>
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

    <BodyNeedFormDialog v-model:visible="needFormVisible" :need-id="editingNeedId" />

    <BodyPartDialog v-model:visible="partDialogVisible" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  InfoFilled, Plus, QuestionFilled, Suitcase, Tickets, Collection, Handbag,
} from '@element-plus/icons-vue'
import PropertySummaryCards from '../../components/property/PropertySummaryCards.vue'
import PropertyTable from '../../components/property/PropertyTable.vue'
import PropertyFormDialog from '../../components/property/PropertyFormDialog.vue'
import PropertyCategoryPanel from '../../components/property/PropertyCategoryPanel.vue'
import PropertyCategoryDialog from '../../components/property/PropertyCategoryDialog.vue'
import BodyNeedSummary from '../../components/body/BodyNeedSummary.vue'
import BodyNeedTable from '../../components/body/BodyNeedTable.vue'
import BodyNeedFormDialog from '../../components/body/BodyNeedFormDialog.vue'
import BodyPartDialog from '../../components/body/BodyPartDialog.vue'
import { usePropertyStore } from '../../stores/propertyStore'
import { useBodyStore } from '../../stores/bodyStore'
import { extractApiMessage } from '../../utils/propertyError'
import type { PropertyCategory } from '../../types/propertyTypes'

const store = usePropertyStore()
const bodyStore = useBodyStore()

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
  { name: 'body', label: '身上之物', icon: Handbag },
]

const activeTab = ref('ledger')

// ─── 筛选（放在页面这一级：四卡点击要能直接改状态这一项） ───
//
// ⚠️ 筛选在**前端**做（`PropertyTable` / `BodyNeedTable` 内部过滤）：
//    量级小，且计数卡的点击必须跟列表**瞬时**联动 —— 走一趟接口会有可见的延迟。
//    后端那几个 query 参数仍然可用（供脚本 / 将来用），只是界面不走它们。
const searchFilter = ref('')
const categoryFilter = ref<number | null>(null)
const statusFilter = ref('')
const conditionFilter = ref('')

/** 点四卡：再点一次同一张 = 取消筛选（同生存资源盘点的交互习惯） */
function onFilterStatus(value: string) {
  statusFilter.value = value
}

// ─── 身上之物的筛选 ───
const bodySearch = ref('')
const bodyPartFilter = ref<number | null>(null)
const bodyStatusFilter = ref('')
/** true = 只看没搞定的（顶部那个数字点下去就是它） */
const bodyPending = ref(false)

const bodyActiveFilter = computed(() => {
  if (bodyPending.value) return 'pending'
  return bodyStatusFilter.value || 'all'
})

/**
 * 顶部计数卡 → 筛选。
 *
 * ⚠️ 「还没搞定」与「待寻/寻找中/已找到」**互斥**（它们量的不是同一件事：
 *    一个是「还没定下来」，一个是「到哪一步了」）。切到其中一个就把另一个清掉 ——
 *    否则会出现「点了两次、两个高亮、实际用了一个条件」的假象。
 */
function onBodyFilter(value: string) {
  if (value === 'pending') {
    bodyPending.value = true
    bodyStatusFilter.value = ''
    return
  }
  bodyPending.value = false
  bodyStatusFilter.value = value === 'all' ? '' : value
}

// ─── 弹窗 ───
const formVisible = ref(false)
const editingItemId = ref<number | null>(null)

const categoryDialogVisible = ref(false)
const editingCategory = ref<PropertyCategory | null>(null)

const needFormVisible = ref(false)
const editingNeedId = ref<number | null>(null)

const partDialogVisible = ref(false)

function openForm(id: number | null) {
  editingItemId.value = id
  formVisible.value = true
}

function openCategoryDialog(category: PropertyCategory | null) {
  editingCategory.value = category
  categoryDialogVisible.value = true
}

function openNeedForm(id: number | null) {
  editingNeedId.value = id
  needFormVisible.value = true
}

function onSaved() {
  // 四卡与列表都由 store 的 refreshAll 重拉 —— 这里不需要再做任何事
}

/**
 * 删除一个位 —— 就是「不需要这一条了」的出口。
 *
 * ⚠️ 这也是刻意**没有**「不想找了」状态的原因：那个状态会同时装
 *    「真的不需要」和「暂时懒得找」两种相反的东西（兜底桶）。
 *    确认框里把那两个替代动作说出来，用户才不会把删除当「暂时搁置」用。
 */
async function onDeleteNeed(id: number) {
  const target = bodyStore.needs.find((item) => item.id === id)
  if (!target) return
  try {
    await ElMessageBox.confirm(
      `确认删掉「${target.part_name} · ${target.name}」？`
      + '只是暂时不想找了的话，把进度留着不动就行 —— 这一条不会来催你。',
      '删掉这一位',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await bodyStore.removeNeed(id)
    ElMessage.success(`已删掉「${target.name}」`)
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '删除失败'))
  }
}

/**
 * 删除一件物件 —— **物理删除**，没有回收站。
 *
 * ⚠️ 确认框里要把「不可恢复」说出来：报废已经承担了「不用了」的语义，
 *    所以删除只用于**录错**。不说清的话，用户会把删除当软删用，
 *    然后发现「淘汰过什么」这份记录少了几条，而那是找不回来的。
 * ⚠️ 顺带一句：挂在它上面的「位」不会跟着消失（`SET_NULL`）——
 *    那是「我该有一副眼镜」这件事，不该因为卖掉旧眼镜就没了。
 */
async function onDelete(id: number) {
  const target = store.items.find((item) => item.id === id)
  if (!target) return
  try {
    await ElMessageBox.confirm(
      `确认删除「${target.name}」？这是永久删除，没有回收站。`
      + '如果只是不用了，请把状态改成「已报废」—— 那会保留记录，也保留「我淘汰过什么」。'
      + '（挂在它上面的「身上之物」不会跟着消失，只会变成没挂东西）',
      '删除物件',
      { type: 'warning', confirmButtonText: '永久删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeItem(id)
    // 关联可能变了（SET_NULL）⇒ 身上之物那边也要重拉，否则会显示一个已经不存在的关联
    await bodyStore.refreshAll()
    ElMessage.success(`已删除「${target.name}」`)
  } catch (e: unknown) {
    ElMessage.error(extractApiMessage(e, '删除失败'))
  }
}

onMounted(() => {
  store.fetchAll()
  // ⚠️ 两个 store **各自取数**，不共用：物件资产没就绪不该拖住身上之物，
  //    反过来也一样（两张表来自不同的迁移，可以只有一个没跑）。
  bodyStore.fetchAll()
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
.property-view__body-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.property-view__body-top > :first-child {
  flex: 1;
  min-width: 0;
}
.property-view__body-parts-entry {
  /* 低频入口收在右侧，不占常态版面（同 §79「按读的频率分流」） */
  flex-shrink: 0;
  margin-top: 2px;
}
</style>
