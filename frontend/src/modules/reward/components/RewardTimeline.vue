<template>
  <el-card class="timeline-card">
    <template #header>
      <div class="card-header">
        <span>📋 奖励流水</span>
      </div>
    </template>

    <!-- 紧凑来源分布 -->
    <div v-if="sourceStats" class="source-distribution">
      <span class="source-part milestone">
        <span class="source-emoji">🎯</span>
        里程碑
        <span class="source-amount">¥{{ formatMoney(sourceStats.milestone) }}</span>
        <span class="source-pct">({{ milestonePct }}%)</span>
      </span>
      <span class="source-divider">|</span>
      <span class="source-part sugar">
        <span class="source-emoji">🍰</span>
        小确幸
        <span class="source-amount">¥{{ formatMoney(sourceStats.sugar) }}</span>
        <span class="source-pct">({{ sugarPct }}%)</span>
      </span>
    </div>

    <div v-loading="loading" class="timeline-body">
      <div v-for="tx in transactions" :key="tx.id" class="tx-item">
        <div class="tx-icon" :class="[tx.amount >= 0 ? 'positive' : 'negative', tx.source_type || '']">
          {{ sourceEmoji(tx) }}
        </div>
        <div class="tx-content">
          <div class="tx-top">
            <span class="tx-type">{{ tx.transaction_type_display || tx.transaction_type }}</span>
            <span class="tx-amount" :class="tx.amount >= 0 ? 'positive' : 'negative'">
              {{ tx.amount >= 0 ? '+' : '' }}¥{{ formatMoney(tx.amount) }}
            </span>
          </div>
          <div class="tx-desc">{{ tx.description || '-' }}</div>
          <div class="tx-meta">
            <span class="tx-balance">
              余额: ¥{{ formatMoney(tx.balance_before) }} → ¥{{ formatMoney(tx.balance_after) }}
            </span>
            <span class="tx-time">{{ tx.created_at?.slice(0, 16) || '' }}</span>
          </div>
        </div>
        <el-button
          type="danger"
          size="small"
          text
          :loading="deletingId === tx.id"
          @click="handleDelete(tx)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>

      <el-empty v-if="!transactions.length && !loading" description="暂无流水记录" :image-size="60" />

      <div v-if="total > 0" class="pagination-wrapper">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          :page-sizes="[5, 10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          small
          @size-change="onSizeChange"
          @current-change="onPageChange"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { RewardTransaction, RewardSourceStats } from '../types/rewardTypes'
import { deleteTransaction } from '../api/rewardApi'

const props = defineProps<{
  transactions: RewardTransaction[]
  total: number
  page: number
  pageSize: number
  loading: boolean
  sourceStats?: RewardSourceStats | null
}>()

const milestonePct = computed(() => {
  if (!props.sourceStats || props.sourceStats.total === 0) return 0
  return Math.round((props.sourceStats.milestone / props.sourceStats.total) * 100)
})

const sugarPct = computed(() => {
  if (!props.sourceStats || props.sourceStats.total === 0) return 0
  return Math.round((props.sourceStats.sugar / props.sourceStats.total) * 100)
})

const emit = defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
  'deleted': []
}>()

const deletingId = ref<number | null>(null)

async function handleDelete(tx: RewardTransaction) {
  try {
    await ElMessageBox.confirm(
      `确定要删除这条记录吗？\n\n${tx.description || '-'}\n+¥${tx.amount}`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
    deletingId.value = tx.id
    await deleteTransaction(tx.id)
    ElMessage.success('已删除')
    emit('deleted')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  } finally {
    deletingId.value = null
  }
}

function sourceEmoji(tx: RewardTransaction): string {
  if (tx.source_type === 'milestone') return '🎯'
  if (tx.source_type === 'sugar') return '🍰'
  if (tx.source_type === 'gift') return '🎁'
  return '⭐'
}

function formatMoney(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return isNaN(n) ? '0.00' : n.toFixed(2)
}

function onSizeChange(size: number) {
  emit('update:pageSize', size)
  emit('update:page', 1)
}

function onPageChange(p: number) {
  emit('update:page', p)
}
</script>

<style scoped lang="scss">
.timeline-card {
  margin-bottom: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 14px;
    font-weight: 500;
  }

  .source-distribution {
    padding: 0 20px 12px;
    font-size: 13px;
    color: #909399;
    display: flex;
    align-items: center;
    gap: 10px;
    border-bottom: 1px solid #f2f2f2;

    .source-part {
      display: inline-flex;
      align-items: center;
      gap: 4px;

      .source-emoji { font-size: 14px; }

      .source-amount {
        font-weight: 600;
        color: #606266;
      }

      .source-pct {
        color: #c0c4cc;
        font-size: 12px;
      }
    }

    .source-divider {
      color: #dcdfe6;
      font-size: 12px;
    }
  }

  .timeline-body {
    min-height: 200px;

    .tx-item {
      display: flex;
      gap: 12px;
      padding: 14px 0;
      border-bottom: 1px solid #f2f2f2;

      &:last-child { border-bottom: none; }

      .tx-icon {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        flex-shrink: 0;
        margin-top: 2px;

        &.positive {
          background: rgba(103, 194, 58, 0.1);
          color: #67C23A;
        }

        &.negative {
          background: rgba(245, 108, 108, 0.1);
          color: #F56C6C;
        }
      }

      .tx-content {
        flex: 1;
        min-width: 0;

        .tx-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 2px;

          .tx-type {
            font-size: 13px;
            font-weight: 500;
            color: #303133;
          }

          .tx-amount {
            font-size: 14px;
            font-weight: 600;

            &.positive { color: #67C23A; }
            &.negative { color: #F56C6C; }
          }
        }

        .tx-desc {
          font-size: 12px;
          color: #606266;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          margin-bottom: 2px;
        }

        .tx-meta {
          display: flex;
          justify-content: space-between;
          align-items: center;

          .tx-balance {
            font-size: 11px;
            color: #c0c4cc;
          }

          .tx-time {
            font-size: 11px;
            color: #c0c4cc;
            white-space: nowrap;
          }
        }
      }
    }
  }

  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>
