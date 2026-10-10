<!--
  生存资源盘点（v3.59.0，P3-A 一期；v3.59.3 加清单与实盘盘点；v3.60.2 盘点交互优化）

  这个页面回答的**不是**「我有哪些东西」，而是：
    按我现在的消耗方式，这些东西还能撑多久；哪一类先断；
    断的是钱这条腿还是物这条腿。

  所以结论条（综合能撑 / 钱能撑 / 瓶颈）**不放进任何一个页签**：
  它是本页唯一的产品答案，停在哪一页都该看得见。
  其余四块按「问题」分成四个页签，一屏只回答一个问题：

    总览           现在能撑多久、哪一类先断（四卡 + 类别明细 + 配置问题）
    物品清单       我有哪些东西（跨类别的全量台账，能改能删；**盘点唯一的挑物品入口**）
    实盘盘点记录   人**数出来**的实物数（盘盈盘亏，提交时校准库存）
    生存时长快照   系统**算出来**的结论（点一下就落一份，不需要人动手）

  ── 盘点为什么改成「两次点击 + 一个数字」（v3.60.2） ──

  实测用法：7 天内 6 次盘点、共 8 行、平均 **1.3 行**（其中 4 次只盘 1 件）。
  也就是说用户是**随手抽查一两件**，而在此之前每次都要为「改一个数字」
  打开一张全量 43 行的弹窗、在其中再找一遍那件。

  ⇒ 两条路都缩短了：

    ① **单件**：清单与类别明细的每行加「盘一下」→ 一个小弹窗，填一个数就走。
       它同时把「改库存」从「编辑物品（改主数据）」里分了出来 ——
       这两件事的入口在此之前是混在一起的。
    ② **批量**：挑物品**只留物品清单一处**（那里的筛选能力本来就更强：
       5 个筛选 vs 弹窗里的 1 个），弹窗只负责确认与提交。
       于是「实盘盘点记录」页的「开始盘点」不再直接开弹窗，而是把用户
       **送到清单页**并给一句提示（`gotoLedgerToPick`）——
       从一个没有预设的地方开弹窗只会开出一个空壳。

  ⚠️ 「勾上该盘的 N 件」曾是一枚**永远按不下去的按钮**：它依赖盘点周期，
     而 43 件物品里 **0 件**设过周期 ⇒ 恒灰，且旁边一个字的解释都没有。
     判据本身没错（把「从未盘过」也算该盘会让 43 件全标红 = 没有标），
     错的是那个字段在问一个用户答不上来的问题。
     ⇒ 另加一条零配置入口「勾上最久没盘的前 N 件」，并在原按钮位置
        说出为什么没有「该盘的」。判据见 `utils/survivalStocktake.ts`。

  ── 缺口对账为什么不在正文里（v3.59.9） ──

  「必需品缺口对账」回答的是**第二把尺子**上的问题：不是「够撑多久」，
  而是「漏了什么」。它原先嵌在总览（四卡之下、类别明细之上），于是每次看
  「还能撑多久」都要先路过一张二十来行的表 —— 两件事本来就不在同一个问题上。
  现在它是页头右侧的一个**入口**，点开才是那份对账（`SurvivalReconcileDialog`）。

  ⚠️ 搬进弹窗的代价：`unclosed_core`（核心项还没闭合）跟着被藏了起来，
     而它是「这份结论能不能用」的**唯一提示**（它不折算进天数 ——
     把「还没录」说成「只够撑 0 天」是另一个错误）。
     ⇒ 入口按钮**必须**带角标把这个数留在页头，见 `essentialEntry`。
     一条只在弹窗里看得见的可信度信号，等于没有这条信号。

  ── 页签摆在哪一行（v3.59.5） ──

  页签在**页头那一行**、紧挨标题右侧，不再自己占一行：
  它管的是页签下方那几块内容，单独占一行时正好夹在结论条与四张卡之间，
  会把「还能撑多久」这一组视觉切开 —— 而四张卡是那个答案的第一个落点。

  ⚠️ 三块原本是竖着堆在同一屏上的，越堆越长 —— 清单是手段、快照是历史，
     都不该跟「还能撑多久」抢同一屏的注意力。现在按页签分开，
     切页签用 `v-show` 而不是 `v-if`：清单的筛选与勾选是**跨页签的中间态**
     （勾好要盘的几件 → 去快照页看一眼 → 回来接着开盘点），
     用 `v-if` 会把它悄悄清空。

  ⚠️ 后两者的名字刻意不重名。二期那块原本标题就叫「盘点历史」，
     而它其实不是盘点 —— 那是系统自己的结论。真盘点进来之后，
     两个都叫「盘点」会让「我到底盘没盘过」永远说不清。

  ── 结论条的口径可达性（v3.59.10） ──

  结论条上的四个数与四张卡用的是**同一份** `SURVIVAL_METRIC_NOTES`
  （经 /survival/meta/ 下发），但在此之前四卡每张都挂 ⓘ，结论条一个都没有。
  结果是**越靠近答案的东西越不可解释**：「覆盖率 3%」孤零零挂在那儿，
  而后端 note 里明明写着「覆盖率低不等于危险 —— 物资是缓冲不是主粮」。

  ⚠️ 「钱能撑多久」在本次之前**没有可挂的口径键**（它只在 `bottleneck` 的
     note 里被顺带提过），所以同步在后端补了 `SURVIVAL_METRIC_NOTES['cash_days']`。
     前端没有、也不该在这里补一句自己的解释。

  ── 类别切换只有一个入口（v3.59.10） ──

  四张卡与那排类别页签绑的是**同一个** `activeCategoryId` ——
  同一屏上两套控件表达同一个选择，视觉语言还不同（卡片 vs 下划线页签）。
  现在页签行撤掉，四卡是唯一的选择器。

  ⚠️ 撤掉它有个连带代价：那排页签**兼职做着明细区的标题**。
     所以明细区补了一行 `{类别} · 明细`，否则下面那块内容没有标题。

  ── 页头的「配置」下拉（v3.59.10） ──

  「初始化默认类别」原先和「单位维护」并排占着主按钮位，看着像一次无害的补齐；
  它其实会弹「覆盖类别口径」，冲掉你在界面上改过的消耗模式、聚合口径与说明文案。
  现在两者一起收进「配置」下拉，危险的那一项带副标题把后果说出来。

  🔴 页面上没有一个阈值数字，也没有一处除法：
     判定与换算全在 `backend/apps/wealth/services/survival_calc.py`，
     口径文案全在 `constants.SURVIVAL_METRIC_NOTES`（经 /survival/meta/ 下发）。
     这里补一句「其实就是除一下」，口径就有了两份，改后端时必然漏改。
