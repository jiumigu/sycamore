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
        :class="{ completed: m.status === 'completed', expanded: expandedId === m.id }"
      >
        <div class="milestone-connector">
          <div class="dot" :class="{
            done: m.status === 'completed',
            progress: m.status === 'in-progress',
          }" />
          <div class="line" />
        </div>

        <div class="milestone-body">
          <div class="milestone-top">
            <el-checkbox
              :model-value="m.status === 'completed'"
              @change="handleToggle(m)"
              size="small"
            />
            <span class="milestone-title" @click="toggleExpand(m)">{{ m.title }}</span>
            <!-- 备注编辑 -->
            <el-popover
              trigger="click"
              :visible="notePopoverVisible[m.id]"
              @show="initNote(m)"
              @hide="notePopoverVisible[m.id] = false"
              placement="top"
              :width="280"
            >
              <template #reference>
                <el-button
                  text size="small"
                  class="note-btn"
                  :type="m.completed_note ? 'warning' : 'default'"
                  @click.stop="notePopoverVisible[m.id] = !notePopoverVisible[m.id]"
                >
                  <el-icon><EditPen /></el-icon>
                </el-button>
              </template>
              <div class="note-popover">
                <el-input
                  v-model="editNote"
                  type="textarea"
                  :rows="3"
                  placeholder="完成备注..."
                  maxlength="500"
                  show-word-limit
                />
                <div class="note-actions">
                  <el-button size="small" @click="notePopoverVisible[m.id] = false">取消</el-button>
                  <el-button size="small" type="primary" @click="saveNote(m)">保存</el-button>
                </div>
              </div>
            </el-popover>
          </div>

          <!-- 里程碑详情行 -->
          <div class="milestone-details">
            <template v-if="m.target_date">
              <span class="detail-item">目标: {{ m.target_date.slice(0, 10) }}</span>
            </template>
            <template v-if="m.target_value !== null && m.target_value !== undefined">
              <span class="detail-item">目标值: {{ maskAmount(m.target_value) }}</span>
            </template>
            <template v-if="m.actual_value !== null && m.actual_value !== undefined">
              <span class="detail-item">实际值: {{ maskAmount(m.actual_value) }}</span>
            </template>
            <span v-if="m.status === 'completed'" class="detail-item done-badge">✓ 已完成</span>
            <span v-if="m.reward_synced && m.reward_amount_display" class="detail-item reward-badge">
              💰 +{{ maskAmount(m.reward_amount_display) }} 奖励已发放
            </span>
            <span v-else-if="m.reward_amount_display && m.reward_amount_display > 0" class="detail-item potential-badge">
              💰 可获得 {{ maskAmount(m.reward_amount_display) }}
            </span>
          </div>

          <div v-if="m.completed_note" class="milestone-note">{{ m.completed_note }}</div>

        </div>
      </div>

      <el-empty v-if="!milestones.length" description="暂无里程碑" :image-size="50" />
    </div>
  </div>

  <!-- 完成庆祝动画 -->
  <teleport to="body">
    <transition name="celebrate">
      <div v-if="showCelebrate" class="celebrate-overlay" @click="showCelebrate = false">
        <div class="celebrate-content" @click.stop>
          <span class="celebrate-icon">🎉</span>
          <h2>里程碑完成！</h2>
          <p class="celebrate-title">{{ completedMilestone?.title }}</p>
          <p v-if="completedMilestone?.reward_amount_display" class="celebrate-reward">
            💰 +{{ completedMilestone.reward_amount_display }}
          </p>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Flag, Plus, EditPen } from '@element-plus/icons-vue'
import { usePrivacyMask } from '@/shared/composables/usePrivacyMask'
import type { Milestone } from '../types/goalTypes'

const props = defineProps<{
  milestones: Milestone[]
}>()

const emit = defineEmits<{
  toggle: [milestone: Milestone, status: string]
  add: []
  updateNote: [milestone: Milestone, note: string]
}>()

const { maskAmount } = usePrivacyMask()
const showCelebrate = ref(false)
const completedMilestone = ref<Milestone | null>(null)

const expandedId = ref<number | null>(null)
const notePopoverVisible = ref<Record<number, boolean>>({})
const editNote = ref('')

