<template>
  <div class="cashflow-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">资产盘点</h1>
        <el-tag type="warning" class="module-tag">资产负债表口径</el-tag>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="handleNewSnapshot">
          <el-icon><Plus /></el-icon>
          新增盘点
        </el-button>
        <el-button @click="switchToMonthly">
          <el-icon><Calendar /></el-icon>
          月度日历
        </el-button>
        <el-button @click="switchToReview">
          <el-icon><DataAnalysis /></el-icon>
          月度复盘
        </el-button>
        <el-button @click="openConfig">
          <el-icon><Setting /></el-icon>
          口径配置
        </el-button>
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 资产全景 + 健康指标 -->
    <el-row :gutter="16" class="cashflow-top-row">
      <el-col :xs="24" :md="16">
        <el-card shadow="never" class="equal-height-card">
          <AssetOverview :overview="store.overview" :loading="store.overviewLoading" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="equal-height-card">
          <HealthMetrics
            :metrics="store.overview?.health_metrics ?? null"
            :ratio-meta="ratioStore.metaByKey"
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- 资产趋势 -->
    <el-card shadow="never" class="section-card">
      <AssetTrend
        :data="store.trendData"
        :months="trendMonths"
        @update:months="handleTrendMonthsChange"
      />
    </el-card>

    <!-- 资产快照（按科目）—— 全页唯一的录入入口与历史列表 -->
    <el-card shadow="never" class="section-card">
      <AssetSnapshotPanel ref="snapshotPanelRef" />
    </el-card>

    <!-- 负债明细台账（逐笔） -->
    <el-card shadow="never" class="section-card">
      <LiabilityPanel />
    </el-card>

    <!-- 应收借出台账（逐笔 · 账龄） -->
    <el-card shadow="never" class="section-card">
      <ReceivablePanel />
    </el-card>

    <!-- 财务规划比率（六项；判定区间由后端下发） -->
    <el-card shadow="never" class="section-card">
      <RatioPanel />
    </el-card>

    <!--
      口径配置抽屉（v3.60.6）。

      「资产科目主数据」与「账单项分类规则」都是**配置项** —— 建库时配一次、
      之后偶尔增删科目或补一条规则。本页的日常动线是「看数 + 记账」，
      两块配置直挂主区，等于每次翻账都要先滚过它们。

      故收进页头右侧这个按钮：默认不渲染（destroy-on-close），点开才挂载。
      ⚠️ 入口可以藏，**引导文案必须跟着改** —— AssetSnapshotPanel 的两处
      空状态提示原先写「先在『资产科目主数据』里……」，已同步指向这里。

      size 用 CSS min()：宽屏 1200px、窄屏 94%。抽屉内两张表都有 fixed 列，
      窄了会挤，所以不取百分比定值。
    -->
    <el-drawer
      v-model="configDrawer"
      size="min(1200px, 94%)"
      destroy-on-close
      @close="handleConfigClose"
    >
      <template #header>
        <div class="config-drawer__header">
          <span class="config-drawer__title">口径配置</span>
          <span class="config-drawer__sub">资产科目主数据 · 账单项分类规则</span>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="config-drawer__tip"
        title="这两块是配置项，日常无需进入"
        description="资产科目决定「按科目录余额」能录哪些项；分类规则决定账单归到收入性质 / 支出刚性 / 现金流哪一类。改动会重算往期归类与六项比率，关闭本抽屉时自动刷新一次。"
      />

      <el-tabs v-model="configTab" class="config-drawer__tabs">
        <el-tab-pane label="资产科目" name="account">
          <AccountPanel />
        </el-tab-pane>
        <el-tab-pane label="分类规则" name="classify">
          <ClassifyRulePanel />
        </el-tab-pane>
      </el-tabs>
    </el-drawer>

  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Refresh, Calendar, DataAnalysis, Setting } from '@element-plus/icons-vue'
import { useCashflowStore } from '../stores/cashflowStore'
import { useDebtStore } from '../stores/debtStore'
import { useAssetStore } from '../stores/assetStore'
import { useClassifyStore } from '../stores/classifyStore'
import { useRatioStore } from '../stores/ratioStore'
import AssetOverview from '../components/cashflow/AssetOverview.vue'
import AssetTrend from '../components/cashflow/AssetTrend.vue'
import HealthMetrics from '../components/cashflow/HealthMetrics.vue'
import LiabilityPanel from '../components/debt/LiabilityPanel.vue'
import ReceivablePanel from '../components/debt/ReceivablePanel.vue'
import AccountPanel from '../components/asset/AccountPanel.vue'
import AssetSnapshotPanel from '../components/asset/AssetSnapshotPanel.vue'
import ClassifyRulePanel from '../components/classify/ClassifyRulePanel.vue'
import RatioPanel from '../components/ratio/RatioPanel.vue'