-->
<template>
  <div class="survival-view">
    <!-- 头部一行装三样：标题、页签、页面级配置。
         页签**不再自己占一行** —— 它管的是下面那三块内容，
         夹在结论条与四张卡之间，会把「还能撑多久」这一组视觉切开。
         新增物品 / 开始盘点仍跟着各自的面板走，不在这里重复出现。 -->
    <div class="survival-view__header">
      <div class="survival-view__title-wrap">
        <el-icon class="survival-view__title-icon"><Box /></el-icon>
        <span class="survival-view__title">生存资源盘点</span>
        <!-- 副标题收进 ⓘ：一行要放下标题 + 四个页签 + 三个配置项，
             这句话是一次性阅读的图例，不该长期占掉 370px 的横向空间 -->
        <el-tooltip :content="PAGE_SUBTITLE" placement="bottom">
          <el-icon class="survival-view__title-help"><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>

      <div v-if="analysis?.available" class="survival-view__tabs">
        <div
          v-for="tab in tabs"
          :key="tab.name"
          class="survival-view__tab"
          :class="{ active: activeTab === tab.name }"
          @click="activeTab = tab.name"
        >
          <el-icon class="survival-view__tab-icon"><component :is="tab.icon" /></el-icon>
          <span>{{ tab.label }}</span>
          <span v-if="tab.badge" class="survival-view__tab-badge">{{ tab.badge }}</span>
        </div>
      </div>

      <div class="survival-view__actions">
        <!-- 参考日期（v3.59.10）—— 见脚本里 `referenceDateValue` 的注释：
             未设时把「今天」显示成一个**具体日期**，而不是留一个空框。
             加这枚标签是因为一个孤零零的日期框说不清自己是干什么的。 -->
        <span class="survival-view__date-label">参考日期</span>
        <el-date-picker
          :model-value="referenceDateValue"
          type="date"
          size="small"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          clearable
          class="survival-view__date"
          @update:model-value="onDateChange"
        />
        <!-- 配置（v3.59.10）：这两项都是一次性 / 低频，
             且「初始化默认类别」是**破坏性的**（会问是否覆盖口径）——
             它们原先与「缺口对账」这种待办入口并排占主按钮位，权重完全一样。 -->
        <el-dropdown size="small" trigger="click" @command="onConfigCommand">
          <el-button size="small">
            配置<el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <!-- 副标题不是装饰：不写出来，它看起来就只是一次无害的补齐 -->
              <el-dropdown-item command="seed">
                <span class="survival-view__menu-item">
                  <span>初始化默认类别</span>
                  <span class="survival-view__menu-note">缺的补齐；已有类别可覆盖口径</span>
                </span>
              </el-dropdown-item>
              <el-dropdown-item command="units">单位维护</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <!-- 缺口对账的入口（v3.59.9）。它原先占着总览正文的一整块，
             现在是页头右侧的一个入口 —— 见文件头「为什么不在正文里」。
             ⚠️ 角标不是装饰：搬进弹窗后，「核心项还没闭合」这个可信度信号
                在页头上没有第二个落点，去掉角标它就等于消失了。
             ⚠️ `v-if` 与四个页签同一条件：迁移没跑 / 表还没建时对账也无从谈起，
                留一个点开只有空壳的入口，比不放更费解。 -->
        <el-button
          v-if="analysis?.available"
          size="small"
          @click="essentialDialogVisible = true"
        >
          必需品缺口对账
          <span
            v-if="essentialEntry.text"
            class="survival-view__entry-badge"
            :class="`survival-view__entry-badge--${essentialEntry.kind}`"
          >{{ essentialEntry.text }}</span>
        </el-button>
      </div>
    </div>

    <!-- 迁移未跑 / 表还没建 —— 是可预期的部署状态，不是错误 -->
    <el-alert
      v-if="analysis && !analysis.available"
      type="info"
      :closable="false"
      show-icon
      class="survival-view__alert"
      :title="analysis.reason ?? '数据尚未就绪'"
    />

    <template v-else>
      <!-- 结论条：首屏最重要的三件事（见文件头，刻意不进页签）。
           四个数各挂一颗 ⓘ（v3.59.10）—— 与四张卡同一套口径来源，
           此前只有卡上有，越靠近答案的那一行反而越不可解释。 -->
      <div class="survival-view__banner">
        <div class="survival-view__banner-main">
          <span class="survival-view__banner-label">综合能撑</span>
          <span class="survival-view__banner-value">{{ formatDays(overallExpected) }}</span>
          <MetricTooltip :meta="bannerMeta('pert_expected')" :width="380" />
          <span v-if="analysis?.shortest_category" class="survival-view__banner-shortest">
            短板「{{ analysis.shortest_category }}」
          </span>
        </div>
        <div class="survival-view__banner-side">
          <span>
            钱能撑
            <b>{{ analysis?.cash.days === null || analysis?.cash.days === undefined
              ? '暂不可算' : formatDays(analysis.cash.days) }}</b>
            <span class="survival-view__banner-note">{{ cashNote }}</span>
            <MetricTooltip :meta="bannerMeta('cash_days')" :width="380" />
          </span>
          <!-- 包一层只为让 ⓘ 贴住标签：它俩是 `.banner-side` 的兄弟时，
               会被那 14px 的行间距推开，看着不像同一件事。 -->
          <span class="survival-view__banner-bottleneck">
            <el-tag :type="bottleneckType(analysis?.bottleneck ?? 'balanced')" size="small" effect="dark">
              {{ analysis?.bottleneck_label || '两端均衡' }}
            </el-tag>
            <MetricTooltip :meta="bannerMeta('bottleneck')" :width="380" />
          </span>
          <span v-if="coverageText" class="survival-view__banner-coverage">
            {{ coverageText }}
            <MetricTooltip :meta="bannerMeta('coverage')" :width="380" />
          </span>
        </div>
      </div>

      <!-- ① 总览 -->
      <div v-show="activeTab === 'overview'" class="survival-view__pane">
        <div class="survival-view__cards">
          <SurvivalCategoryCard
            v-for="row in analysis?.categories ?? []"
            :key="row.category_id"
            :result="row"
            :meta="store.metricMetaByKey[cardMetricKey(row)] ?? null"
            :active="row.category_id === store.activeCategoryId"
            @select="store.setActiveCategory"
          />
          <!-- 入口搬进「配置」下拉后（v3.59.10），这句话必须跟着改指路 ——
               留一个「点『初始化默认类别』」而界面上已经找不到那个按钮，
               是比不放指引更糟的指引。 -->
          <el-empty
            v-if="!(analysis?.categories ?? []).length"
            description="还没有任何类别 —— 先去右上角「配置 → 初始化默认类别」"
            :image-size="80"
          />
        </div>

        <!-- 必需品缺口对账**不在这里** —— 它是另一把尺子上的问题
             （「漏了什么」而不是「够撑多久」），入口在页头右侧。见文件头。 -->

        <div class="survival-view__panel">
          <!-- 明细区标题（v3.59.10）：类别切换已整个交给上面四张卡，
               这一行只声明「现在看的是哪一类」——
               撤掉的那排类别页签原本兼职做这件事，不补回来这块内容就没有标题了。 -->
          <div v-if="activeCategoryName" class="survival-view__detail-head">
            <span class="survival-view__detail-title">{{ activeCategoryName }}</span>
            <span class="survival-view__detail-sub">· 明细</span>
          </div>

          <SurvivalDetailPanel
            :category="store.activeCategoryResult"
            @new-recipe="openRecipeDialog(null)"
            @edit-recipe="openRecipeDialog"
            @delete-recipe="removeRecipe"
            @new-item="openItemDialog(null)"
            @seed-and-new="openRecipeDialog(null)"
            @stocktake-one="openQuickStocktake"
          />
        </div>

        <!-- 配置问题：不是错误，是「这里还会算不准」的说明。
             「看不见的数据」比「错的数据」更危险，所以不做成自动消失的 toast。 -->
        <el-collapse v-if="analysis?.issues.length" class="survival-view__issues">
          <el-collapse-item :name="'issues'">
            <template #title>
              <span class="survival-view__issues-title">
                <el-icon><WarningFilled /></el-icon>
                还有 {{ analysis.issues.length }} 处配置会影响准确性
              </span>
            </template>
            <ul class="survival-view__issues-list">
              <li v-for="(issue, idx) in analysis.issues" :key="idx">
                <span class="survival-view__issue-scope">
                  {{ issue.recipe ? `${issue.category} · ${issue.recipe}` : issue.category }}
                </span>
                <span class="survival-view__issue-message">{{ issue.message }}</span>
                <span v-if="issue.detail" class="survival-view__issue-detail">{{ issue.detail }}</span>
              </li>
            </ul>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- ② 物品清单：跨类别的全量台账 —— **盘点从这里挑物品**（唯一入口） -->
      <div v-show="activeTab === 'ledger'" class="survival-view__pane">
        <SurvivalItemLedger
          @new-item="onLedgerNewItem"
          @edit-item="openItemFromLedger"
          @delete-item="removeItem"
          @stocktake="openStocktake"
          @stocktake-one="openQuickStocktake"
          @use-up="openFlowDialog($event, 'use')"
          @restock="openFlowDialog($event, 'restock')"
        />
      </div>

      <!-- ③ 库存流水：回答「这东西是怎么变少的」—— **只查不登**，
           登记入口长在物品上（清单 / 明细 / 工作表每行），见 SurvivalFlowPanel 文件头 -->
      <div v-show="activeTab === 'flow'" class="survival-view__pane">
        <SurvivalFlowPanel />
      </div>

      <!-- ④ 实盘盘点记录：人数出来的实物数（盘盈盘亏），删记录不回滚库存 -->
      <div v-show="activeTab === 'stocktake'" class="survival-view__pane">
        <!--
          「开始盘点」不再直接开弹窗（v3.60.2）。
          挑物品只留清单页一处，所以这里改成**把你送到清单页并说明怎么挑** ——
          弹窗里那份 43 行的全量表已经撤掉，直接开一个空的它没有意义。
        -->
        <SurvivalStocktakePanel @stocktake="gotoLedgerToPick" />
      </div>

      <!-- ⑤ 生存时长快照：系统算出来的结论，回答「比上次是变长了还是变短了」 -->
      <div v-show="activeTab === 'snapshot'" class="survival-view__pane">
        <SurvivalSnapshotPanel />
      </div>
    </template>

    <!-- 弹窗 -->
    <!-- 缺口对账的壳（v3.59.9）—— 它内部那个新增/编辑弹窗仍归面板自己管 -->
    <SurvivalReconcileDialog v-model:visible="essentialDialogVisible" />
    <SurvivalUnitDialog
      v-model:visible="unitDialogVisible"
      :category-id="store.activeCategoryId"
      :category-name="store.activeCategory?.name ?? ''"
    />
    <SurvivalRecipeDialog
      v-model:visible="recipeDialogVisible"
      :category-id="store.activeCategoryId"
      :recipe-id="editingRecipeId"
    />
    <SurvivalItemDialog
      v-model:visible="itemDialogVisible"
      :category-id="itemDialogCategoryId"
      :item-id="editingItemId"
    />
    <SurvivalStocktakeDialog
      v-model:visible="stocktakeVisible"
      :preset-item-ids="stocktakePreset"
    />
    <!-- 用掉 / 入库（v3.60.18）—— 一次性消耗的登记口。
         它长在物品上（清单每行的两个动作），**不在流水页** —— 见 SurvivalFlowDialog 文件头 -->
    <SurvivalFlowDialog
      v-model:visible="flowDialogVisible"
      :item-id="flowDialogItemId"
      :mode="flowDialogMode"
      :fallback-name="flowDialogFallback.name"
      :fallback-quantity="flowDialogFallback.quantity"
      :fallback-unit-name="flowDialogFallback.unitName"
      @saved="onFlowSaved"
    />
    <!-- 单件盘点（v3.60.2）—— 一次一个数字，匹配「随手抽查一两件」的真实用法 -->
    <SurvivalQuickStocktakeDialog
      v-model:visible="quickStocktakeVisible"
      :item-id="quickStocktakeItemId"
      :fallback-name="quickStocktakeFallback.name"
      :fallback-book-quantity="quickStocktakeFallback.quantity"
      :fallback-unit-name="quickStocktakeFallback.unitName"
      :fallback-restock-threshold="quickStocktakeFallback.restockThreshold"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { Component } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowDown, Box, Camera, Clock, Finished, Odometer, QuestionFilled, Tickets, WarningFilled,
} from '@element-plus/icons-vue'
import MetricTooltip from '../../components/common/MetricTooltip.vue'
import SurvivalCategoryCard from '../../components/survival/SurvivalCategoryCard.vue'
import SurvivalDetailPanel from '../../components/survival/SurvivalDetailPanel.vue'
import SurvivalReconcileDialog from '../../components/survival/SurvivalReconcileDialog.vue'
import SurvivalUnitDialog from '../../components/survival/SurvivalUnitDialog.vue'
import SurvivalRecipeDialog from '../../components/survival/SurvivalRecipeDialog.vue'
import SurvivalItemDialog from '../../components/survival/SurvivalItemDialog.vue'
import SurvivalItemLedger from '../../components/survival/SurvivalItemLedger.vue'
import SurvivalFlowDialog from '../../components/survival/SurvivalFlowDialog.vue'
import SurvivalFlowPanel from '../../components/survival/SurvivalFlowPanel.vue'
import SurvivalStocktakeDialog from '../../components/survival/SurvivalStocktakeDialog.vue'
import SurvivalQuickStocktakeDialog from '../../components/survival/SurvivalQuickStocktakeDialog.vue'
import SurvivalStocktakePanel from '../../components/survival/SurvivalStocktakePanel.vue'
import SurvivalSnapshotPanel from '../../components/survival/SurvivalSnapshotPanel.vue'
import { useSurvivalStore } from '../../stores/survivalStore'
import { useSurvivalFlowStore } from '../../stores/survivalFlowStore'
import { bottleneckType, formatDays } from '../../utils/survivalFormat'
import type { SurvivalCategoryResult } from '../../types/survivalTypes'
import type { RatioMeta } from '../../types/wealthTypes'

