<template>
  <div class="gift-page" v-loading="loading">
    <!-- ========== 页面标题 ========== -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">礼物清单</h1>
        <el-tag type="success" class="module-tag">奖励兑换</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="refreshAll">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          添加礼物
        </el-button>
      </div>
    </div>

    <!-- ========== 统计卡片 ========== -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover" body-style="padding:16px">
          <div class="stat-body">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">全部礼物</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card pending" shadow="hover" body-style="padding:16px">
          <div class="stat-body">
            <div class="stat-value">{{ stats.pending }}</div>
            <div class="stat-label">待兑换</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card waiting" shadow="hover" body-style="padding:16px">
          <div class="stat-body">
            <div class="stat-value">{{ stats.waiting }}</div>
            <div class="stat-label">可兑换</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card redeemed" shadow="hover" body-style="padding:16px">
          <div class="stat-body">
            <div class="stat-value">{{ stats.redeemed }}</div>
            <div class="stat-label">已兑换</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ========== 筛选栏 ========== -->
    <div class="filter-bar">
      <el-radio-group v-model="statusFilter" size="default" @change="onFilterChange">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="pending">待兑换</el-radio-button>
        <el-radio-button value="waiting">可兑换</el-radio-button>
        <el-radio-button value="redeemed">已兑换</el-radio-button>
        <el-radio-button value="cancelled">已取消</el-radio-button>
      </el-radio-group>

      <el-select
        v-model="categoryFilter"
        placeholder="全部分类"
        clearable
        size="default"
        style="width: 140px"
        @change="onFilterChange"
      >
        <el-option
          v-for="opt in categoryOptions"
          :key="opt.value"
          :label="`${opt.icon} ${opt.label}`"
          :value="opt.value"
        />
      </el-select>
    </div>

    <!-- ========== 礼物卡片列表 ========== -->
    <div v-if="giftList.length" class="gift-grid">
      <GiftCard
        v-for="gift in giftList"
        :key="gift.id"
        :gift="gift"
        @redeem="openRedeemDialog"
        @cancel="handleCancel"
        @edit="openEditDialog"
        @delete="handleDelete"
      />
    </div>

    <el-empty v-else description="暂无礼物" :image-size="80" />

    <!-- ========== 表单对话框 ========== -->
    <GiftForm
      :visible="formVisible"
      :gift="editingGift"
      @update:visible="formVisible = $event"
      @submit="handleFormSubmit"
    />

    <!-- ========== 兑换对话框 ========== -->
    <GiftExchangeModal
      :visible="exchangeVisible"
      :gift="exchangingGift"
      :pool-balance="poolBalance"
      @update:visible="exchangeVisible = $event"
      @confirm="handleExchangeConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Refresh, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getGiftList, getGiftStats, getRewardPool,
  createGift, updateGift, deleteGift, redeemGift, cancelGift,
} from '../api/rewardApi'
import type { GiftList, GiftStats } from '../types/rewardTypes'
import { GIFT_CATEGORY_OPTIONS } from '../types/rewardTypes'
import GiftCard from '../components/gift/GiftCard.vue'
import GiftForm from '../components/gift/GiftForm.vue'
import GiftExchangeModal from '../components/gift/GiftExchangeModal.vue'

const loading = ref(false)
const giftList = ref<GiftList[]>([])
const stats = ref<GiftStats>({
  total: 0, pending: 0, waiting: 0, redeemed: 0, cancelled: 0,
  total_expected: 0, total_redeemed: 0,
})
const poolBalance = ref(0)

// 筛选
const statusFilter = ref('')
const categoryFilter = ref('')
const categoryOptions = GIFT_CATEGORY_OPTIONS

// 表单
const formVisible = ref(false)
const editingGift = ref<GiftList | null>(null)

// 兑换
const exchangeVisible = ref(false)
const exchangingGift = ref<GiftList | null>(null)

async function loadGifts() {
  try {
    const params: Record<string, string> = {}
    if (statusFilter.value) params.status = statusFilter.value
    if (categoryFilter.value) params.category = categoryFilter.value
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

async function loadStats() {
  try {
    const res = await getGiftStats()
    stats.value = res.data
  } catch { /* ignore */ }
}

async function loadPool() {
  try {
    const res = await getRewardPool()
    poolBalance.value = Number(res.data.balance) || 0
  } catch { /* ignore */ }
}

async function refreshAll() {
  loading.value = true
  await Promise.all([loadGifts(), loadStats(), loadPool()])
  loading.value = false
}

function onFilterChange() {
  loadGifts()
}

// ────────── 表单操作 ──────────

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
    await refreshAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '操作失败')
  }
}

// ────────── 兑换操作 ──────────

function openRedeemDialog(gift: GiftList) {
  exchangingGift.value = gift
  exchangeVisible.value = true
}

async function handleExchangeConfirm(data: { gift_id: number; actual_reward?: number }) {
  try {
    await redeemGift(data.gift_id, (data.actual_reward ? { actual_reward: data.actual_reward } : {}))
    ElMessage.success('兑换成功！🎉')
    exchangeVisible.value = false
    exchangingGift.value = null
    await refreshAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '兑换失败')
  }
}

// ────────── 取消操作 ──────────

async function handleCancel(gift: GiftList) {
  try {
    await ElMessageBox.confirm(`确定取消「${gift.name}」？`, '取消礼物', {
      type: 'warning',
      confirmButtonText: '确定取消',
      cancelButtonText: '再想想',
    })
    await cancelGift(gift.id)
    ElMessage.success('礼物已取消')
    await refreshAll()
  } catch { /* cancelled */ }
}

// ────────── 删除操作 ──────────

async function handleDelete(gift: GiftList) {
  try {
    await ElMessageBox.confirm(`确定删除「${gift.name}」？删除后不可恢复。`, '删除礼物', {
      type: 'error',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
    })
    await deleteGift(gift.id)
    ElMessage.success('礼物已删除')
    await refreshAll()
  } catch { /* cancelled */ }
}

onMounted(refreshAll)
</script>

<style scoped lang="scss">
.gift-page {
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

    .header-actions {
      display: flex;
      gap: 8px;
    }
  }

  // ========== 统计卡片 ==========
  .stats-row {
    margin-bottom: 20px;
  }

  .stat-card {
    .stat-body {
      text-align: center;

      .stat-value {
        font-size: 28px;
        font-weight: 700;
        color: #303133;
        line-height: 1.2;
        margin-bottom: 4px;
      }

      .stat-label {
        font-size: 13px;
        color: #909399;
      }
    }

    &.pending .stat-value { color: #409EFF; }
    &.waiting .stat-value { color: #67C23A; }
    &.redeemed .stat-value { color: #909399; }
  }

  // ========== 筛选栏 ==========
  .filter-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    background: #fff;
    padding: 12px 16px;
    border-radius: 12px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  }

  // ========== 卡片网格 ==========
  .gift-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }
}
</style>
