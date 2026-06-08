<template>
  <div class="gift-card" :class="[`status-${gift.status}`]" @click="$emit('click', gift)">
    <!-- 顶部：分类图标 + 状态标签 -->
    <div class="card-top">
      <div class="category-badge" :style="{ background: categoryColor + '20', color: categoryColor }">
        {{ categoryIcon }}
      </div>
      <el-tag
        :type="statusTagType"
        size="small"
        effect="dark"
        class="status-tag"
      >
        {{ gift.status_display || gift.status }}
      </el-tag>
    </div>

    <!-- 礼品图 -->
    <div v-if="gift.image_url" class="card-image">
      <img :src="gift.image_url" :alt="gift.name" @error="onImageError" />
    </div>

    <!-- 名称 + 价格 -->
    <div class="card-body">
      <h3 class="gift-name" :title="gift.name">{{ gift.name }}</h3>
      <div class="gift-price">
        <span class="price-label">参考价格</span>
        <span class="price-value">¥{{ formatMoney(gift.expected_reward) }}</span>
      </div>

      <!-- 进度条 -->
      <div class="progress-section">
        <div class="progress-header">
          <span class="progress-label">
            {{ gift.status === 'redeemed' ? '已兑换' : gift.status === 'cancelled' ? '已取消' : '进度' }}
          </span>
          <span class="progress-pct">{{ gift.progress }}%</span>
        </div>
        <el-progress
          :percentage="Math.min(gift.progress, 100)"
          :stroke-width="8"
          :color="progressColor"
          :show-text="false"
        />
        <div v-if="gift.status === 'pending' || gift.status === 'waiting'" class="needed">
          还差 ¥{{ formatMoney(gift.needed) }}
        </div>
      </div>

      <!-- 备注 -->
      <p v-if="gift.notes" class="gift-notes">{{ gift.notes }}</p>
    </div>

    <!-- 操作按钮 -->
    <div class="card-actions" @click.stop>
      <el-button
        v-if="gift.status === 'waiting' && gift.can_redeem"
        type="success"
        size="small"
        @click="$emit('redeem', gift)"
      >
        兑换
      </el-button>
      <el-button
        v-if="gift.status === 'waiting'"
        size="small"
        @click="$emit('cancel', gift)"
      >
        取消
      </el-button>
      <el-button
        v-if="gift.status === 'pending'"
        size="small"
        plain
        @click="$emit('edit', gift)"
      >
        编辑
      </el-button>
      <el-button
        v-if="gift.status === 'pending'"
        size="small"
        type="danger"
        plain
        @click="$emit('delete', gift)"
      >
        删除
      </el-button>
      <el-button
        v-if="gift.status === 'cancelled'"
        size="small"
        plain
        @click="$emit('edit', gift)"
      >
        重新启用
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { GiftList } from '../../types/rewardTypes'
import { GIFT_CATEGORY_OPTIONS, GIFT_STATUS_MAP } from '../../types/rewardTypes'

const props = defineProps<{
  gift: GiftList
}>()

defineEmits<{
  click: [gift: GiftList]
  redeem: [gift: GiftList]
  cancel: [gift: GiftList]
  edit: [gift: GiftList]
  delete: [gift: GiftList]
}>()

function formatMoney(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return isNaN(n) ? '0.00' : n.toFixed(2)
}

const categoryColors: Record<string, string> = {
  physical: '#409EFF',
  experience: '#E6A23C',
  virtual: '#67C23A',
  other: '#909399',
}

const categoryIcons: Record<string, string> = {
  physical: '📚',
  experience: '✈️',
  virtual: '🎫',
  other: '🎁',
}

const categoryColor = categoryColors[props.gift.category || 'other'] || '#909399'
const categoryIcon = categoryIcons[props.gift.category || 'other'] || '🎁'

const statusTagType = GIFT_STATUS_MAP[props.gift.status]?.type as
  | 'info' | 'success' | 'primary' | 'danger' | 'warning' | undefined || 'info'

const progressColor = computed(() => {
  if (props.gift.status === 'redeemed') return '#67C23A'
  if (props.gift.status === 'cancelled') return '#909399'
  if (props.gift.progress >= 100) return '#E6A23C'
  return '#409EFF'
})

import { computed } from 'vue'

function onImageError(e: Event) {
  const el = e.target as HTMLImageElement
  el.style.display = 'none'
}
</script>

<style scoped lang="scss">
.gift-card {
  background: #fff;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: all 0.3s;
  cursor: pointer;
  display: flex;
  flex-direction: column;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  }

  &.status-redeemed {
    opacity: 0.75;
  }

  &.status-cancelled {
    opacity: 0.55;
  }

  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .category-badge {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }

    .status-tag {
      flex-shrink: 0;
    }
  }

  .card-image {
    margin-bottom: 12px;
    border-radius: 8px;
    overflow: hidden;
    max-height: 140px;

    img {
      width: 100%;
      height: 140px;
      object-fit: cover;
      display: block;
    }
  }

  .card-body {
    flex: 1;

    .gift-name {
      margin: 0 0 8px;
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .gift-price {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      .price-label {
        font-size: 12px;
        color: #909399;
      }

      .price-value {
        font-size: 18px;
        font-weight: 700;
        color: #F56C6C;
      }
    }

    .progress-section {
      margin-bottom: 8px;

      .progress-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;

        .progress-label {
          font-size: 12px;
          color: #909399;
        }

        .progress-pct {
          font-size: 12px;
          font-weight: 600;
          color: #606266;
        }
      }

      .needed {
        margin-top: 4px;
        font-size: 11px;
        color: #E6A23C;
      }
    }

    .gift-notes {
      margin: 8px 0 0;
      font-size: 12px;
      color: #909399;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }

  .card-actions {
    display: flex;
    gap: 6px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #f2f2f2;
    flex-wrap: wrap;
  }
}
</style>