const store = useSurvivalStore()

/** 页头副标题 —— 一次性的图例，收进标题旁的 ⓘ（见模板注释） */
const PAGE_SUBTITLE = '物资 = 项目资源 · 生存时长 = 项目周期 · 三年赎回期 = 里程碑'

const analysis = computed(() => store.analysis)
const overallExpected = computed(() => analysis.value?.overall.expected ?? null)

/** 明细区标题上的类别名（v3.59.10）—— 页签行撤掉后由它声明「现在看的是哪一类」 */
const activeCategoryName = computed(
  () => store.activeCategory?.name ?? store.activeCategoryResult?.name ?? '',
)

/**
 * 结论条上各数字的口径气泡（v3.59.10）。
 *
 * 后端 `SURVIVAL_METRIC_NOTES` 一直下发的就是这些键，此前前端只接了卡片
 * （`meal_days` / `life_days` / `survival_days`）、快照面板与对账面板用的那几个 ——
 * 结论条一个都没接，于是**最靠近答案的一行反而是全页唯一没有口径可达性的地方**。
 * 这里仍然只是取用，不写任何一句自己的解释。
 */
function bannerMeta(key: string): RatioMeta | null {
  return store.metricMetaByKey[key] ?? null
}

type SurvivalTabName = 'overview' | 'ledger' | 'flow' | 'stocktake' | 'snapshot'

