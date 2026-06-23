<template>
  <div class="goal-hub">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">目标管理</h1>
        <el-tag type="primary" class="module-tag">成长发展</el-tag>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="showQuickDialog = true">
          <el-icon><Lightning /></el-icon>
          快速创建
        </el-button>
        <el-button @click="openCreate()">
          <el-icon><Plus /></el-icon>
          手动创建
        </el-button>
        <el-button @click="refreshAll">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6f7ff"><el-icon color="#1890ff"><Flag /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.total_goals || 0 }}</div>
              <div class="stat-label">总目标数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f6ffed"><el-icon color="#52c41a"><Check /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.completed_goals || 0 }}</div>
              <div class="stat-label">已完成</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff7e6"><el-icon color="#fa8c16"><Clock /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.in_progress_goals || 0 }}</div>
              <div class="stat-label">进行中</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff1f0"><el-icon color="#f5222d"><Warning /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ stats?.overdue_goals || 0 }}</div>
              <div class="stat-label">已超期</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 状态筛选标签 -->
    <el-card class="section-card filter-tabs-card">
      <el-radio-group v-model="filterStatus" @change="fetchData" class="status-tabs">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="in-progress">进行中</el-radio-button>
        <el-radio-button value="planning">计划中</el-radio-button>
        <el-radio-button value="paused">已暂停</el-radio-button>
        <el-radio-button value="completed">已完成</el-radio-button>
        <el-radio-button value="abandoned">已放弃</el-radio-button>
        <el-radio-button value="archived">已归档</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- 筛选栏 -->
    <el-card class="section-card">
      <div class="filter-bar">
        <el-input v-model="searchKeyword" placeholder="搜索目标..." clearable class="search-input" @input="fetchData" />
        <el-select v-model="filterCategory" placeholder="类型" clearable @change="fetchData" class="filter-select">
          <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
        <el-select v-model="filterPriority" placeholder="优先级" clearable @change="fetchData" class="filter-select">
          <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
        <el-button v-if="boardStore.hasSelectedGoals" type="success" @click="openCreateAction">
          <el-icon><Plus /></el-icon>
          + 新增行为 ({{ boardStore.selectedGoalIds.length }}个目标)
        </el-button>
        <el-button v-if="boardStore.hasSelectedGoals" @click="boardStore.clearSelection()">
          清空勾选
        </el-button>
        <el-button @click="resetFilters" class="reset-btn"><el-icon><RefreshRight /></el-icon>重置</el-button>
      </div>
    </el-card>

    <!-- 目标网格 -->
    <div v-loading="goalStore.loading" class="goal-grid">
      <template v-for="goal in goalStore.goalList" :key="goal.id">
        <GoalCard
          :goal="goal"
          :is-selected="boardStore.selectedGoalIds.includes(goal.id)"
          :actions-count="boardStore.getActionsCount(goal.id)"
          :tracking-action-id="getTrackingActionId(goal)"
          @edit="openDetailEdit"
          @delete="handleDelete"
          @clone="handleClone"
          @expand="handleExpand"
          @milestone-toggle="handleMilestoneToggle"
          @update-status="handleUpdateStatus"
          @edit-milestone="handleEditMilestone"
          @toggle-select="boardStore.toggleGoalSelection"
          @view-actions="handleViewActions"
          @show-milestones="openMilestoneDialog"
          @checkin="handleCheckin"
        />
      </template>
      <el-empty v-if="!goalStore.goalList.length && !goalStore.loading" description="暂无目标" :image-size="120" />
    </div>
  </div>

  <GoalDetail
    v-model:visible="dialogVisible"
    :goal-id="editingId"
    @saved="onSaved"
  />

  <CreateActionDialog
    v-model:visible="showCreateAction"
    :goal-ids="boardStore.selectedGoalIds"
    :all-milestones="createDialogMilestones"
    @created="onActionsCreated"
  />

  <QuickGoalDialog
    v-model:visible="showQuickDialog"
    @created="onQuickCreated"
  />

  <el-dialog v-model="showCloneDialog" title="复制目标" width="420px">
    <el-form label-width="90px">
      <el-form-item label="目标名称">
        <el-input v-model="cloneForm.name" />
      </el-form-item>
      <el-form-item label="复制里程碑">
        <el-switch v-model="cloneForm.copyMilestones" />
      </el-form-item>
      <el-form-item label="复制行为记录">
        <el-switch v-model="cloneForm.copyActions" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showCloneDialog = false">取消</el-button>
      <el-button type="primary" :loading="goalStore.submitting" @click="handleCloneSubmit">确认复制</el-button>
    </template>
  </el-dialog>

  <ActionDrawer
    v-model:visible="showActionDrawer"
    :goal-id="actionDrawerGoalId"
    :goal-title="actionDrawerGoalTitle"
    :goal-milestones="actionDrawerMilestones"
    @updated="onActionsUpdated"
  />

  <!-- 里程碑详情弹窗 -->
  <el-dialog v-model="showMilestoneDialog" :title="milestoneGoal?.title" width="680px">
    <div class="goal-summary">
      <span>进度：{{ milestoneGoal?.progress_percentage }}%</span>
      <span>里程碑：{{ milestoneCompletedCount }}/{{ milestoneTotalCount }}</span>
      <span>状态：{{ milestoneGoal?.status_display || milestoneGoal?.status }}</span>
    </div>

    <el-divider />

    <div class="add-milestone">
      <el-input v-model="newMilestoneTitle" placeholder="新增里程碑名称" style="width: 300px" />
      <el-date-picker v-model="newMilestoneDate" type="date" value-format="YYYY-MM-DD" placeholder="截止日期" />
      <el-button type="primary" @click="handleAddMilestone">添加</el-button>
    </div>

    <el-divider />

    <div v-if="milestones.length > 0" class="milestone-list">
      <div
        v-for="m in milestones" :key="m.id"
        class="milestone-item"
        :class="{ completed: m.status === 'completed' }"
      >
        <div class="milestone-left">
          <el-checkbox
            :model-value="m.status === 'completed'"
            @change="(val: boolean) => handleToggleMilestone(m, val)"
          />
        </div>
        <div class="milestone-content">
          <div class="milestone-name">{{ m.title }}</div>
          <div class="milestone-meta">
            <span v-if="m.target_date">
              截止：{{ m.target_date }}
              <el-button size="small" text @click.stop="editMilestoneDate(m)">✏️</el-button>
            </span>
            <span v-else>
              <el-button size="small" text @click.stop="editMilestoneDate(m)">+ 设置截止日期</el-button>
            </span>
            <span v-if="m.reward_amount">💰 ¥{{ m.reward_amount }}</span>
            <span :class="m.status === 'completed' ? 'text-success' : 'text-warning'">
              {{ m.status_display || m.status }}
            </span>
          </div>
          <div v-if="m.description" class="milestone-detail-desc">📋 {{ m.description }}</div>
          <div v-if="m.completed_note" class="milestone-detail-note">✅ {{ m.completed_note }}</div>
          <div v-if="m.self_review" class="milestone-detail-review">💭 {{ m.self_review }}</div>
        </div>
      </div>
    </div>
    <el-empty v-else description="暂无里程碑" />

    <template #footer>
      <el-button @click="showMilestoneDialog = false">关闭</el-button>
    </template>
  </el-dialog>

  <!-- 里程碑截止日期编辑弹窗 -->
  <el-dialog v-model="showDateDialog" title="设置截止日期" width="300px" append-to-body>
    <el-date-picker v-model="editingMilestoneDate" type="date" value-format="YYYY-MM-DD" style="width:100%" />
    <template #footer>
      <el-button @click="showDateDialog = false">取消</el-button>
      <el-button type="primary" @click="saveMilestoneDate">保存</el-button>
    </template>
  </el-dialog>

  <!-- 里程碑详情编辑弹窗 -->
  <el-dialog v-model="showEditDialog" :title="editingMilestoneData?.status === 'completed' ? '✅ 里程碑完成' : '📝 编辑里程碑'" width="550px" :close-on-click-modal="false">
    <div class="milestone-header" v-if="editingMilestoneData">
      <p><strong>{{ editingMilestoneData.title }}</strong></p>
      <p v-if="editingMilestoneData.target_date" class="edit-deadline">截止日期：{{ editingMilestoneData.target_date.slice(0, 10) }}</p>
      <el-tag :type="editingMilestoneData.status === 'completed' ? 'success' : 'warning'" size="small">
        {{ editingMilestoneData.status_display || editingMilestoneData.status }}
      </el-tag>
    </div>

    <el-divider />

    <el-form-item label="详情描述">
      <el-input
        v-model="editDescription"
        type="textarea" :rows="3"
        placeholder="里程碑的详细说明"
        maxlength="500" show-word-limit
      />
    </el-form-item>

    <el-form-item label="完成备注">
      <el-input
        v-model="editCompletionNote"
        type="textarea" :rows="2"
        placeholder="简单记录完成情况"
        maxlength="200" show-word-limit
      />
    </el-form-item>

    <el-form-item label="自我批阅">
      <el-input
        v-model="editSelfReview"
        type="textarea" :rows="3"
        placeholder="你想对完成这件事的自己说什么？"
        maxlength="500" show-word-limit
      />
    </el-form-item>

    <div class="quick-phrases">
      <span class="phrase-label">快捷填入：</span>
      <el-tag
        v-for="phrase in quickPhrases" :key="phrase"
        size="small" class="phrase-tag"
        @click="editSelfReview = phrase"
      >
        {{ phrase }}
      </el-tag>
    </div>

    <template #footer>
      <el-button @click="showEditDialog = false">取消</el-button>
      <el-button type="primary" @click="saveMilestoneDetail">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Flag, Check, Clock, Warning, RefreshRight, Lightning, CopyDocument } from '@element-plus/icons-vue'
