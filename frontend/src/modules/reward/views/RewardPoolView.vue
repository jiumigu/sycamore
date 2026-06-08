<template>
  <div class="reward-page" v-loading="store.loading">
    <!-- ========== 页面标题 ========== -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">快乐银行</h1>
        <el-tag type="warning" class="module-tag">激励机制</el-tag>
      </div>
      <div class="header-actions">
        <el-button size="default" @click="giftDrawerVisible = true">
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
      @deleted="store.refreshAll()"
    />

    <!-- ========== 礼物清单抽屉 ========== -->
    <el-drawer
      v-model="giftDrawerVisible"
      title="🎁 礼物清单"
      size="400px"
      direction="rtl"
    >
      <div class="gift-drawer-body">
        <!-- 统计卡 -->
        <div v-if="store.giftStats" class="drawer-stats">
          <div class="drawer-stat-item">
            <span class="drawer-stat-value">{{ store.giftStats.pending }}</span>
            <span class="drawer-stat-label">待兑换</span>
          </div>
          <div class="drawer-stat-item">
            <span class="drawer-stat-value waiting">{{ store.giftStats.waiting }}</span>
            <span class="drawer-stat-label">可兑换</span>
          </div>
          <div class="drawer-stat-item">
            <span class="drawer-stat-value redeemed">{{ store.giftStats.redeemed }}</span>
            <span class="drawer-stat-label">已兑换</span>
          </div>
        </div>

        <el-divider />

        <!-- 操作按钮 -->
        <div class="drawer-actions">
          <el-button size="small" @click="statusFilter = ''; loadGifts()">全部</el-button>
          <el-button size="small" :type="statusFilter === 'pending' ? 'primary' : ''" @click="statusFilter = 'pending'; loadGifts()">待兑换</el-button>
          <el-button size="small" :type="statusFilter === 'waiting' ? 'success' : ''" @click="statusFilter = 'waiting'; loadGifts()">可兑换</el-button>
          <el-button size="small" type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>

        <!-- 礼物列表 -->
        <div v-if="giftList.length" class="drawer-gift-list">
          <div v-for="gift in giftList" :key="gift.id" class="drawer-gift-item">
            <div class="drawer-gift-icon">{{ categoryIcon(gift.category) }}</div>
            <div class="drawer-gift-body">
              <div class="drawer-gift-top">
                <span class="drawer-gift-name">{{ gift.name }}</span>
                <el-tag :type="statusType(gift.status)" size="small" effect="dark">
                  {{ gift.status_display || gift.status }}
                </el-tag>
              </div>
              <div class="drawer-gift-progress">
                <span class="drawer-gift-price">¥{{ formatMoney(gift.expected_reward) }}</span>
                <el-progress
                  :percentage="Math.min(gift.progress, 100)"
                  :stroke-width="6"
                  :color="gift.progress >= 100 ? '#E6A23C' : '#409EFF'"
                  :show-text="false"
                />
              </div>
              <div class="drawer-gift-actions">
                <el-button v-if="gift.status === 'waiting' && gift.can_redeem" size="small" type="success" @click="openRedeemDialog(gift)">兑换</el-button>
                <el-button v-if="gift.status === 'pending'" size="small" @click="openEditDialog(gift)">编辑</el-button>
                <el-button v-if="gift.status === 'pending'" size="small" type="danger" plain @click="handleDelete(gift)">删除</el-button>
              </div>
            </div>
          </div>
        </div>

        <el-empty v-else description="暂无礼物" :image-size="60" />
      </div>

      <!-- 抽屉内的礼物编辑弹窗 -->
      <GiftForm
        :visible="formVisible"
        :gift="editingGift"
        @update:visible="formVisible = $event"
        @submit="handleFormSubmit"
      />

      <!-- 抽屉内的兑换弹窗 -->
      <GiftExchangeModal
        :visible="exchangeVisible"
        :gift="exchangingGift"
        :pool-balance="store.pool.balance"
        @update:visible="exchangeVisible = $event"
        @confirm="handleExchangeConfirm"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRewardStore } from '../stores/rewardStore'
import { getGiftList, createGift, updateGift, deleteGift, redeemGift, cancelGift } from '../api/rewardApi'
import { GIFT_CATEGORY_OPTIONS, GIFT_STATUS_MAP } from '../types/rewardTypes'
import type { GiftList } from '../types/rewardTypes'
import BalanceCard from '../components/BalanceCard.vue'
import RewardTimeline from '../components/RewardTimeline.vue'
import GiftForm from '../components/gift/GiftForm.vue'
import GiftExchangeModal from '../components/gift/GiftExchangeModal.vue'

const store = useRewardStore()

