<template>
  <div class="inbox-item" :class="{ selected: isSelected, done: item.status === 'done', abandoned: item.status === 'abandoned' }">
    <div v-if="batchMode" class="item-checkbox" @click="toggleSelect">
      <el-checkbox :model-value="isSelected" />
    </div>
    <div class="item-icon">{{ categoryIcon }}</div>
    <div class="item-body" @click="$emit('select')">
      <div class="item-header">
        <span class="item-priority" :style="{ color: priorityColor }">●</span>
        <span class="item-content">{{ item.content }}</span>
        <el-tag v-if="item.status === 'done'" size="small" type="success" effect="plain">已完成</el-tag>
        <el-tag v-else-if="item.status === 'hesitating'" size="small" type="warning" effect="plain">犹豫中</el-tag>
        <el-tag v-else-if="item.status === 'processed'" size="small" type="warning" effect="plain">已处理</el-tag>
        <el-tag v-else-if="item.status === 'archived'" size="small" type="info" effect="plain">已归档</el-tag>
        <el-tag v-else-if="item.status === 'abandoned'" size="small" type="info" effect="plain">已废弃</el-tag>
      </div>
      <div class="item-meta">
        <span v-if="item.description" class="item-desc">{{ item.description }}</span>
        <span class="item-category">{{ categoryLabel }}</span>
        <span v-if="tagList.length" class="item-tags">
          <el-tag v-for="t in tagList" :key="t" size="small" effect="plain">{{ t }}</el-tag>
        </span>
        <span v-if="item.due_date" class="item-due" :class="dueDateUrgency">
          📅 {{ formatDueDate }}
        </span>
        <span class="item-date">{{ dateText }}</span>
        <span
          v-if="item.status === 'hesitating' && item.hesitate_reason"
          class="item-reason item-reason--hesitate"
        >🤔 {{ item.hesitate_reason }}</span>
        <span
          v-if="item.status === 'done' && item.completion_note"
          class="item-reason item-reason--done"
        >📝 {{ item.completion_note }}</span>
        <span
          v-if="item.status === 'abandoned' && item.abandon_reason"
          class="item-reason item-reason--abandoned"
        >🗑️ {{ item.abandon_reason }}</span>
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
            <el-dropdown-item v-if="item.status === 'pending' || item.status === 'hesitating'" command="complete">✅ 标记完成</el-dropdown-item>
            <el-dropdown-item command="convert">🔄 转为...</el-dropdown-item>
            <el-dropdown-item command="resume" v-if="item.status === 'hesitating'">▶️ 开始行动</el-dropdown-item>
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

/** 行上那个日期：**排序键是什么，这里就印什么**（v3.64.82）。
 *
 *  「已完成」列表在后端按 `Coalesce(processed_at, created_at)` 倒序
 *  （`InboxViewSet.filter_queryset`）。这里若还印 `created_at`，
 *  用户看到的就是一串没规律的日期 —— 按完成时间排出来是
 *  10-23 / 10-23 / 10-26，印出来的却是 10-22 / 10-22 / 10-17。
 *
 *  兜底也和后端同一句：没有完成时间（历史数据）就用记下的时间。
 *  🔴 时间是后端下发的本地时间串，只截断，禁 `new Date()`（会差 8h）。
 */
const dateText = computed(() => {
  const raw = props.item.status === 'done'
    ? (props.item.processed_at ?? props.item.created_at)
    : props.item.created_at
  if (!raw) return '—'
  const day = raw.slice(0, 10)
  return props.item.status === 'done' ? `完成于 ${day}` : day
})

const categoryLabel = computed(() => {
  return props.item.category_display
})

const tagList = computed(() => {
  return props.item.tags?.split(',').map(t => t.trim()).filter(Boolean) ?? []
})

const priorityColor = computed(() => {
  return PRIORITY_OPTIONS.find(p => p.value === props.item.priority)?.color ?? '#6B7280'
})

const dueDateUrgency = computed(() => {
  if (!props.item.due_date || props.item.status !== 'pending') return ''
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(props.item.due_date)
  due.setHours(0, 0, 0, 0)
  const diffDays = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays <= 0) return 'overdue'
  if (diffDays <= 2) return 'soon'
  return ''
})

const formatDueDate = computed(() => {
  if (!props.item.due_date) return ''
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(props.item.due_date)
  due.setHours(0, 0, 0, 0)
  const diffDays = Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return `今天截止 ${props.item.due_date}`
  if (diffDays === 1) return `明天截止 ${props.item.due_date}`
  if (diffDays === -1) return `昨天截止 ${props.item.due_date}`
  return `📅 ${props.item.due_date}`
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
.inbox-item.abandoned {
  opacity: 0.6;
  .item-content {
    text-decoration: line-through;
    color: #9CA3AF;
  }
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
.item-tags {
  display: inline-flex;
  gap: 4px;
}
.item-due.overdue {
  color: #EF4444;
  font-weight: 600;
}
.item-due.soon {
  color: #F59E0B;
  font-weight: 600;
}
/* 状态附带的说明（完成备注 / 犹豫原因 / 废弃原因）—— 三者同构，一套样式。
   🔴 它**独占一行、高度跟内容走**：长度不是常量（真实数据里最长 88 字、带 2 个换行），
      挤在日期后面只能截成 280px 的一小截，而右边大半行是空的。
   🔴 也**不设行数上限**：`line-clamp: 2` 只是把截断点往后挪 —— 那条 88 字 3 行的备注
      照样会被切在第 2 行，用户看到的还是半句话。回看类文本按内容给高度，
      多出来的一两行比「省略号」便宜。
      日期那一段仍是「一行里的一小段」，两者不能共用一个宽度规则。 */
.item-reason {
  flex: 1 1 100%;
  min-width: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
.item-reason--hesitate { color: #F59E0B; }
.item-reason--done { color: #10B981; }
.item-reason--abandoned { color: #9CA3AF; }
.item-actions {
  flex-shrink: 0;
}
</style>