import { useGoalStore } from '../stores/goalStore'
import { useGoalBoardStore } from '../stores/goalBoardStore'
import * as goalApi from '../api/goalApi'
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS } from '../types/goalTypes'
import type { Goal, GoalStatus, Milestone } from '../types/goalTypes'
import GoalCard from '../components/GoalCard.vue'
import GoalDetail from './GoalDetail.vue'
import CreateActionDialog from '../components/CreateActionDialog.vue'
import ActionDrawer from '../components/ActionDrawer.vue'
import QuickGoalDialog from '../components/QuickGoalDialog.vue'

const goalStore = useGoalStore()
const boardStore = useGoalBoardStore()

const searchKeyword = ref('')
const filterCategory = ref('')
const filterStatus = ref('in-progress')
const filterPriority = ref('')
const dialogVisible = ref(false)
const editingId = ref<number | undefined>(undefined)

const showCreateAction = ref(false)
const createDialogMilestones = ref<Milestone[]>([])

const showActionDrawer = ref(false)
const actionDrawerGoalId = ref(0)
const actionDrawerGoalTitle = ref('')
const actionDrawerMilestones = ref<Milestone[]>([])

const stats = computed(() => goalStore.stats)

/** 打开新增行为弹窗前先加载选中目标的里程碑 */
const showQuickDialog = ref(false)
const showCloneDialog = ref(false)
const cloneForm = reactive({
  name: '',
  copyMilestones: true,
  copyActions: true,
})
const cloneTargetId = ref<number | null>(null)

