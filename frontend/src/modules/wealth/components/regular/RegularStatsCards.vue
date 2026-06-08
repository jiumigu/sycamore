<template>
  <el-row :gutter="16" class="stats-row">
    <el-col :span="6">
      <el-card shadow="hover" class="stat-card">
        <div class="stat-body">
          <div class="stat-icon" style="background: #D1FAE5; color: #059669">💵</div>
          <div>
            <div class="stat-value">{{ maskAmount(stats?.total_value, privacyStore.privacyMode) }}</div>
            <div class="stat-label">存款总额</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="hover" class="stat-card">
        <div class="stat-body">
          <div class="stat-icon" style="background: #DBEAFE; color: #2563EB">🏦</div>
          <div>
            <div class="stat-value">{{ maskAmount(stats?.ongoing_value, privacyStore.privacyMode) }}</div>
            <div class="stat-label">未到期 ({{ stats?.ongoing_count }}笔)</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="hover" class="stat-card">
        <div class="stat-body">
          <div class="stat-icon" style="background: #FEF3C7; color: #D97706">⏰</div>
          <div>
            <div class="stat-value">{{ maskAmount(stats?.matured_value, privacyStore.privacyMode) }}</div>
            <div class="stat-label">已到期 ({{ stats?.matured_count }}笔)</div>
          </div>
        </div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="hover" class="stat-card">
        <div class="stat-body">
          <div class="stat-icon" style="background: #FCE4EC; color: #DB2777">💹</div>
          <div>
            <div class="stat-value">{{ maskAmount(stats?.total_interest, privacyStore.privacyMode) }}</div>
            <div class="stat-label">预计总利息</div>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { maskAmount } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import type { RegularStats } from '../../types/wealthTypes'

defineProps<{
  stats: RegularStats | null
}>()

const privacyStore = usePrivacyStore()
</script>

<style scoped>
.stats-row {
  margin-bottom: 16px;
}
.stat-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
}
.stat-card :deep(.el-card__body) {
  padding: 16px;
}
.stat-body {
  display: flex;
  align-items: center;
  gap: 12px;
}
.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
</style>
