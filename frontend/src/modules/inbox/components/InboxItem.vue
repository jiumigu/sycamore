<template>
  <div class="inbox-item" :class="{ selected: isSelected, done: item.status === 'done' }">
    <div v-if="batchMode" class="item-checkbox" @click="toggleSelect">
      <el-checkbox :model-value="isSelected" />
    </div>
    <div class="item-icon">{{ categoryIcon }}</div>
    <div class="item-body" @click="$emit('select')">
      <div class="item-header">
        <span class="item-priority" :style="{ color: priorityColor }">●</span>
        <span class="item-content">{{ item.content }}</span>
        <el-tag v-if="item.status === 'done'" size="small" type="success" effect="plain">已完成</el-tag>
        <el-tag v-else-if="item.status === 'processed'" size="small" type="warning" effect="plain">已处理</el-tag>
        <el-tag v-else-if="item.status === 'archived'" size="small" type="info" effect="plain">已归档</el-tag>
      </div>
      <div class="item-meta">
        <span v-if="item.description" class="item-desc">{{ item.description }}</span>
        <span class="item-category">{{ categoryLabel }}</span>
        <span v-if="item.due_date" class="item-due" :class="{ overdue: isOverdue }">
          📅 {{ item.due_date }}
        </span>
        <span class="item-date">{{ item.created_at?.slice(0, 10) }}</span>
        <span v-if="item.status === 'done' && item.completion_note" class="item-completion-note">
          📝 {{ item.completion_note }}
        </span>
      </div>
    </div>
    <div class="item-actions">
      <el-dropdown trigger="click" @command="(cmd: string) => $emit('action', cmd)">
        <el-button size="small" circle>
          <el-icon><MoreFilled /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="edit">✏️ 编辑</el-dropdown-item>
            <el-dropdown-item v-if="item.status === 'pending'" command="complete">✅ 标记完成</el-dropdown-item>
            <el-dropdown-item command="convert">🔄 转为...</el-dropdown-item>
            <el-dropdown-item command="delete" divided>🗑️ 删除</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MoreFilled } from '@element-plus/icons-vue'
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS } from '../types/inboxTypes'
import type { InboxItem } from '../types/inboxTypes'

const props = defineProps<{
  item: InboxItem
  batchMode: boolean
  selected: boolean
}>()

const emit = defineEmits<{
  select: []
  action: [cmd: string]
}>()

const categoryIcon = computed(() => {
  return CATEGORY_OPTIONS.find(c => c.value === props.item.category)?.icon ?? '📌'
})

const categoryLabel = computed(() => {
  return props.item.category_display
})

const priorityColor = computed(() => {
  return PRIORITY_OPTIONS.find(p => p.value === props.item.priority)?.color ?? '#6B7280'
})

const isOverdue = computed(() => {
  if (!props.item.due_date || props.item.status !== 'pending') return false
  return new Date(props.item.due_date) < new Date()
})

const isSelected = computed(() => props.selected)

function toggleSelect() {
  emit('select')
}
</script>

<style scoped>
.inbox-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  background: #fff;
  transition: all 0.2s;
}
.inbox-item:hover {
  border-color: #3B82F6;
  box-shadow: 0 1px 4px rgba(59,130,246,0.1);
}
.inbox-item.selected {
  background: #EFF6FF;
  border-color: #3B82F6;
}
.inbox-item.done {
  opacity: 0.6;
}
.item-checkbox {
  padding-top: 2px;
  cursor: pointer;
}
.item-icon {
  font-size: 18px;
  padding-top: 2px;
  flex-shrink: 0;
}
.item-body {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.item-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.item-priority {
  font-size: 10px;
}
.item-content {
  font-size: 14px;
  font-weight: 500;
  color: #1F2937;
}
.item-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: #6B7280;
  flex-wrap: wrap;
}
.item-desc {
  color: #9CA3AF;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-due.overdue {
  color: #EF4444;
  font-weight: 600;
}
.item-completion-note {
  color: #10B981;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-actions {
  flex-shrink: 0;
}
</style>