// 交易流水
const txPage = ref(1)
const txPageSize = ref(10)
const txLoading = ref(false)

const displayTransactions = computed(() => {
  const start = (txPage.value - 1) * txPageSize.value
  return store.transactions.slice(start, start + txPageSize.value)
})

// 礼物抽屉
const giftDrawerVisible = ref(false)
const statusFilter = ref('')
const giftList = ref<GiftList[]>([])

async function loadGifts() {
  try {
    const params: Record<string, string> = {}
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getGiftList(params)
    giftList.value = (res.data || []).map((g: GiftList) => ({
      ...g,
      progress: Number(g.progress) || 0,
      needed: Number(g.needed) || 0,
    }))
  } catch {
    giftList.value = []
  }
}

// 礼物表单
const formVisible = ref(false)
const editingGift = ref<GiftList | null>(null)

function openCreateDialog() {
  editingGift.value = null
  formVisible.value = true
}

function openEditDialog(gift: GiftList) {
  editingGift.value = gift
  formVisible.value = true
}

async function handleFormSubmit(data: Record<string, unknown>) {
  try {
    if (editingGift.value?.id) {
      await updateGift(editingGift.value.id, data)
      ElMessage.success('礼物已更新')
    } else {
      await createGift(data)
      ElMessage.success('礼物已添加')
    }
    formVisible.value = false
    editingGift.value = null
    await Promise.all([loadGifts(), store.fetchGiftStats(), store.fetchPool()])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  }
}

// 兑换
const exchangeVisible = ref(false)
const exchangingGift = ref<GiftList | null>(null)

function openRedeemDialog(gift: GiftList) {
  exchangingGift.value = gift
  exchangeVisible.value = true
}

async function handleExchangeConfirm(data: { gift_id: number; actual_reward?: number }) {
  try {
    await redeemGift(data.gift_id, {
      ...(data.actual_reward ? { actual_reward: data.actual_reward } : {}),
    })
    ElMessage.success('兑换成功！🎉')
    exchangeVisible.value = false
    exchangingGift.value = null
    await Promise.all([loadGifts(), store.refreshAll()])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '兑换失败')
  }
}

// 删除
async function handleDelete(gift: GiftList) {
  try {
    await ElMessageBox.confirm(`确定删除「${gift.name}」？`, '删除礼物', {
      type: 'error',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    await deleteGift(gift.id)
    ElMessage.success('已删除')
    await Promise.all([loadGifts(), store.fetchGiftStats()])
  } catch { /* cancelled */ }
}

// 工具函数
function formatMoney(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return isNaN(n) ? '0.00' : n.toFixed(2)
}

function categoryIcon(cat: string | null | undefined): string {
  const opt = GIFT_CATEGORY_OPTIONS.find(o => o.value === cat)
  return opt?.icon || '🎁'
}

function statusType(status: string) {
  return (GIFT_STATUS_MAP[status]?.type as 'success' | 'warning' | 'info' | 'danger') || 'info'
}

// 打开抽屉时加载礼物列表
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

// ========== 抽屉样式 ==========
.gift-drawer-body {
  height: 100%;
  display: flex;
  flex-direction: column;

  .drawer-stats {
    display: flex;
    gap: 8px;

    .drawer-stat-item {
      flex: 1;
      text-align: center;
      padding: 12px 0;
      background: #f9f9f9;
      border-radius: 10px;

      .drawer-stat-value {
        display: block;
        font-size: 22px;
        font-weight: 700;
        color: #303133;
        margin-bottom: 2px;

        &.waiting { color: #67C23A; }
        &.redeemed { color: #909399; }
      }

      .drawer-stat-label {
        font-size: 12px;
        color: #909399;
      }
    }
  }

  .drawer-actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  .drawer-gift-list {
    flex: 1;
    overflow-y: auto;

    .drawer-gift-item {
      display: flex;
      gap: 10px;
      padding: 12px 0;
      border-bottom: 1px solid #f2f2f2;

      &:last-child { border-bottom: none; }

      .drawer-gift-icon {
        font-size: 24px;
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .drawer-gift-body {
        flex: 1;
        min-width: 0;

        .drawer-gift-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 4px;

          .drawer-gift-name {
            font-size: 14px;
            font-weight: 500;
            color: #303133;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
            margin-right: 8px;
          }
        }

        .drawer-gift-progress {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 6px;

          .drawer-gift-price {
            font-size: 12px;
            color: #F56C6C;
            font-weight: 500;
            white-space: nowrap;
          }

          .el-progress { flex: 1; }
        }

        .drawer-gift-actions {
          display: flex;
          gap: 4px;
        }
      }
    }
  }
}
</style>