interface SurvivalTab {
  name: SurvivalTabName
  label: string
  icon: Component
  /** 页签上的角标。空串 = 不显示 —— 不留一个空占位，否则四个页签会一起被撑歪 */
  badge: string
}

/**
 * 默认停在「总览」。
 *
 * 不记上次停在哪一页：本页的产品是「还能撑多久」，
 * 每次进来都该先看到它，而不是上次顺手翻到的那张表。
 */
const activeTab = ref<SurvivalTabName>('overview')

/**
 * 页签角标只挂一个：**该盘几件**。
 *
 * 它是唯一需要用户「现在去做」的事，所以放在有动作的那一页上。
 * 总件数、快照数的角标看着热闹，但看与不看不会改变任何行为，就不加了。
 */
const tabs = computed<SurvivalTab[]>(() => [
  { name: 'overview', label: '总览', icon: Odometer, badge: '' },
  {
    name: 'ledger',
    label: '物品清单',
    icon: Tickets,
    badge: store.dueItems.length ? `该盘 ${store.dueItems.length}` : '',
  },
  { name: 'stocktake', label: '实盘盘点记录', icon: Finished, badge: '' },
  { name: 'snapshot', label: '生存时长快照', icon: Camera, badge: '' },
  // 库存流水（v3.60.18）：回答「这东西是怎么变少的」。
  // 它与「实盘盘点记录」是**两件事**：盘点数是「人核对过的绝对值」，
  // 流水是「每次变化的连续增量」—— 合并之后分不清「被吃掉的」与「被脚本改的」。
  { name: 'flow', label: '库存流水', icon: Clock, badge: '' },
])