function handleClone(goal: Goal) {
  cloneForm.name = `${goal.title}（副本）`
  cloneForm.copyMilestones = true
  cloneForm.copyActions = true
  cloneTargetId.value = goal.id
  showCloneDialog.value = true
}

async function handleCloneSubmit() {
  if (!cloneTargetId.value || !cloneForm.name.trim()) return
  try {
    await goalStore.cloneGoal(cloneTargetId.value, {
      name: cloneForm.name,
      copy_milestones: cloneForm.copyMilestones,
      copy_actions: cloneForm.copyActions,
    })
    ElMessage.success('目标已复制')
    showCloneDialog.value = false
    refreshAll()
  } catch {
    ElMessage.error('复制失败')
  }
}

function onQuickCreated() {
  showQuickDialog.value = false
  refreshAll()
}

async function openCreateAction() {
  const all: Milestone[] = []
  const seen = new Set<number>()
  for (const goalId of boardStore.selectedGoalIds) {
    try {
      const detail = await goalStore.fetchGoalById(goalId)
      for (const m of detail?.milestones || []) {
        if (!seen.has(m.id)) {
          seen.add(m.id)
          all.push(m)
        }
      }
    } catch {
      // 跳过加载失败的目标
    }
  }
  createDialogMilestones.value = all
  showCreateAction.value = true
}

/** 打开行为抽屉前加载里程碑数据 */
async function handleViewActions(goal: Goal) {
  actionDrawerGoalId.value = goal.id
  actionDrawerGoalTitle.value = goal.title
  try {
    const detail = await goalStore.fetchGoalById(goal.id)
    actionDrawerMilestones.value = detail?.milestones || []
  } catch {
    actionDrawerMilestones.value = []
  }
  showActionDrawer.value = true
}

