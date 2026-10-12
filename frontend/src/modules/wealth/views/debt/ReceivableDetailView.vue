<!--
  应收借出台账（v3.60.20）

  从「资产盘点」（`/wealth/cashflow`）页头按钮进入的**独立页**。
  与「负债明细台账」是同一次拆分（v3.60.20）的两半，结构刻意保持一致。

  ── 为什么要拎出来 ──

  同负债台账：它原先是资产盘点主区的一块，10 列宽表 + 账龄条压在页面中段，
  把主区推得很长，而「逐笔登记借出」是偶发动作。

  ── 入口与回程 ──

  入口：资产盘点页头右侧「应收借出台账」按钮。
  回程：本页右上「返回资产盘点」。
  ⚠️ 本页**不在侧边栏** ⇒ 回程按钮必需。

  ── 路由挂父路径之下 ──

  `/wealth/cashflow/receivable`（同 §45.1 的理由）。

  ── 数据 ──

  面板只从 `debtStore` 读（computed），取数点在本页 onMounted。
  本页**只拉应收这一半**（`fetchReceivables`），不连坐负债 ——
  debtStore 的 fetchAll() 是「负债 + 应收」两个并行请求，此处各取所需。
-->
<template>
  <div class="debt-detail-view">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">应收借出台账</h1>
        <el-tag type="warning" class="module-tag">资产盘点 · 逐笔借出</el-tag>
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
      <ReceivablePanel />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, ArrowLeft } from '@element-plus/icons-vue'
import { useDebtStore } from '../../stores/debtStore'
import ReceivablePanel from '../../components/debt/ReceivablePanel.vue'

const router = useRouter()
const debtStore = useDebtStore()

function goBack() {
  router.push('/wealth/cashflow')
}

function handleRefresh() {
  debtStore.fetchReceivables()
}

onMounted(() => {
  debtStore.fetchReceivables()
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
