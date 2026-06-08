<template>
  <el-row :gutter="20" class="balance-row">
    <el-col :span="8">
      <el-card class="balance-card available" shadow="hover">
        <div class="card-body">
          <div class="card-icon">
            <el-icon><Wallet /></el-icon>
          </div>
          <div class="card-info">
            <div class="card-label">当前余额</div>
            <div class="card-value">¥{{ formatMoney(pool.balance) }}</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card class="balance-card earned" shadow="hover">
        <div class="card-body">
          <div class="card-icon">
            <el-icon><Star /></el-icon>
          </div>
          <div class="card-info">
            <div class="card-label">累计获得</div>
            <div class="card-value">¥{{ formatMoney(pool.total_earned) }}</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card class="balance-card withdrawn" shadow="hover">
        <div class="card-body">
          <div class="card-icon">
            <el-icon><SuccessFilled /></el-icon>
          </div>
          <div class="card-info">
            <div class="card-label">累计提取</div>
            <div class="card-value">¥{{ formatMoney(pool.total_withdrawn) }}</div>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import type { RewardPool } from '../types/rewardTypes'
import { Wallet, Star, SuccessFilled } from '@element-plus/icons-vue'

defineProps<{ pool: RewardPool }>()

function formatMoney(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return isNaN(n) ? '0.00' : n.toFixed(2)
}
</script>

<style scoped lang="scss">
.balance-row {
  margin-bottom: 20px;
}

.balance-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-4px);
  }

  .card-body {
    display: flex;
    align-items: center;
    gap: 16px;

    .card-icon {
      width: 50px;
      height: 50px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
      flex-shrink: 0;
    }

    .card-info {
      flex: 1;

      .card-label {
        font-size: 14px;
        color: #909399;
        margin-bottom: 4px;
      }

      .card-value {
        font-size: 26px;
        font-weight: 700;
        color: #303133;
      }
    }
  }

  &.available .card-icon {
    background: rgba(64, 158, 255, 0.1);
    color: #409EFF;
  }

  &.earned .card-icon {
    background: rgba(103, 194, 58, 0.1);
    color: #67C23A;
  }

  &.withdrawn .card-icon {
    background: rgba(245, 108, 108, 0.1);
    color: #F56C6C;
  }
}
</style>
