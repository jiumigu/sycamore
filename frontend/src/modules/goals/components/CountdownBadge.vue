<template>
  <span class="countdown-badge" :class="badgeClass">
    <span v-if="days === null" class="no-date">无截止日期</span>
    <span v-else-if="days <= 0" class="expired">⏰ 已过期</span>
    <span v-else-if="days <= 3" class="urgent">🔥 {{ days }} 天</span>
    <span v-else-if="days <= 7" class="warning">⚠️ {{ days }} 天</span>
    <span v-else class="normal">📅 {{ days }} 天</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  days: number | null
}>()

const badgeClass = computed(() => {
  if (props.days === null) return ''
  if (props.days <= 0) return 'expired'
  if (props.days <= 3) return 'urgent'
  if (props.days <= 7) return 'warning'
  return 'normal'
})
</script>

<style scoped>
.countdown-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;

  &.normal {
    background: #ecf5ff;
    color: #409eff;
  }

  &.warning {
    background: #fdf6ec;
    color: #e6a23c;
  }

  &.urgent {
    background: #fef0f0;
    color: #f56c6c;
    animation: pulse 1.5s ease-in-out infinite;
  }

  &.expired {
    background: #fef0f0;
    color: #f56c6c;
  }

  .no-date {
    color: var(--el-text-color-secondary);
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>