/**
 * 页头「必需品缺口对账」入口上的角标（v3.59.9）。
 *
 * 🔴 它承载的是一个**可信度信号**，不是装饰 —— 对账搬进弹窗之后，
 *    「核心项还没闭合」在页头上就没有第二个落点了，而它是
 *    「这份结论能不能用」的唯一提示（它**不折算进天数**：把「还没录」
 *    说成「只够撑 0 天」是另一个错误，见 `SURVIVAL_METRIC_NOTES`）。
 *
 * 三态各自指向**不同的动作**，所以不合并成「有 / 无」：
 *    `''`      对账已闭环，进去只是看一眼
 *    `idle`    还没建基准清单 → 去「初始化基准清单」
 *    `gap`     有核心项没闭合 → 去把它关联 / 录入
 *
 * ⚠️ 数字取 `analysis.essentials.summary`（后端算好的那一份），**不在这里
 *    对 `essentials` 数组自己数一遍** —— 数一遍就会出现「入口说还差 3 项、
 *    弹窗里明明 4 项」这种自相矛盾，而原因仅仅是其中一处忘了刷新
 *    （同 store 里 `essentialReconcile` 的注释）。
 */
type EssentialEntryKind = '' | 'idle' | 'gap'

const essentialEntry = computed<{ text: string; kind: EssentialEntryKind }>(() => {
  const reconcile = store.essentialReconcile
  if (!reconcile) return { text: '', kind: '' }
  if (!reconcile.is_configured) return { text: '待初始化', kind: 'idle' }
  const count = reconcile.summary.unclosed_core_count
  return count > 0 ? { text: `还差 ${count} 项`, kind: 'gap' } : { text: '', kind: '' }
})

/** 缺口对账弹窗（v3.59.9）—— 入口在页头，内容全在组件里 */
const essentialDialogVisible = ref(false)
const unitDialogVisible = ref(false)
const recipeDialogVisible = ref(false)
const itemDialogVisible = ref(false)
const stocktakeVisible = ref(false)
const editingRecipeId = ref<number | null>(null)
const editingItemId = ref<number | null>(null)
/**
 * 物品弹窗要用哪个类别。
 *
 * ⚠️ **必须单独存一份，不能直读 `store.activeCategoryId`**：
 *    从物品清单点「编辑」时，那件物品的类别往往不是当前 tab 停的那一类，
 *    沿用当前类别会让弹窗按错的消耗模式显隐字段 ——
 *    配餐类根本不显示「一份可用天数」，用户会以为那个值丢了。
 */
const itemDialogCategoryId = ref<number | null>(null)
/** 从清单带过去的待盘 id；**空数组 = 没挑东西**（正常入口不会为空，见弹窗里的防御分支） */
const stocktakePreset = ref<number[]>([])
/** 单件盘点（v3.60.2）—— 只盘这一件，不再翻全量弹窗 */
const quickStocktakeVisible = ref(false)
const quickStocktakeItemId = ref<number | null>(null)
/**
 * 单件盘点弹窗打开前**先摆出来的那份**。
 *
 * ⚠️ 它只是「先渲染」用的，不是真源 —— 弹窗会自己按 `item_ids` 拉一次最新账面。
 *    两者不一致时以接口那份为准（同批量弹窗里「账面是参考」的说明）。
 */
const quickStocktakeFallback = ref<{
  name: string
  quantity: number | null
  unitName: string
  restockThreshold: number | null
}>({ name: '', quantity: null, unitName: '', restockThreshold: null })

/**
 * 用掉 / 入库浮层（v3.60.18 · P0）。
 *
 * ⚠️ 与 `openQuickStocktake` 同一套路：父级把**已知的那份**先传给弹窗渲染，
 *    弹窗不为了拿一个数量再打一次接口 —— 数量就在 `store.items` 里。
 *
 * 🔴 与「盘一下」的分工必须守住：
 *    盘点问的是**绝对值**（还剩多少），这两问问的是**变化量**（用掉多少）。
 *    同一个事实的两种说法，永远只问一个（方案 §3.5.1）。
 */
