<!--
  负债明细台账（v3.60.20）

  从「资产盘点」（`/wealth/cashflow`）页头按钮进入的**独立页**。

  ── 为什么要拎出来 ──

  原先这块台账直接嵌在资产盘点主区，与资产全景 / 趋势 / 快照 / 比率面板叠在一起。
  用户的原话是「想在资产盘点右侧点按钮进入」——
  「逐笔登记负债」不是每次盘点都要做的事，它是**偶发动作**，
  却让主区每天都被推长一屏。

  ── 入口与回程 ──

  入口：资产盘点页头右侧「负债明细台账」按钮。
  回程：本页右上「返回资产盘点」。

  ⚠️ 本页**不在侧边栏**（刻意不新增菜单项 —— 它属于资产盘点的下一层，
     不该与「财务管理的平级入口」并列）。因此回程按钮是**必需**的，
     否则用户进来只能靠浏览器后退。

  ── 路由挂父路径之下 ──

  path 写成 `/wealth/cashflow/liability`，而不是 `/wealth/liability`：
  侧边栏高亮用 `route.path.startsWith('/wealth')`，两者都能亮起「财务管理」，
  但挂在父路径之下才表达得出「这是资产盘点的下一层」（§45.1）。

  ── 数据 ──

  面板本身**不取数**（只从 `debtStore` 读 computed），故取数点在本页 onMounted。
  这是刻意的：面板可被任意宿主复用，取数时机由宿主决定。
-->
<template>
  <div class="debt-detail-view">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">负债明细台账</h1>
        <el-tag type="warning" class="module-tag">资产盘点 · 逐笔负债</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" plain @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回资产盘点
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="section-card">
      <LiabilityPanel />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, ArrowLeft } from '@element-plus/icons-vue'
import { useDebtStore } from '../../stores/debtStore'
import LiabilityPanel from '../../components/debt/LiabilityPanel.vue'

const router = useRouter()
const debtStore = useDebtStore()

function goBack() {
  router.push('/wealth/cashflow')
}

function handleRefresh() {
  debtStore.fetchLiabilities()
}

onMounted(() => {
  debtStore.fetchLiabilities()
})
</script>

<style scoped>
.debt-detail-view {
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
.section-card :deep(.el-card__body) { padding: 20px; }

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .header-actions { width: 100%; justify-content: flex-start; }
}
</style>
