<template>
  <el-card shadow="hover" class="alert-card" v-if="items.length">
    <template #header>
      <div class="alert-header">
        <span>⚠️ 到期提醒</span>
        <el-tag v-if="expiredCount" type="danger" size="small">{{ expiredCount }}笔已过期</el-tag>
      </div>
    </template>
    <div class="alert-list">
      <div
        v-for="item in items"
        :key="item.id"
        class="alert-item"
        :style="{ borderLeftColor: statusConfig(item.status).color }"
      >
        <div class="alert-left">
          <span class="alert-dot" :style="{ background: statusConfig(item.status).color }"></span>
          <div>
            <span class="alert-bank">{{ item.bankinfo || '未知银行' }}</span>
            <span class="alert-amount">{{ formatMoney(item.value) }}</span>
          </div>
        </div>
        <div class="alert-right">
          <span class="alert-date" :style="{ color: statusConfig(item.status).color }">
            {{ statusConfig(item.status).label }} · {{ item.end_date }}
          </span>
          <el-button size="small" type="primary" link @click="$emit('mature', item)">
            {{ item.status === 'expired' ? '处理' : '提醒' }}
          </el-button>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ExpiringItem } from '../../types/wealthTypes'
import { EXPIRING_STATUS_CONFIG } from '../../types/wealthTypes'

const props = defineProps<{
  items: ExpiringItem[]
}>()

defineEmits<{
  mature: [item: ExpiringItem]
}>()

const expiredCount = computed(() => props.items.filter(i => i.status === 'expired').length)

function formatMoney(v: number | null | undefined): string {
  if (v == null) return '¥0'
  const n = Math.round(v)
  if (n >= 10000) return '¥' + (n / 10000).toFixed(1) + '万'
  return '¥' + n.toLocaleString()
}

function statusConfig(status: string): { label: string; color: string; bg: string } {
  return EXPIRING_STATUS_CONFIG[status] || EXPIRING_STATUS_CONFIG.normal
}
</script>

<style scoped>
.alert-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
}
.alert-card :deep(.el-card__body) {
  padding: 8px 16px 12px;
}
.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
}
.alert-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.alert-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #FAFAFA;
  border-radius: 8px;
  border-left: 3px solid;
}
.alert-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.alert-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.alert-bank {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-right: 8px;
}
.alert-amount {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.alert-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.alert-date {
  font-size: 12px;
  font-weight: 500;
}
</style>
