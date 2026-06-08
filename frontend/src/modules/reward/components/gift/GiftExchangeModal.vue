<template>
  <el-dialog
    :model-value="visible"
    title="兑换礼物"
    width="420px"
    :close-on-click-modal="false"
    @update:model-value="$emit('update:visible', $event)"
  >
    <div v-if="gift" class="exchange-body">
      <div class="gift-summary">
        <div class="summary-icon">{{ categoryIcon }}</div>
        <div class="summary-info">
          <h3>{{ gift.name }}</h3>
          <p class="summary-price">参考价格 ¥{{ formatMoney(gift.expected_reward) }}</p>
        </div>
      </div>

      <el-divider />

      <div class="balance-info">
        <div class="info-row">
          <span>当前奖励池余额</span>
          <span class="balance-value">¥{{ formatMoney(poolBalance) }}</span>
        </div>
        <div class="info-row">
          <span>兑换后余额</span>
          <span class="balance-value after" :class="{ insufficient: remaining < 0 }">
            ¥{{ formatMoney(remaining) }}
          </span>
        </div>
      </div>

      <div v-if="gift.status !== 'waiting'" class="warning-text">
        礼物当前状态不可兑换
      </div>

      <el-form
        v-else
        ref="formRef"
        :model="form"
        label-width="90px"
        class="exchange-form"
      >
        <el-form-item label="实际金额">
          <el-input-number
            v-model="form.actual_reward"
            :min="0.01"
            :max="gift.expected_reward"
            :precision="2"
            :step="10"
            placeholder="留空则使用参考价格"
            clearable
            style="width: 100%"
          />
          <div class="form-tip">留空则按参考价格 {{ formatMoney(gift.expected_reward) }} 扣除</div>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button
        type="success"
        :loading="submitting"
        :disabled="!gift || gift.status !== 'waiting' || remaining < 0"
        @click="handleConfirm"
      >
        确认兑换
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import type { GiftList } from '../../types/rewardTypes'

const props = defineProps<{
  visible: boolean
  gift: GiftList | null
  poolBalance: number
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [data: { gift_id: number; actual_reward?: number }]
}>()

const form = reactive({
  actual_reward: undefined as number | undefined,
})

const submitting = ref(false)
const formRef = ref()

const categoryIcons: Record<string, string> = {
  physical: '📚',
  experience: '✈️',
  virtual: '🎫',
  other: '🎁',
}
const categoryIcon = computed(() => categoryIcons[props.gift?.category || 'other'] || '🎁')

const remaining = computed(() => {
  if (!props.gift) return 0
  const deduct = form.actual_reward || props.gift.expected_reward
  return props.poolBalance - deduct
})

function formatMoney(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return isNaN(n) ? '0.00' : n.toFixed(2)
}

function handleConfirm() {
  if (!props.gift) return
  submitting.value = true
  emit('confirm', {
    gift_id: props.gift.id,
    ...(form.actual_reward ? { actual_reward: form.actual_reward } : {}),
  })
}
</script>

<style scoped lang="scss">
.exchange-body {
  .gift-summary {
    display: flex;
    align-items: center;
    gap: 16px;

    .summary-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      background: rgba(64, 158, 255, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
      flex-shrink: 0;
    }

    .summary-info {
      flex: 1;

      h3 {
        margin: 0 0 4px;
        font-size: 16px;
        color: #303133;
      }

      .summary-price {
        margin: 0;
        font-size: 13px;
        color: #F56C6C;
        font-weight: 500;
      }
    }
  }

  .balance-info {
    margin: 16px 0;

    .info-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      font-size: 14px;
      color: #606266;

      .balance-value {
        font-weight: 600;
        color: #303133;

        &.after {
          &.insufficient {
            color: #F56C6C;
          }
        }
      }
    }
  }

  .warning-text {
    color: #F56C6C;
    font-size: 13px;
    text-align: center;
    padding: 12px;
    background: rgba(245, 108, 108, 0.05);
    border-radius: 8px;
  }

  .exchange-form {
    margin-top: 12px;

    .form-tip {
      font-size: 11px;
      color: #909399;
      margin-top: 4px;
    }
  }
}
</style>
