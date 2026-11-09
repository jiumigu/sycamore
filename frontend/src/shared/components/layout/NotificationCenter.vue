<template>
  <div class="notification-center">
    <div class="nc-head">
      <span class="nc-title">通知</span>
      <el-button
        v-if="store.unreadCount > 0"
        link
        size="small"
        class="nc-all"
        @click="store.markAllRead()"
      >
        全部已读
      </el-button>
    </div>

    <div v-if="store.loading" class="nc-empty">加载中…</div>
    <div v-else-if="store.loadError" class="nc-empty nc-fail">{{ store.loadError }}</div>
    <div v-else-if="!store.list.length" class="nc-empty">暂无通知</div>

    <ul v-else class="nc-list">
      <li
        v-for="n in store.list"
        :key="n.id"
        :class="['nc-item', `is-${n.category}`, { 'is-unread': !n.is_read }]"
        @click="onClick(n)"
      >
        <div class="nc-item-title">{{ n.title }}</div>
        <div v-if="n.body" class="nc-item-body">{{ n.body }}</div>
        <div class="nc-item-time">{{ timeText(n.created_at) }}</div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import dayjs from 'dayjs'
import { useNotificationStore } from '@/core/notifications/stores/notificationStore'
import type { NotificationItem } from '@/core/notifications/api/notificationApi'

const emit = defineEmits<{
  (e: 'notification-click', notification: NotificationItem): void
}>()

const store = useNotificationStore()

// 每次打开面板都刷一次；后端有 30 分钟节流，重复打开不会反复生成
onMounted(() => { store.refresh() })

function timeText(iso: string): string {
  const t = dayjs(iso)
  return t.isSame(dayjs(), 'day') ? t.format('HH:mm') : t.format('MM-DD HH:mm')
}

function onClick(n: NotificationItem) {
  if (!n.is_read) store.markRead(n.id)
  emit('notification-click', n)
}
</script>

<style scoped lang="scss">
.notification-center {
  width: 320px;
  max-height: 420px;
  display: flex;
  flex-direction: column;
}

.nc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 4px 8px;
  border-bottom: 1px solid var(--lm-border, #ebeef5);

  .nc-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--lm-text-primary, #303133);
  }
}

.nc-empty {
  padding: 28px 0;
  text-align: center;
  font-size: 13px;
  color: var(--lm-text-secondary, #909399);

  &.nc-fail {
    color: var(--el-color-warning, #e6a23c);
  }
}

.nc-list {
  margin: 0;
  padding: 0;
  list-style: none;
  overflow-y: auto;
}

.nc-item {
  padding: 10px 8px;
  cursor: pointer;
  border-bottom: 1px solid var(--lm-border-light, #f2f6fc);

  &:hover {
    background: var(--lm-fill-light, #f5f7fa);
  }

  &.is-unread .nc-item-title {
    font-weight: 600;
  }

  &.is-alert .nc-item-title {
    color: var(--el-color-danger, #f56c6c);
  }

  &.is-reminder .nc-item-title {
    color: var(--el-color-warning, #e6a23c);
  }
}

.nc-item-title {
  font-size: 13px;
  color: var(--lm-text-primary, #303133);
  line-height: 1.4;
}

.nc-item-body {
  margin-top: 2px;
  font-size: 12px;
  color: var(--lm-text-secondary, #909399);
  line-height: 1.4;
}

.nc-item-time {
  margin-top: 4px;
  font-size: 11px;
  color: var(--lm-text-placeholder, #c0c4cc);
}
</style>