async function fetchData() {
  const params: Record<string, unknown> = {}
  if (filterCategory.value) params.category = filterCategory.value
  if (filterStatus.value) params.status = filterStatus.value
  if (filterPriority.value) params.priority = filterPriority.value
  if (searchKeyword.value) params.search = searchKeyword.value
  await goalStore.fetchGoalList(params)
}

async function refreshAll() {
  await Promise.all([
    fetchData(),
    goalStore.fetchStats(),
  ])
}

function resetFilters() {
  searchKeyword.value = ''
  filterCategory.value = ''
  filterPriority.value = ''
  fetchData()
}

function openCreate() { editingId.value = undefined; dialogVisible.value = true }

function openDetailEdit(goal: Goal) {
  editingId.value = goal.id
  dialogVisible.value = true
}

async function handleDelete(goal: Goal) {
  try {
    await ElMessageBox.confirm(`确定删除"${goal.title}"？`, '提示', { type: 'warning' })
    await goalStore.deleteExistingGoal(goal.id)
    ElMessage.success('已删除')
    fetchData()
  } catch { /* cancelled */ }
}

async function handleExpand(goalId: number) {
  try {
    const detail = await goalStore.fetchGoalById(goalId)
    if (!detail) return
    const item = goalStore.goalList.find(g => g.id === goalId)
    if (item) {
      item.milestones = detail.milestones
      item.actions = detail.actions
    }
  } catch {
    // 静默失败
  }
}

