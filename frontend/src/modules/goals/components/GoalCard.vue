<template>
  <div class="goal-card-wrapper">
    <el-card
      class="goal-card"
      :class="{
        'is-completed': goal.status === 'completed',
        'is-archived': goal.status === 'archived',
        'is-expanded': expanded,
        'is-selected': isSelected,
      }"
    >
      <div class="card-click-area" @click="toggleExpand">
        <div class="card-header">
          <div class="header-left">
            <el-checkbox
              :model-value="isSelected"
              @click.stop
              @change="emit('toggleSelect', goal.id)"
              class="goal-checkbox"
            />
            <el-tag :type="priorityTag.type" size="small" class="priority-tag">
              {{ priorityTag.label }}
            </el-tag>
            <el-dropdown @command="handleStatusChange" @click.stop>
              <el-tag :type="statusTag.type" size="small" style="cursor: pointer">
                {{ statusTag.label }}
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-tag>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="opt in STATUS_OPTIONS" :key="opt.value"
                    :command="opt.value"
                    :disabled="opt.value === goal.status"
                  >
                    {{ opt.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <div class="header-right">
            <div class="progress-ring" @click.stop>
              <svg width="40" height="40" viewBox="0 0 40 40">
                <circle cx="20" cy="20" r="16" fill="none" stroke="#eee" stroke-width="3" />
                <circle
                  cx="20" cy="20" r="16" fill="none"
                  :stroke="progressColor" stroke-width="3"
                  stroke-linecap="round"
                  :stroke-dasharray="ringCircumference"
                  :stroke-dashoffset="ringOffset"
                  transform="rotate(-90, 20, 20)"
                />
                <text x="20" y="20" text-anchor="middle" dominant-baseline="central" font-size="9" font-weight="bold" :fill="progressColor">
                  {{ goal.progress_percentage }}%
                </text>
              </svg>
            </div>
            <el-icon class="expand-icon" :class="{ rotated: expanded }">
              <ArrowDown />
            </el-icon>
          </div>
        </div>

        <h3 class="goal-title" @click.stop="emit('showMilestones', goal)">{{ goal.title }}</h3>
        <p v-if="goal.description" class="goal-desc">{{ goal.description }}</p>

        <div class="card-meta">
          <span class="meta-item">
            <el-icon><Calendar /></el-icon>
            {{ goal.deadline ? goal.deadline.slice(0, 10) : '无期限' }}
          </span>
          <span class="meta-item">
            <el-icon><Flag /></el-icon>
            {{ goal.category_display || goal.category }}
          </span>
          <span v-if="goal.year" class="meta-item">
            <el-icon><Clock /></el-icon>
            {{ goal.year }}年
          </span>
          <span v-if="goal.parent_goal_name" class="meta-item parent-badge">
            📎 {{ goal.parent_goal_name }}
          </span>
          <span v-if="goal.sub_goals_count && goal.sub_goals_count > 0" class="meta-item">
            📁 {{ goal.sub_goals_count }}个子目标
          </span>
        </div>

        <div v-if="goal.tags?.length" class="card-tags">
          <el-tag v-for="t in goal.tags.slice(0, 3)" :key="t" size="small" type="info" class="goal-tag">
            {{ t }}
          </el-tag>
          <el-tag v-if="goal.tags.length > 3" size="small" type="info">+{{ goal.tags.length - 3 }}</el-tag>
        </div>
      </div>

      <!-- 展开区 -->
      <transition name="expand">
        <div v-if="expanded" class="card-expanded">
          <el-divider />

          <template v-if="goal.is_tracking_mode && trackingActionId">
            <BehaviorTrackCard
              :goal-id="goal.id"
              :action-id="trackingActionId"
              @checked="$emit('checkin', goal.id)"
            />
          </template>
          <template v-else>
            <MilestoneBoard
              :milestones="goal.milestones || []"
              :goal-actions="[]"
              @toggle="handleMilestoneToggle"
              @add="$emit('edit', goal)"
              @edit-detail="(m: Milestone) => emit('editMilestone', goal, m)"
            />
          </template>
        </div>
      </transition>

      <div class="card-footer">
        <span class="footer-item" @click.stop="emit('showMilestones', goal)">
          🏁 {{ goal.milestone_count ?? 0 }} 里程碑
        </span>
        <span class="footer-item" @click.stop="emit('viewActions', goal)">
          📋 {{ goal.action_count ?? 0 }} 行为记录
        </span>
      </div>
      <div class="card-actions">
        <el-button text size="small" @click.stop="emit('edit', goal)">
          <el-icon><Edit /></el-icon> 编辑
        </el-button>
        <el-button text size="small" @click.stop="emit('clone', goal)">
          <el-icon><CopyDocument /></el-icon> 复制
        </el-button>
        <el-button text size="small" type="danger" @click.stop="emit('delete', goal)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Calendar, Flag, Clock, Edit, Delete, ArrowDown, List, CopyDocument } from '@element-plus/icons-vue'
import { PRIORITY_OPTIONS, STATUS_OPTIONS } from '../types/goalTypes'
import type { Goal, GoalStatus, Milestone } from '../types/goalTypes'
import MilestoneBoard from './MilestoneBoard.vue'
import BehaviorTrackCard from './BehaviorTrackCard.vue'

const props = defineProps<{
  goal: Goal
  isSelected: boolean
  actionsCount: number
  trackingActionId?: number | null
}>()

const emit = defineEmits<{
  edit: [goal: Goal]
  delete: [goal: Goal]
  clone: [goal: Goal]
  expand: [goalId: number]
  milestoneToggle: [goal: Goal, milestone: Milestone, status: string]
  editMilestone: [goal: Goal, milestone: Milestone]
  updateStatus: [goalId: number, status: GoalStatus]
  toggleSelect: [goalId: number]
  viewActions: [goal: Goal]
  showMilestones: [goal: Goal]
  checkin: [goalId: number]
}>()

const expanded = ref(false)

const priorityTag = computed(() => PRIORITY_OPTIONS.find(p => p.value === props.goal.priority) || PRIORITY_OPTIONS[2])
const statusTag = computed(() => STATUS_OPTIONS.find(s => s.value === props.goal.status) || STATUS_OPTIONS[0])

const progressColor = computed(() => {
  const p = props.goal.progress_percentage
  if (p >= 100) return '#67c23a'
  if (p >= 75) return '#409eff'
  if (p >= 50) return '#e6a23c'
  if (p >= 25) return '#f56c6c'
  return '#909399'
})

const circumference = 2 * Math.PI * 16
const ringCircumference = `${circumference}`
const ringOffset = computed(() => circumference - (props.goal.progress_percentage / 100) * circumference)

function toggleExpand() {
  expanded.value = !expanded.value
  if (expanded.value && !props.goal.milestones?.length) {
    emit('expand', props.goal.id)
  }
}

function handleStatusChange(status: string) {
  emit('updateStatus', props.goal.id, status as GoalStatus)
}

function handleMilestoneToggle(m: Milestone, status: string) {
  emit('milestoneToggle', props.goal, m, status)
}
</script>

<style scoped lang="scss">
.goal-card-wrapper { break-inside: avoid; }

.goal-card {
  border-radius: 8px;
  transition: all 0.25s ease;
  cursor: pointer;

  &:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); transform: translateY(-1px); }
  &.is-completed { opacity: 0.75; background-color: var(--el-color-success-light-9); }
  &.is-archived { opacity: 0.6; }
  &.is-expanded { box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12); }
  &.is-selected { box-shadow: 0 0 0 2px var(--el-color-primary); }

  :deep(.el-card__body) { padding: 14px; }

  .card-click-area { cursor: pointer; }

  .card-header {
    display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;
    .header-left { display: flex; gap: 4px; flex-wrap: wrap; align-items: center;
      .goal-checkbox { margin-right: 4px; }
    }

    .header-right { display: flex; align-items: center; gap: 6px;
      .progress-ring { flex-shrink: 0; cursor: default; }
      .expand-icon { font-size: 16px; color: var(--el-text-color-secondary); transition: transform 0.2s;
        &.rotated { transform: rotate(180deg); }
      }
    }
  }

  .goal-title { margin: 0 0 6px; font-size: 15px; font-weight: 600; }
  .goal-desc { margin: 0 0 10px; font-size: 13px; color: var(--el-text-color-secondary); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

  .card-meta { display: flex; gap: 10px; margin-bottom: 6px; font-size: 12px; color: var(--el-text-color-secondary);
    .meta-item { display: flex; align-items: center; gap: 3px; .el-icon { font-size: 12px; } }
    .parent-badge { color: #8e44ad; font-weight: 500; }
  }

  .card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px;
    .goal-tag { margin: 0; font-size: 11px; height: 20px; line-height: 18px; padding: 0 5px; }
  }

  .card-expanded {
    .actions-section { margin-top: 4px; }
  }

  .card-footer { display: flex; gap: 16px; padding: 8px 0 0; font-size: 12px; color: var(--el-text-color-secondary);
    .footer-item { cursor: pointer; &:hover { color: var(--el-color-primary); } }
  }

  .card-actions { display: flex; justify-content: flex-end; gap: 4px; border-top: 1px solid var(--el-border-color-light); padding-top: 8px; margin-top: 8px; }
}

.expand-enter-active, .expand-leave-active { transition: all 0.25s ease; overflow: hidden; }
.expand-enter-from, .expand-leave-to { opacity: 0; max-height: 0; padding-top: 0; }
</style>