const router = useRouter()
const store = useCashflowStore()
const debtStore = useDebtStore()
const assetStore = useAssetStore()
const classifyStore = useClassifyStore()
const ratioStore = useRatioStore()

const trendMonths = ref(12)

/**
 * 口径配置抽屉（v3.60.6）。
 *
 * 两个页签对应两块配置面板：资产科目主数据 / 账单项分类规则。
 * 它们与主区的取数**互相独立** —— 面板本身不 onMounted 取数，
 * store 已由本页 onMounted 统一拉过（比率体系要用），故渲染可以安全延迟。
 */
const configDrawer = ref(false)
const configTab = ref<'account' | 'classify'>('account')

function openConfig() {
  configDrawer.value = true
}

/**
 * 关掉抽屉时刷一次比率体系。
 *
 * 科目与规则都是比率的**上游**：改一条规则会让往期归类重算，六项比率随之变。
 * 不刷的话，用户关掉抽屉回到主区看到的仍是旧数 —— 而界面上看不出是旧的。
 */
function handleConfigClose() {
  ratioStore.clearOpeningPosition()
  ratioStore.fetchAll()
}

/**
 * 全页唯一的录入入口。
 *
 * 2026-09-29 之前这里有**两个**「新增盘点」：页头那个写旧表
 * `wealth_cash_flow` 的 8 个硬编码列，面板里那个按科目写新体系。
 * 同一次月末盘点要填两遍，而顶部三块吃旧表、六项比率吃新体系 ——
 * 两块的期次还会分叉（旧表 18 期 vs 新体系 1 期）。
 *
 * 现在统一到按科目的新体系：页头这个按钮只是把面板里的弹窗调起来，
 * **不再自己持有一份表单** —— 入口可以有两个，数据源只能有一个。
 */
const snapshotPanelRef = ref<InstanceType<typeof AssetSnapshotPanel> | null>(null)

function handleNewSnapshot() {
  snapshotPanelRef.value?.openDialog()
}

function switchToMonthly() {
  router.push('/wealth/monthly')
}
function switchToReview() {
  router.push('/wealth/review')
}
function handleRefresh() {
  store.fetchOverview()
  store.fetchTrend(trendMonths.value)
  debtStore.fetchAll()
  assetStore.fetchAll()
  classifyStore.fetchAll()
  // 快照列表归面板自己管，刷新时也要一起重拉
  snapshotPanelRef.value?.refresh()
  // 比率体系依赖资产快照 + 分类规则 + 负债台账 —— 三者任一变了数就变，
  // 故刷新时一起重拉
  ratioStore.clearOpeningPosition()
  ratioStore.fetchAll()
}

function handleTrendMonthsChange(val: number) {
  trendMonths.value = val
  store.fetchTrend(val || 99)
}

onMounted(() => {
  store.fetchOverview()
  store.fetchTrend(12)
  // 负债 / 应收台账与资产快照各自独立取数：改一笔台账不应触发全页重拉
  debtStore.fetchAll()
  // 资产科目与按科目的快照（全页唯一的资产录入体系）同样独立
  assetStore.fetchAll()
  // 账单项分类规则与归类结果 —— 改一条规则会让往期数字重算，故自带取数
  classifyStore.fetchAll()
  // 财务规划比率（六项）—— 依赖上面三者的结果，必须最后拉
  ratioStore.fetchAll()
})
</script>

<style scoped>
.cashflow-view {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}
.module-tag { font-size: 12px; }
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.section-card {
  margin-bottom: 16px;
}
.section-card :deep(.el-card__body) { padding: 20px; }

/* 口径配置抽屉（配置项收口入口） */
.config-drawer__header {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.config-drawer__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.config-drawer__sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.config-drawer__tip { margin-bottom: 12px; }

/* 顶部卡片等高对齐 */
.cashflow-top-row {
  margin-bottom: 16px;
  .el-col {
    display: flex;
  }
}
.equal-height-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  :deep(.el-card__body) {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .header-actions { width: 100%; justify-content: flex-start; }
}
</style>