async function handleMilestoneToggle(goal: Goal, milestone: Milestone, status: string) {
  try {
    await goalStore.updateMilestoneStatus(milestone.id, { status }, goal.id)
    ElMessage.success(status === 'completed' ? '里程碑已完成' : '里程碑已重置')
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

async function handleEditMilestone(goal: Goal, milestone: Milestone) {
  editingMilestoneData.value = milestone
  editDescription.value = milestone.description || ''
  editCompletionNote.value = milestone.completed_note || ''
  editSelfReview.value = milestone.self_review || ''
  showEditDialog.value = true
}

const showEditDialog = ref(false)
const editingMilestoneData = ref<Milestone | null>(null)
const editDescription = ref('')
const editCompletionNote = ref('')
const editSelfReview = ref('')

const quickPhrases = [
  '辛苦了，这段时间不容易',
  '做得不错，继续保持',
  '比想象中难，但坚持下来了',
  '下次可以提前准备',
  '这件事让我学到了...',
  '完成了！下一个目标是什么？',
]

async function saveMilestoneDetail() {
  if (!editingMilestoneData.value) return
  try {
    const data: Record<string, unknown> = {
      description: editDescription.value,
      completed_note: editCompletionNote.value,
      self_review: editSelfReview.value,
    }
    await goalStore.updateMilestoneStatus(editingMilestoneData.value.id, data, editingMilestoneData.value.goal)
    showEditDialog.value = false
    ElMessage.success('已保存')
    refreshAll()
  } catch {
    ElMessage.error('保存失败')
  }
}

async function handleUpdateStatus(goalId: number, status: GoalStatus) {
  try {
    await goalStore.updateGoalStatus(goalId, status)
    ElMessage.success('状态已更新')
  } catch {
    ElMessage.error('状态更新失败')
  }
}

function getTrackingActionId(goal: Goal): number | null {
  if (!goal.is_tracking_mode || !goal.actions?.length) return null
  return goal.actions[0].id ?? null
}

function handleCheckin(goalId: number) {
  handleExpand(goalId)
}

function onActionsCreated() {
  boardStore.clearSelection()
}

function onActionsUpdated() {
  // 抽屉内操作后自动刷新缓存
}

const showMilestoneDialog = ref(false)
const milestoneGoal = ref<Goal | null>(null)
const milestones = ref<Milestone[]>([])
const newMilestoneTitle = ref('')
const newMilestoneDate = ref('')

const showDateDialog = ref(false)
const editingMilestone = ref<Milestone | null>(null)
const editingMilestoneDate = ref('')

const milestoneCompletedCount = computed(() => milestones.value.filter(m => m.status === 'completed').length)
const milestoneTotalCount = computed(() => milestones.value.length)

async function openMilestoneDialog(goal: Goal) {
  milestoneGoal.value = goal
  showMilestoneDialog.value = true
  const detail = await goalStore.fetchGoalById(goal.id)
  milestones.value = detail?.milestones || []
}

async function handleAddMilestone() {
  if (!newMilestoneTitle.value.trim() || !milestoneGoal.value) return
  try {
    await goalApi.createMilestone({
      goal: milestoneGoal.value.id,
      title: newMilestoneTitle.value.trim(),
      target_date: newMilestoneDate.value || null,
    })
    newMilestoneTitle.value = ''
    newMilestoneDate.value = ''
    const detail = await goalStore.fetchGoalById(milestoneGoal.value.id)
    milestones.value = detail?.milestones || []
    refreshAll()
  } catch {
    ElMessage.error('添加里程碑失败')
  }
}

async function handleToggleMilestone(m: Milestone, completed: boolean) {
  if (!milestoneGoal.value) return
  const newStatus = completed ? 'completed' : 'pending'
  try {
    await goalStore.updateMilestoneStatus(m.id, { status: newStatus }, milestoneGoal.value.id)
    const detail = await goalStore.fetchGoalById(milestoneGoal.value.id)
    milestones.value = detail?.milestones || []
  } catch {
    ElMessage.error('操作失败')
  }
}

function editMilestoneDate(milestone: Milestone) {
  editingMilestone.value = milestone
  editingMilestoneDate.value = milestone.target_date || ''
  showDateDialog.value = true
}

async function saveMilestoneDate() {
  if (!editingMilestone.value) return
  try {
    await goalApi.patchMilestone(editingMilestone.value.id, {
      target_date: editingMilestoneDate.value || null,
    })
    showDateDialog.value = false
    // 刷新当前里程碑列表
    if (milestoneGoal.value) {
      const detail = await goalStore.fetchGoalById(milestoneGoal.value.id)
      milestones.value = detail?.milestones || []
    }
    ElMessage.success('日期已更新')
  } catch {
    ElMessage.error('更新失败')
  }
}

function onSaved() {
  dialogVisible.value = false
  refreshAll()
}

onMounted(() => { refreshAll() })
</script>

<style scoped lang="scss">
.goal-hub { padding: 20px; background: var(--el-bg-color-page); min-height: 100vh; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
  .header-left { display: flex; align-items: center; gap: 12px;
    .page-title { margin: 0; font-size: 24px; font-weight: 600; }
    .module-tag { font-size: 12px; }
  }
  .header-actions { display: flex; gap: 12px; }
}
.stats-row { margin-bottom: 16px; }
.stat-card :deep(.el-card__body) { padding: 16px; }
.stat-content { display: flex; align-items: center; gap: 14px;
  .stat-icon { width: 44px; height: 44px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
  .stat-info {
    .stat-value { font-size: 22px; font-weight: 600; line-height: 1; color: var(--el-text-color-primary); margin-bottom: 3px; }
    .stat-label { font-size: 13px; color: var(--el-text-color-regular); }
  }
}
.section-card { margin-bottom: 16px; }
.filter-tabs-card { padding: 0; }
.filter-tabs-card :deep(.el-card__body) { padding: 12px 16px; }
.status-tabs { width: 100%; display: flex; flex-wrap: wrap; gap: 4px; }

.filter-bar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  .search-input { width: 200px; }
  .filter-select { width: 120px; }
  .reset-btn { margin-left: 4px; }
}

.goal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }

.goal-summary { display: flex; gap: 24px; font-size: 14px; color: #555;
  span { background: #f5f7fa; padding: 4px 12px; border-radius: 4px; }
}

.add-milestone { display: flex; gap: 8px; align-items: center; }

.milestone-item {
  display: flex; gap: 12px; padding: 12px; border: 1px solid #eee; border-radius: 8px; margin-bottom: 8px;
  &.completed { background: #f0f9f0;
    .milestone-name { text-decoration: line-through; color: #999; }
  }
}

.milestone-meta {
  display: flex; gap: 16px; font-size: 12px; color: #666; margin-top: 4px;
  .text-success { color: #67c23a; }
  .text-warning { color: #e6a23c; }
}

.milestone-notes {
  margin-top: 6px; padding: 8px; background: #f9fafb; border-radius: 4px; font-size: 13px; color: #666;
}

.milestone-detail-desc {
  margin-top: 6px; padding: 8px; background: #f0f5ff; border-radius: 4px; font-size: 13px; color: #555;
}
.milestone-detail-note {
  margin-top: 6px; padding: 8px; background: #f0fff4; border-radius: 4px; font-size: 13px; color: #555;
}
.milestone-detail-review {
  margin-top: 6px; padding: 8px 10px; background: #fdf6ec; border-left: 3px solid #e6a23c;
  border-radius: 4px; font-size: 13px; color: #666; font-style: italic;
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