const completedCount = computed(() => props.milestones.filter(m => m.status === 'completed').length)

function toggleExpand(m: Milestone) {
  expandedId.value = expandedId.value === m.id ? null : m.id
}

/** checkbox 切换：completed ↔ pending */
function handleToggle(m: Milestone) {
  const newStatus = m.status === 'completed' ? 'pending' : 'completed'
  if (newStatus === 'completed') {
    completedMilestone.value = m
    showCelebrate.value = true
    setTimeout(() => { showCelebrate.value = false }, 2500)
  }
  emit('toggle', m, newStatus)
}

function initNote(m: Milestone) {
  editNote.value = m.completed_note || ''
}

function saveNote(m: Milestone) {
  emit('updateNote', m, editNote.value)
  notePopoverVisible.value[m.id] = false
}
</script>

<style scoped lang="scss">
.milestone-board {
  .board-header {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
    .board-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 500; }
  }

  .milestone-list { position: relative;

    .milestone-item { display: flex; gap: 10px;
      &.completed {
        .milestone-title { text-decoration: line-through; color: var(--el-text-color-placeholder); }
      }
      &.expanded {
        .milestone-body { padding-bottom: 12px; }
      }

      .milestone-connector { display: flex; flex-direction: column; align-items: center; width: 14px;
        .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--el-border-color); margin-top: 6px; z-index: 1; flex-shrink: 0;
          &.done { background: var(--el-color-success); }
          &.progress { background: var(--el-color-primary); }
        }
        .line { flex: 1; width: 2px; background: var(--el-border-color-light); min-height: 24px; }
      }

      .milestone-body { flex: 1; padding-bottom: 8px; min-width: 0;
        .milestone-top { display: flex; align-items: center; gap: 4px; margin-bottom: 2px;
          .milestone-title { font-size: 13px; font-weight: 500; flex: 1; cursor: pointer;
            &:hover { color: var(--el-color-primary); }
          }
          .note-btn { flex-shrink: 0; }
        }

        .milestone-details { display: flex; flex-wrap: wrap; gap: 8px; margin-left: 24px; margin-bottom: 4px;
          .detail-item { font-size: 11px; color: var(--el-text-color-secondary); }
          .done-badge { color: var(--el-color-success); font-weight: 500; }
          .reward-badge { color: var(--el-color-warning); font-weight: 500; }
          .potential-badge { color: var(--el-color-primary); font-weight: 500; }
        }

        .milestone-note { margin-left: 24px; margin-top: 4px; padding: 4px 8px; background: var(--el-fill-color-light); border-radius: 4px; font-size: 12px; color: var(--el-text-color-regular); }

        .milestone-actions {
          margin-left: 24px; margin-top: 8px; padding: 8px; background: var(--el-bg-color-page); border-radius: 6px;
          .actions-divider { font-size: 11px; color: var(--el-text-color-secondary); margin-bottom: 4px; font-weight: 500; }
        }
      }
    }
  }
}

.note-popover {
  .note-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
}

.expand-enter-active, .expand-leave-active { transition: all 0.2s ease; overflow: hidden; }
.expand-enter-from, .expand-leave-to { opacity: 0; max-height: 0; }

.celebrate-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.celebrate-content {
  background: #fff;
  border-radius: 16px;
  padding: 40px;
  text-align: center;
  animation: bounce-in 0.5s ease;
  h2 { margin: 0 0 8px; font-size: 22px; color: #1F2937; }
}
.celebrate-icon {
  font-size: 64px;
  display: block;
  margin-bottom: 16px;
}
.celebrate-title {
  font-size: 16px;
  color: #4B5563;
  margin: 0 0 4px;
}
.celebrate-reward {
  color: #f59e0b;
  font-size: 20px;
  font-weight: 700;
  margin: 8px 0 0;
}
.celebrate-enter-active, .celebrate-leave-active { transition: opacity 0.3s ease; }
.celebrate-enter-from, .celebrate-leave-to { opacity: 0; }
@keyframes bounce-in {
  0% { transform: scale(0.3); opacity: 0; }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); opacity: 1; }
}
</style>
