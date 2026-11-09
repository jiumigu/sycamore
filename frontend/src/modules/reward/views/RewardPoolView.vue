<template>
  <div class="reward-page" v-loading="store.loading">
    <!-- ========== 页面标题 ========== -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">快乐银行</h1>
        <el-tag type="warning" class="module-tag">激励机制</el-tag>
      </div>
      <div class="header-actions">
        <!-- v3.63.11：这里原来是「打开抽屉」——抽屉与独立页 `/reward/gifts` 是两套实现，
             菜单项撤掉之后统一走独立页，不再维护抽屉那一份。 -->
        <el-button size="default" @click="$router.push('/reward/gifts')">
          🎁 礼物清单
        </el-button>
        <el-button size="default" @click="store.refreshAll()">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- ========== 奖励池卡片 ========== -->
    <BalanceCard :pool="store.pool" />

    <!-- ========== 来源筛选 ========== -->
    <el-card shadow="hover" class="filter-card">
      <div class="filter-row">
        <span class="filter-label">来源</span>
        <el-radio-group v-model="filterSource" size="small">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="sugar">🍰 小确幸</el-radio-button>
          <el-radio-button value="milestone">🎯 里程碑</el-radio-button>
          <el-radio-button value="goal_complete">🎉 目标完成</el-radio-button>
          <el-radio-button value="inbox_complete">📥 收件箱完成</el-radio-button>
        </el-radio-group>
      </div>
    </el-card>

    <!-- ========== 奖励流水（含紧凑来源比例行） ========== -->
    <RewardTimeline
      :transactions="displayTransactions"
      :total="store.txTotal"
      :page="txPage"
      :page-size="txPageSize"
      :loading="txLoading"
      :source-stats="store.sourceStats"
      @update:page="txPage = $event"
      @update:page-size="txPageSize = $event"
      @deleted="handleDeleted"
    />

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { useRewardStore } from '../stores/rewardStore'
import BalanceCard from '../components/BalanceCard.vue'
import RewardTimeline from '../components/RewardTimeline.vue'

const store = useRewardStore()

// 来源筛选
const filterSource = ref('')

watch(filterSource, () => {
  txPage.value = 1
  fetchFilteredTransactions()
})

function fetchFilteredTransactions() {
  const params: Record<string, unknown> = { page: 1, page_size: 1000 }
  if (filterSource.value) params.source_type = filterSource.value
  store.fetchTransactions(params)
}

function handleDeleted() {
  fetchFilteredTransactions()
  store.fetchSourceStats()
  store.fetchPool()
}

// 交易流水
const txPage = ref(1)
const txPageSize = ref(10)
const txLoading = ref(false)

const displayTransactions = computed(() => {
  const start = (txPage.value - 1) * txPageSize.value
  return store.transactions.slice(start, start + txPageSize.value)
})

// 进页面即拉取奖励池 / 来源占比 / 流水
onMounted(() => {
  store.refreshAll()
})
</script>

<style scoped lang="scss">
.reward-page {
  padding: 20px;
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      .page-title {
        margin: 0;
        font-size: 24px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }

      .module-tag { font-size: 12px; }
    }

    .header-actions { display: flex; gap: 8px; }
  }
}

// ========== 筛选卡片 ==========
.filter-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
}
.filter-card :deep(.el-card__body) {
  padding: 12px 16px;
}
.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.filter-label {
  font-size: 13px;
  color: #606266;
  flex-shrink: 0;
}

</style>