const flowStore = useSurvivalFlowStore()
const flowDialogVisible = ref(false)
const flowDialogItemId = ref<number | null>(null)
const flowDialogMode = ref<'use' | 'restock'>('use')
const flowDialogFallback = ref<{ name: string; quantity: number | null; unitName: string }>(
  { name: '', quantity: null, unitName: '' },
)

function openFlowDialog(itemId: number, mode: 'use' | 'restock') {
  const item = store.items.find((i) => i.id === itemId)
  // 找不到就不开：正常路径下 id 一定来自清单里的一行，
  // 找不到说明这件刚被别处删掉、页面还没刷新
  if (!item) return
  flowDialogItemId.value = itemId
  flowDialogMode.value = mode
  // 数量取**主数据**而不是工作表：工作表是按「参考日期」算出来的视角，
  // 而这里要的是「现在账上写着几件」—— 改的就是它
  flowDialogFallback.value = {
    name: item.name,
    quantity: item.quantity ?? null,
    unitName: item.unit_name ?? '',
  }
  flowDialogVisible.value = true
}

/**
 * 记完一笔之后刷新。
 *
 * 🔴 一次消耗会同时改变三样东西：物品数量、实盘工作表、综合分析 ——
 *    都要重取。只刷物品的话，总览里「还能撑多久」还是旧的，
 *    而它恰恰是这一页的主答案（这也是为什么用 `refreshAll` 而不是 `fetchItems`）。
 *
 * ⚠️ 流水页签用 `bumpRefresh` 通知（而不是让父级直接取数）——
 *    它有自己的筛选条件，父级替它取数会把筛选悄悄重置掉。
 */
async function onFlowSaved() {
  flowStore.bumpRefresh()
  await store.refreshAll()
}

/**
 * 卡片口径气泡取哪一条。
 *
 * 配餐看「配餐可支撑天数」、其余看「耐用品与耗材天数」——
 * 数字一样是「天」，但算法完全不同，用同一段说明会解释错。
 * 数字类额外有「还能读多少小时」，也挂同一颗 ⓘ。
 */
function cardMetricKey(row: SurvivalCategoryResult): string {
  const table: Record<string, string> = {
    meal: 'meal_days',
    depreciation: 'life_days',
    on_demand: 'life_days',
    time_based: 'life_days',
  }
  return table[row.consume_mode] ?? 'survival_days'
}

/** 「钱能撑多久」算不出来时，把原因放在同一行 —— 不能让空值显得像是零 */
const cashNote = computed(() => {
  const cash = analysis.value?.cash
  if (!cash) return ''
  if (cash.days !== null && cash.days !== undefined) return '（应急金月数 × 30）'
  return cash.basis ? `· ${cash.basis}` : ''
})

const coverageText = computed(() => {
  const coverage = analysis.value?.coverage
  if (!coverage) return ''
  if (coverage.pct !== null && coverage.pct !== undefined) {
    return `三年赎回期剩余 ${coverage.remaining_days} 天 · 覆盖率 ${coverage.pct}%`
  }
  return coverage.reason ? `三年覆盖率：${coverage.reason}` : ''
})

/**
 * 参考日期（v3.59.10）。
 *
 * 🔴 空值 = 今天，但**「今天」必须在界面上落成一个具体的日期**。
 *    留一个空框时，「用默认值」与「用户清空了日期」在视觉上是同一个东西，
 *    而且两者得到的分析结果也确实相同 —— 反过来，用户从这个空框里
 *    **无从知道现在算的是哪一天**。同 `formatStocktakeGap` 那条：
 *    空值不许重载两种含义（`''` 就是「今天」，那今天就得说出来）。
 *
 * ⚠️ 只在**未设**时兜底成今天：用户一旦选了日期就以那个为准，
 *    清空（`clearable`）等于回到今天。
 * ⚠️ 用本地日期拼，**不用 `toISOString()`** —— 后者是 UTC，
 *    UTC+8 的凌晨会得到「昨天」，与后端 `date.today()` 对不上。
 * ⚠️ 页面跨过午夜不刷新时，显示的仍是进来那天的日期（后端按新的一天算）。
 *    这是既有边界、不是本次引入的，刷新即恢复。
 */
