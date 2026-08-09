<template>
  <div class="milestone-board">
    <div class="board-header">
      <span class="board-title">
        <el-icon><Flag /></el-icon>
        里程碑 ({{ completedCount }}/{{ milestones.length }})
      </span>
      <span v-if="uniformReward > 0" class="uniform-reward">💰 每项奖励 ¥{{ uniformReward }}</span>
      <el-button text size="small" type="primary" @click="$emit('add')">
        <el-icon><Plus /></el-icon> 添加
      </el-button>
    </div>

    <div class="milestone-list-wrapper">
      <div
        v-for="m in milestones" :key="m.id || m.title"
        class="milestone-item"
        :class="{ completed: m.status === 'completed' }"
      >
        <span class="status-icon" :class="m.status === 'completed' ? 'done' : 'todo'" @click.stop="handleQuickComplete(m)">
          {{ m.status === 'completed' ? '✅' : '○' }}
        </span>
        <span class="milestone-title" :class="{ 'text-done': m.status === 'completed' }">{{ m.title }}</span>
        <span class="milestone-date">
          <template v-if="m.status === 'completed'">
            完成：{{ m.updated_at?.slice(0, 10) || m.target_date?.slice(0, 10) || '--' }}
          </template>
          <template v-else>
            截止：{{ m.target_date?.slice(0, 10) || '未设置' }}
          </template>
        </span>
        <el-button size="small" text @click.stop="$emit('editDetail', m)">✏️</el-button>
      </div>

      <el-empty v-if="!milestones.length" description="暂无里程碑" :image-size="50" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Flag, Plus } from '@element-plus/icons-vue'
import type { Milestone } from '../types/goalTypes'

const props = defineProps<{
  milestones: Milestone[]
}>()

const emit = defineEmits<{
  toggle: [milestone: Milestone, status: string]
  add: []
  editDetail: [milestone: Milestone]
}>()

const completedCount = computed(() => props.milestones.filter(m => m.status === 'completed').length)

const uniformReward = computed(() => {
  const amounts = props.milestones
    .filter(m => {
      const amt = m.reward_amount_display ?? m.reward_amount ?? 0
      return amt > 0
    })
    .map(m => m.reward_amount_display ?? m.reward_amount ?? 0)
  if (amounts.length === 0) return 0
  const first = amounts[0]
  return amounts.every(a => a === first) ? first : 0
})

function handleQuickComplete(m: Milestone) {
  const newStatus = m.status === 'completed' ? 'pending' : 'completed'
  emit('toggle', m, newStatus)
}
</script>

<style scoped lang="scss">
.milestone-board {
  .board-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 12px;
    .board-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 500; flex-shrink: 0; }
    .uniform-reward { font-size: 12px; color: #e6a23c; font-weight: 500; white-space: nowrap; flex-shrink: 0; }
  }

  .milestone-list-wrapper {
    max-height: 400px;
    overflow-y: auto;
    padding-right: 4px;

    &::-webkit-scrollbar { width: 4px; }
    &::-webkit-scrollbar-thumb { background: #ddd; border-radius: 2px; }

    .milestone-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 8px;
      flex-wrap: nowrap;
      border-bottom: 1px solid var(--el-border-color-light);

      &:last-child { border-bottom: none; }

      &.completed {
        background: #f9fafb;
      }

      .status-icon {
        flex-shrink: 0;
        font-size: 14px;
        cursor: pointer;
        transition: transform 0.15s;
        &:hover { transform: scale(1.2); }
        &.done { color: #67c23a; }
        &.todo { color: #ccc; }
      }

      .milestone-title {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: 13px;
        color: #333;

        &.text-done {
          text-decoration: line-through;
          color: #bbb;
        }
      }

      .milestone-date {
        flex-shrink: 0;
        font-size: 12px;
        color: #999;
        white-space: nowrap;
      }
    }
  }
}
</style>
