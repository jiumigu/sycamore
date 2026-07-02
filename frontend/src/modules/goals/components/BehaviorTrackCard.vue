<template>
  <div class="behavior-track" v-loading="loading">
    <!-- 连续天数 -->
    <div class="streak-row">
      <span class="streak-fire">🔥</span>
      <span class="streak-count">已坚持 <strong>{{ stats?.streak?.current ?? 0 }}</strong> 天</span>
      <span class="streak-divider">·</span>
      <span>最长连续 <strong>{{ stats?.streak?.longest ?? 0 }}</strong> 天</span>
      <span class="streak-divider">·</span>
      <span>剩余 <strong>{{ remaining }}</strong> 天</span>
    </div>

    <!-- 进度条 -->
    <div class="progress-row">
      <el-progress
        :percentage="displayProgress"
        :stroke-width="10"
        :color="progressColor"
      />
      <span class="progress-text">{{ displayProgress }}%</span>
    </div>

    <!-- 操作区 -->
    <div class="action-row">
      <el-button
        type="primary"
        :loading="checkingIn"
        :disabled="alreadyChecked"
        @click="handleCheckin"
      >
        <el-icon><Select /></el-icon>
        {{ alreadyChecked ? '今日已打卡' : '今日打卡' }}
      </el-button>
      <el-button @click="showCalendar = true">
        <el-icon><Calendar /></el-icon> 查看打卡日历
      </el-button>
    </div>

    <!-- 里程碑列表 -->
    <div class="milestone-section">
      <div class="milestone-section-title">🎯 里程碑（{{ stats?.completed_milestones ?? 0 }}/{{ stats?.total_milestones ?? 0 }}）</div>
      <div
        v-for="m in milestones"
        :key="m.id"
        class="milestone-item"
        :class="{ completed: m.status === 'completed' }"
      >
        <div class="milestone-left">
          <span class="status-icon" :class="m.status === 'completed' ? 'done' : 'todo'" @click.stop="toggleMilestoneStatus(m)">
            {{ m.status === 'completed' ? '✅' : '○' }}
          </span>
        </div>
        <div class="milestone-content">
          <div class="milestone-name">{{ m.title }}</div>
          <div class="milestone-meta">
            <span v-if="m.reward_amount">💰 ¥{{ m.reward_amount }}</span>
            <el-tag :type="m.status === 'completed' ? 'success' : 'info'" size="small">
              {{ m.status === 'completed' ? '已达成' : '待开始' }}
            </el-tag>
          </div>
        </div>
        <div class="milestone-right">
          <el-button size="small" text @click.stop="openEditDialog(m)">✏️</el-button>
        </div>
      </div>
      <el-empty v-if="!milestones.length" description="暂无里程碑" :image-size="60" />
    </div>

    <!-- 里程碑编辑弹窗 -->
    <el-dialog v-model="showEditDialog" title="📝 编辑里程碑" width="550px" append-to-body :close-on-click-modal="false">
      <div class="milestone-header" v-if="editingMilestone">
        <p><strong>{{ editingMilestone.title }}</strong></p>
        <p v-if="editingMilestone.target_date" class="edit-deadline">截止日期：{{ editingMilestone.target_date.slice(0, 10) }}</p>
        <el-tag :type="editingMilestone.status === 'completed' ? 'success' : 'warning'" size="small">
          {{ editingMilestone.status === 'completed' ? '已达成' : '待开始' }}
        </el-tag>
      </div>
      <el-divider />
      <el-form-item label="详情描述">
        <el-input v-model="editForm.description" type="textarea" :rows="3" placeholder="里程碑的详细说明" maxlength="500" show-word-limit />
      </el-form-item>
      <el-form-item label="完成备注">
        <el-input v-model="editForm.completed_note" type="textarea" :rows="2" placeholder="简单记录完成情况" maxlength="200" show-word-limit />
      </el-form-item>
      <el-form-item label="自我批阅">
        <el-input v-model="editForm.self_review" type="textarea" :rows="3" placeholder="你想对完成这件事的自己说什么？" maxlength="500" show-word-limit />
      </el-form-item>
      <div class="quick-phrases">
        <span class="phrase-label">快捷填入：</span>
        <el-tag v-for="phrase in quickPhrases" :key="phrase" size="small" class="phrase-tag" @click="editForm.self_review = phrase">
          {{ phrase }}
        </el-tag>
      </div>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingMilestone" @click="saveMilestoneEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 打卡日历弹窗 -->
    <el-dialog v-model="showCalendar" title="打卡日历" width="560px" destroy-on-close>
      <div class="calendar-heatmap">
        <div class="calendar-month" v-for="(days, monthLabel) in calendarByMonth" :key="monthLabel">
          <div class="month-label">{{ monthLabel }}</div>
          <div class="month-days">
            <div
              v-for="(info, dayIdx) in days"
              :key="dayIdx"
              class="day-cell"
              :class="{ checked: info.checked, future: info.future, today: info.today, unchecked: !info.checked && !info.future }"
              :title="info.date"
              @click="handleDayClick(info)"
            >
              {{ info.dayNum }}
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showCalendar = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 补打卡确认弹窗 -->
    <el-dialog v-model="showCheckinDialog" title="确认打卡" width="350px" append-to-body>
      <div class="checkin-content">
        <p v-if="isPastDate">
          确认<strong>补打 {{ checkingDate }}</strong> 的卡吗？
        </p>
        <p v-else>
          确认今天（{{ checkingDate }}）打卡吗？
        </p>
      </div>
      <template #footer>
        <el-button @click="showCheckinDialog = false">取消</el-button>
        <el-button type="primary" :loading="confirmingCheckin" @click="confirmCheckin">确认打卡</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ElMessageBox } from 'element-plus'