function localToday(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const todayISO = ref(localToday())
const referenceDateValue = computed(() => store.referenceDate || todayISO.value)

async function onDateChange(value: string | null) {
  await store.setReferenceDate(value ?? '')
}

/**
 * 「配置」下拉的分派（v3.59.10）。
 *
 * 这两项都不高频，其中「初始化默认类别」还是**破坏性的**：类别已存在时
 * 它会问「是否覆盖口径」，点「覆盖」会冲掉界面上改过的消耗模式、聚合口径
 * 与说明文案。它原先和「单位维护」并排占着主按钮位，看着像一次无害的补齐 ——
 * 收进下拉、并在菜单项里把后果写出来，就是这次降权的全部内容。
 */
function onConfigCommand(command: string) {
  if (command === 'units') {
    unitDialogVisible.value = true
    return
  }
  if (command === 'seed') seedDefaults()
}

function openRecipeDialog(id: number | null) {
  if (!store.activeCategoryId) {
    ElMessage.warning('先选一个类别')
    return
  }
  if (!store.activeCategory) return
  if (store.activeCategory.consume_mode !== 'meal') {
    ElMessage.warning(`「${store.activeCategory.name}」不是配餐类，用「新增物品」录入`)
    return
  }
  editingRecipeId.value = id
  recipeDialogVisible.value = true
}

/**
 * 新增 / 编辑物品。
 *
 * `categoryId` 只是**默认值** —— 物品弹窗里类别是第一格、可以改。
 * 这里曾经在打开前就把类别锁死成「总览当前选中的那一类」，
 * 于是从物品清单点「新增物品」永远落进「吃」：想加一件冬衣，
 * 得先关掉弹窗、回总览切到「穿」、再点一次新增。
 */
function openItemDialog(id: number | null, categoryId: number | null = null) {
  editingItemId.value = id
  itemDialogCategoryId.value = categoryId ?? store.activeCategoryId
  itemDialogVisible.value = true
}

/** 从物品清单新增：默认类别跟着清单上筛的那一类走 */
function onLedgerNewItem(categoryId?: number) {
  openItemDialog(null, categoryId ?? null)
}

/** 从物品清单来的编辑：类别跟物品走，不跟 tab 走 */
function openItemFromLedger(id: number, categoryId: number) {
  editingItemId.value = id
  itemDialogCategoryId.value = categoryId
  itemDialogVisible.value = true
}

function openStocktake(itemIds: number[]) {
  stocktakePreset.value = [...itemIds]
  stocktakeVisible.value = true
}

/**
 * 单件盘点（v3.60.2）。
 *
 * ⚠️ 这里传的是「**父级已知的那份**」账面 —— 弹窗先拿它渲染，
 *    同时自己按 `item_ids` 去拉那一件的最新账面覆盖掉。
 *    先渲染再校准，是为了让弹窗**立刻**有内容可看，
 *    而不是先白一屏再跳数字。
 *
 * ⚠️ 找不到就什么都不做：正常路径下 id 一定来自清单里的一行，
 *    找不到说明这件刚被别处删掉、页面还没刷新。
 */
function openQuickStocktake(itemId: number) {
  const item = store.items.find((i) => i.id === itemId)
  const sheet = store.worksheet.find((row) => row.item_id === itemId)
  if (!item && !sheet) return
  quickStocktakeItemId.value = itemId
  quickStocktakeFallback.value = {
    name: sheet?.name ?? item?.name ?? '',
    // 账面以工作表为准（它带着随时间变的列）；工作表没有才退回主数据
    quantity: sheet?.book_quantity ?? item?.quantity ?? null,
    unitName: sheet?.unit_name ?? item?.unit_name ?? '',
    restockThreshold: sheet?.restock_threshold ?? item?.restock_threshold ?? null,
  }
  quickStocktakeVisible.value = true
}

/**
 * 「开始盘点」→ 送去物品清单挑。
 *
 * 盘点弹窗里那份**全量表格已经撤掉**（挑物品只留清单页一处，见设计文档 §五），
 * 所以从一个没有任何预设的地方直接开弹窗只会开出一个空壳。
 * 用一句 toast 说清下一步，而不是让用户自己猜（同硬坑⑫）。
 */
function gotoLedgerToPick() {
  activeTab.value = 'ledger'
  ElMessage.info('在物品清单里勾选要盘的几件，再点「盘点选中的 N 件」')
}

async function removeItem(id: number) {
  const item = store.items.find((i) => i.id === id)
  try {
    await ElMessageBox.confirm(
      `确认删除物品「${item?.name ?? id}」？`
      + '历史盘点与快照里那次记录的名字会保留（那些记录自带当时的名称），'
      + '只是往后不再计入时长与清单。',
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeItem(id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

async function removeRecipe(id: number) {
  const recipe = store.recipes.find((r) => r.id === id)
  try {
    await ElMessageBox.confirm(
      `确认删除配方「${recipe?.name ?? id}」？食材本身不会被删掉，只是不再计入时长。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await store.removeRecipe(id)
    ElMessage.success('已删除')
  } catch (e: unknown) {
    ElMessage.error('删除失败')
  }
}

async function seedDefaults() {
  let created = 0
  try {
    const result = await store.seedDefaults() as { created_categories: number } | undefined
    created = result?.created_categories ?? 0
  } catch {
    ElMessage.error('初始化失败')
    return
  }
  if (created) {
    ElMessage.success(`已建好 ${created} 个默认类别（吃 / 穿 / 用 / 数字 / 医药）`)
    return
  }
  // 类别已存在 ⇒ 刚才那次只**补缺**（缺的单位、缺的基准项），不覆盖已有类别的口径。
  // ⚠️ 但默认口径会随版本变（v3.59.7 把「用」类由求和改为取最小），只在首次创建时生效的话，
  //    老库会一直跑着旧口径 —— 而界面上看不出任何差别，数字也照样「合理」。
  //    所以这里显式问一次；「会冲掉什么」必须写清，别让一次确认变成一次静默覆盖。
  try {
    await ElMessageBox.confirm(
      '默认类别都已存在，刚才只补齐了缺失的单位与基准项。'
      + '要把已有类别的消耗模式、聚合口径与说明文案覆盖为当前默认值吗？'
      + '（会冲掉你在界面上改过的这些内容，以及基准项的性质与提示；已关联的物品不受影响）',
      '覆盖类别口径',
      { type: 'warning', confirmButtonText: '覆盖', cancelButtonText: '保持现状' },
    )
  } catch {
    return
  }
  try {
    const result = await store.seedDefaults(true) as { updated_categories: number } | undefined
    ElMessage.success(`已覆盖 ${result?.updated_categories ?? 0} 个类别的口径`)
  } catch {
    ElMessage.error('覆盖失败')
  }
}

onMounted(() => {
  store.fetchAll()
})

onUnmounted(() => {
  store.resetState()
})
</script>

<style scoped>
.survival-view {
  padding: 16px 20px 32px;
}
/* ── 头部 ──
   标题、页签、页面级配置挤在一行，窄屏靠 flex-wrap 自动折行。
   吸顶：页签就在这一行里，滚下去不该把导航一起滚走。
   底色取页面底色（--lm-bg-secondary）—— 留白带的话，下面的卡片也是白的，
   滚动中分不清哪条是导航。 */
.survival-view__header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  /* 负边距让底色通栏，否则吸顶时两侧会露出滚动上来的卡片 */
  margin: 0 -20px 14px;
  padding: 12px 20px;
  background: var(--lm-bg-secondary);
}
.survival-view__title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.survival-view__title-icon {
  font-size: 18px;
  color: var(--el-color-primary);
}
.survival-view__title {
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}
.survival-view__title-help {
  font-size: 14px;
  color: var(--el-text-color-placeholder);
  cursor: help;
}
.survival-view__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  /* 顶到最右：页签紧跟标题，配置项永远贴边 */
  margin-left: auto;
}
/* 参考日期的说明标签（v3.59.10）—— 一个孤零零的日期框说不清自己是干什么的，
   而它此前连值都没有（占位符写着「默认今天」）就更说不清 */
.survival-view__date-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.survival-view__date {
  /* 180 → 160：给「标题 + 页签 + 配置项」这一行腾出折行余量。
     v3.59.10 又腾了一次：两个低频按钮收进「配置」下拉，净换出约 76px */
  width: 160px;
}
/* 「配置」下拉里的破坏性项：主标题 + 一行小字把后果说出来。
   没有这行副标题时，它看起来就只是一次无害的补齐 */
.survival-view__menu-item {
  display: flex;
  flex-direction: column;
  line-height: 1.5;
}
.survival-view__menu-note {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-view__alert {
  margin-bottom: 14px;
}
.survival-view__banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
  /* 自己不留下间距：首块内容的 16px 由各块自己给 ——
     这样四张卡才会紧贴在「综合能撑」下面，中间不再夹一层导航 */
  margin-bottom: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
}
.survival-view__banner-main {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.survival-view__banner-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.survival-view__banner-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-color-primary);
}
.survival-view__banner-shortest {
  font-size: 13px;
  color: var(--el-color-danger);
}
.survival-view__banner-side {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.survival-view__banner-note,
.survival-view__banner-coverage {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
/* ⓘ 要贴住它解释的那个标签：作为 `.banner-side` 的直接子元素时，
   会被那一行的 14px 间距推开，看着不像同一件事 */
.survival-view__banner-bottleneck {
  display: inline-flex;
  align-items: center;
}

/* ── 页签 ──
   从「独立一行的下划线页签」改成**行内胶囊**：
   下划线样式要有通栏底线才成立，而这一行左边是标题、右边是配置项，
   底线会横穿整条头部。激活色仍是本分组主题色，与 WealthHub 一脉。 */
.survival-view__tabs {
  display: flex;
  gap: 2px;
  flex-wrap: wrap;
}
.survival-view__tab {
  display: flex;
  align-items: center;
  gap: 6px;
  /* 内边距压到 12px：这一行要放下四个页签 + 三个配置项，
     原来 16px 的内边距会让整行正好卡在折行边缘（内容区约 1016px 时） */
  padding: 7px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  transition: all 0.2s;
  user-select: none;
}
.survival-view__tab:hover {
  color: var(--el-text-color-primary);
  background: var(--el-fill-color-light);
}
.survival-view__tab.active {
  color: #f39c12;
  background: rgba(243, 156, 18, 0.12);
  font-weight: 600;
}
.survival-view__tab-icon {
  font-size: 16px;
}
.survival-view__tab-badge {
  padding: 0 6px;
  border-radius: 8px;
  background: var(--el-color-warning);
  color: #fff;
  font-size: 11px;
  font-weight: 400;
  line-height: 16px;
}

/* 页头入口上的角标（v3.59.9）—— 刻意复用页签角标那一套视觉语言：
   同一页上「有个数要你去处理」统一长这样，不为它另造一种。
   `gap` 用警示色（有活要干）、`idle` 用中性色（还没启用，不是警报）。 */
.survival-view__entry-badge {
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 400;
  line-height: 16px;
}
.survival-view__entry-badge--gap {
  background: var(--el-color-warning);
  color: #fff;
}
.survival-view__entry-badge--idle {
  background: var(--el-fill-color-darker);
  color: var(--el-text-color-secondary);
}

.survival-view__cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
  /* 页签条不再给下间距，首块自己给 —— 与另三个面板自带的 16px 对齐 */
  margin-top: 16px;
  margin-bottom: 18px;
}
.survival-view__panel {
  padding: 4px 0;
}
/* 明细区标题（v3.59.10）—— 撤掉那排类别页签之后，这块内容得自己声明标题。
   类别名是主体（与卡片上的名字同字），「· 明细」只是把它和后四个页签里的
   那些面板名区分开 */
.survival-view__detail-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 10px;
}
.survival-view__detail-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.survival-view__detail-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.survival-view__issues {
  margin-top: 16px;
}
.survival-view__issues-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--el-color-warning);
}
.survival-view__issues-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 2;
  color: var(--el-text-color-regular);
}
.survival-view__issue-scope {
  margin-right: 8px;
  color: var(--el-text-color-secondary);
}
.survival-view__issue-message {
  color: var(--el-color-warning);
}
.survival-view__issue-detail {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
}
</style>
