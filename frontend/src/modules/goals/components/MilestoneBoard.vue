<template>
  <div class="milestone-board">
    <div class="board-header">
      <span class="board-title">
        <el-icon><Flag /></el-icon>
        里程碑 ({{ completedCount }}/{{ milestones.length }})
      </span>
      <el-button text size="small" type="primary" @click="$emit('add')">
        <el-icon><Plus /></el-icon> 添加
      </el-button>
    </div>

    <div class="milestone-list">
      <div
        v-for="m in milestones" :key="m.id || m.title"
        class="milestone-item"
        :class="{ completed: m.status === 'completed' }"
      >
        <div class="milestone-left">
          <el-checkbox
            :model-value="m.status === 'completed'"
            @change="(val: boolean) => handleQuickComplete(m, val)"
            size="small"
          />
        </div>
        <div class="milestone-content">
          <div class="milestone-name">{{ m.title }}</div>
          <div class="milestone-meta">
            <span>截止：{{ m.target_date?.slice(0, 10) || '未设置' }}</span>
            <span v-if="m.reward_amount_display">💰 ¥{{ maskAmount(m.reward_amount_display) }}</span>
            <span :class="m.status === 'completed' ? 'text-success' : 'text-warning'">{{ m.status_display || m.status }}</span>
          </div>
          <div v-if="m.description" class="milestone-desc-preview">📋 {{ m.description.slice(0, 80) }}{{ m.description.length > 80 ? '...' : '' }}</div>
        </div>
        <div class="milestone-right">
          <el-button size="small" text @click.stop="$emit('editDetail', m)">✏️</el-button>
        </div>
      </div>

      <el-empty v-if="!milestones.length" description="暂无里程碑" :image-size="50" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Flag, Plus } from '@element-plus/icons-vue'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import type { Milestone } from '../types/goalTypes'

const props = defineProps<{
  milestones: Milestone[]
}>()

const emit = defineEmits<{
  toggle: [milestone: Milestone, status: string]
  add: []
  editDetail: [milestone: Milestone]
}>()

const { maskAmount } = usePrivacyMask()

const completedCount = computed(() => props.milestones.filter(m => m.status === 'completed').length)

function handleQuickComplete(m: Milestone, checked: boolean) {
  emit('toggle', m, checked ? 'completed' : 'pending')
}
</script>

<style scoped lang="scss">
.milestone-board {
  .board-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
    .board-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 500; }
  }

  .milestone-list { position: relative;

    .milestone-item {
      display: flex; align-items: flex-start; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--el-border-color-light);
      &.completed {
        .milestone-name { text-decoration: line-through; color: var(--el-text-color-placeholder); }
      }

      .milestone-left { padding-top: 2px; }

      .milestone-content { flex: 1; min-width: 0;
        .milestone-name { font-size: 13px; font-weight: 500; line-height: 1.4; }

        .milestone-meta {
          display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px;
          font-size: 11px; color: var(--el-text-color-secondary);
          .text-success { color: var(--el-color-success); font-weight: 500; }
          .text-warning { color: var(--el-color-warning); font-weight: 500; }
        }

        .milestone-desc-preview {
          margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary);
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
      }

      .milestone-right { flex-shrink: 0; padding-top: 0; }
    }
  }
}
</style>