import { Select, Calendar } from '@element-plus/icons-vue'
import { checkinAction, getCheckinStats, patchMilestone, toggleMilestone } from '../api/goalApi'
import type { CheckinStats, CheckinMilestone } from '../types/goalTypes'

const props = defineProps<{
  goalId: number
  actionId: number | null
}>()

const emit = defineEmits<{
  checked: []
}>()

const loading = ref(false)
const checkingIn = ref(false)
const showCalendar = ref(false)
const stats = ref<CheckinStats | null>(null)
const alreadyChecked = ref(false)

const milestones = computed(() => stats.value?.milestones ?? [])

const showCheckinDialog = ref(false)
const checkingDate = ref('')
const isPastDate = ref(false)
const confirmingCheckin = ref(false)

const showEditDialog = ref(false)
const editingMilestone = ref<CheckinMilestone | null>(null)
const savingMilestone = ref(false)
const editForm = reactive({
  description: '',
  completed_note: '',
  self_review: '',
})
const quickPhrases = [
  '辛苦了，这段时间不容易',
  '做得不错，继续保持',
  '比想象中难，但坚持下来了',
  '下次可以提前准备',
  '这件事让我学到了...',
  '完成了！下一个目标是什么？',
]

const remaining = computed(() => {
  if (!stats.value) return 0
  return Math.max(0, stats.value.total_milestones - stats.value.completed_milestones)
})

const displayProgress = computed(() => stats.value?.progress_percentage ?? 0)

const rewardMilestones = computed(() => stats.value?.reward_milestones ?? [])

const progressColor = computed(() => {
  const p = displayProgress.value
  if (p >= 100) return '#67c23a'
  if (p >= 75) return '#409eff'
  if (p >= 50) return '#e6a23c'
  if (p >= 25) return '#f56c6c'
  return '#909399'
})

const calendarByMonth = computed(() => {
  const cal = stats.value?.calendar ?? {}
  const months: Record<string, Array<{ dayNum: number; date: string; checked: boolean; future: boolean; today: boolean }>> = {}
  const todayStr = new Date().toISOString().slice(0, 10)

  // If no data, show current month
  const dates = Object.keys(cal).length ? Object.keys(cal).sort() : [todayStr]

  // Collect all dates from calendar data
  const allDates = new Set<string>()
  const checkedDates = new Set(Object.keys(cal).filter(d => cal[d]))

  // Determine range: from earliest data to today
  const startDate = dates[0] || todayStr
  const endDate = todayStr

  const cursor = new Date(startDate)
  const end = new Date(endDate)
  while (cursor <= end) {
    const ds = cursor.toISOString().slice(0, 10)
    allDates.add(ds)
    cursor.setDate(cursor.getDate() + 1)
  }

  for (const ds of allDates) {
    const d = new Date(ds + 'T00:00:00')
    const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    if (!months[monthKey]) months[monthKey] = []
    months[monthKey].push({
      dayNum: d.getDate(),
      date: ds,
      checked: checkedDates.has(ds),
      future: ds > todayStr,
      today: ds === todayStr,
    })
  }

  return months
})

async function loadStats() {
  if (!props.actionId) return
  loading.value = true
  try {
    const res = await getCheckinStats(props.actionId)
    stats.value = res.data as CheckinStats
    const todayStr = new Date().toISOString().slice(0, 10)
    alreadyChecked.value = !!(stats.value?.calendar?.[todayStr])
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

async function handleCheckin() {
  if (!props.actionId) return
  checkingIn.value = true
  try {
    const res = await checkinAction(props.actionId)
    if (res.data.checked) {
      ElMessage.success('打卡成功！')
      alreadyChecked.value = true
      emit('checked')
      await loadStats()
    } else if (res.data.already_checked) {
      ElMessage.info('今日已打卡')
      alreadyChecked.value = true
    }
  } catch {
    ElMessage.error('打卡失败')
  } finally {
    checkingIn.value = false
  }
}

function handleDayClick(info: { dayNum: number; date: string; checked: boolean; future: boolean; today: boolean }) {
  if (info.future) return

  if (info.checked) {
    ElMessage.info('该日期已打卡')
    return
  }

  checkingDate.value = info.date
  isPastDate.value = info.date < new Date().toISOString().slice(0, 10)
  showCheckinDialog.value = true
}

async function confirmCheckin() {
  if (!props.actionId || !checkingDate.value) return
  confirmingCheckin.value = true
  try {
    await checkinAction(props.actionId, checkingDate.value)
    ElMessage.success(isPastDate.value ? '补打卡成功' : '打卡成功')
    showCheckinDialog.value = false
    await loadStats()
    emit('checked')
  } catch {
    ElMessage.error('打卡失败')
  } finally {
    confirmingCheckin.value = false
  }
}

function openEditDialog(m: CheckinMilestone) {
  editingMilestone.value = m
  editForm.description = m.description
  editForm.completed_note = m.completed_note
  editForm.self_review = m.self_review
  showEditDialog.value = true
}

async function saveMilestoneEdit() {
  if (!editingMilestone.value) return
  savingMilestone.value = true
  try {
    await patchMilestone(editingMilestone.value.id, {
      description: editForm.description,
      completed_note: editForm.completed_note,
      self_review: editForm.self_review,
    })
    showEditDialog.value = false
    ElMessage.success('已保存')
    await loadStats()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingMilestone.value = false
  }
}

async function toggleMilestoneStatus(m: CheckinMilestone) {
  const wasCompleted = m.status === 'completed'
  const action = wasCompleted ? '重置' : '完成'
  try {
    await ElMessageBox.confirm(
      `确定${action}里程碑「${m.title}」吗？`,
      '确认',
      { confirmButtonText: action, cancelButtonText: '取消', type: 'warning' },
    )
    await toggleMilestone(props.goalId, m.id, {
      status: wasCompleted ? 'pending' : 'completed',
    })
    ElMessage.success(`里程碑已${action}`)
    emit('checked')
    await loadStats()
  } catch {
    // cancelled
  }
}

onMounted(loadStats)
</script>

<style scoped lang="scss">
.behavior-track {
  padding: 4px 0;
}

.streak-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--el-text-color-primary);
  margin-bottom: 10px;
  flex-wrap: wrap;

  .streak-fire { font-size: 18px; }
  .streak-count { font-weight: 500; }
  .streak-divider { color: var(--el-border-color); }
  strong { color: var(--el-color-danger); }
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;

  :deep(.el-progress) { flex: 1; }
  .progress-text { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; }
}

.action-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.calendar-heatmap {
  max-height: 400px;
  overflow-y: auto;

  .calendar-month {
    margin-bottom: 16px;

    .month-label {
      font-size: 14px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin-bottom: 6px;
    }

    .month-days {
      display: flex;
      flex-wrap: wrap;
      gap: 3px;

      .day-cell {
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        border-radius: 4px;
        background: var(--el-fill-color-light);
        color: var(--el-text-color-secondary);
        cursor: pointer;
        user-select: none;

        &.checked {
          background: var(--el-color-success);
          color: #fff;
        }

        &.today {
          border: 2px solid var(--el-color-primary);
        }

        &.future {
          opacity: 0.3;
          cursor: not-allowed;
        }

        &.unchecked {
          background: #f5f5f5;
          color: #333;
          &:hover { background: #ecf5ff; }
        }
      }
    }
  }
}

.milestone-section {
  margin-top: 12px;

  .milestone-section-title {
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--el-text-color-primary);
  }

  .milestone-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-bottom: 1px solid #f5f5f5;

    &:last-child { border-bottom: none; }

    &.completed {
      background: #f9fafb;
      .milestone-name { color: #999; text-decoration: line-through; }
    }

    .status-icon {
      font-size: 16px;
      cursor: pointer;
      transition: transform 0.15s;
      &:hover { transform: scale(1.2); }
      &.done { color: #67c23a; }
      &.todo { color: #ccc; }
    }

    .milestone-content {
      flex: 1;
      min-width: 0;

      .milestone-name {
        font-size: 13px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .milestone-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 2px;
        font-size: 12px;
        color: #999;
      }
    }

    .milestone-right {
      flex-shrink: 0;
    }
  }
}

.milestone-header {
  p { margin: 4px 0; font-size: 14px; }
  .edit-deadline { color: var(--el-text-color-secondary); font-size: 13px; }
}

.quick-phrases {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px;
  .phrase-label { font-size: 12px; color: #999; }
  .phrase-tag { cursor: pointer; }
}
</style>
