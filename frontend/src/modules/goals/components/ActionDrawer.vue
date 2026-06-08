<template>
  <el-drawer
    :model-value="visible"
    :title="goalTitle"
    size="50%"
    @update:model-value="$emit('update:visible', $event)"
    @open="handleOpen"
  >
    <!-- 快速添加 -->
    <div class="quick-add">
      <el-input
        v-model="quickName"
        placeholder="回车快速添加行为"
        maxlength="200"
        @keyup.enter="handleQuickAdd"
      >
        <template #append>
          <el-button @click="handleQuickAdd" :loading="quickSubmitting">添加</el-button>
        </template>
      </el-input>
    </div>

    <!-- 行为列表 -->
    <div v-loading="loading" class="action-list">
      <div v-if="!actions.length && !loading" class="empty-hint">
        暂无行为记录
      </div>
      <div v-for="action in actions" :key="action.id" class="action-item">
        <div class="action-main">
          <div class="action-name">{{ action.name }}</div>
          <div class="action-meta">
            <el-tag v-if="action.milestone_title" size="small" type="info">
              {{ action.milestone_title }}
            </el-tag>
            <span class="action-time">{{ action.action_date || action.created_at.slice(0, 10) }}</span>
          </div>
          <div v-if="action.note" class="action-note">{{ action.note }}</div>
        </div>
        <div class="action-ops">
          <el-button text size="small" @click="openEdit(action)">
            <el-icon><Edit /></el-icon>
          </el-button>
          <el-button text size="small" type="danger" @click="handleDelete(action)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog
      v-model="editVisible"
      title="编辑行为"
      width="420px"
      destroy-on-close
    >
      <el-form ref="editFormRef" :model="editData" :rules="editRules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="editData.name" maxlength="200" />
        </el-form-item>
        <el-form-item label="里程碑">
          <el-select v-model="editData.milestone" placeholder="不关联（可选）" clearable style="width: 100%">
            <el-option
              v-for="m in goalMilestones"
              :key="m.id"
              :label="m.title"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="发生日期">
          <el-date-picker
            v-model="editData.action_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="默认今天，可补录历史日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editData.note" type="textarea" :rows="3" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="handleEditSubmit">确定</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete } from '@element-plus/icons-vue'
import { useGoalBoardStore } from '../stores/goalBoardStore'
import type { Action, Milestone } from '../types/goalTypes'

const props = defineProps<{
  visible: boolean
  goalId: number
  goalTitle: string
  goalMilestones: Milestone[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  updated: []
}>()

const boardStore = useGoalBoardStore()
const loading = ref(false)
const quickName = ref('')
const quickSubmitting = ref(false)

const actions = computed(() => boardStore.getActionsByGoal(props.goalId))

// 编辑
const editVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref()
const editData = reactive({
  id: 0,
  name: '',
  milestone: null as number | null,
  note: '',
  action_date: '',
})
const editRules = { name: [{ required: true, message: '请输入行为名称', trigger: 'blur' }] }

async function handleOpen() {
  loading.value = true
  try {
    await boardStore.loadActions(props.goalId)
  } catch {
    ElMessage.error('加载行为记录失败')
  } finally {
    loading.value = false
  }
}

async function handleQuickAdd() {
  const name = quickName.value.trim()
  if (!name) return
  quickSubmitting.value = true
  try {
    await boardStore.addAction(props.goalId, { name })
    quickName.value = ''
    emit('updated')
    ElMessage.success('已添加')
  } catch {
    ElMessage.error('添加失败')
  } finally {
    quickSubmitting.value = false
  }
}

function openEdit(action: Action) {
  editData.id = action.id
  editData.name = action.name
  editData.milestone = action.milestone
  editData.note = action.note || ''
  editData.action_date = action.action_date || ''
  editVisible.value = true
}

async function handleEditSubmit() {
  if (!editFormRef.value) return
  const valid = await editFormRef.value.validate().catch(() => false)
  if (!valid) return
  editSubmitting.value = true
  try {
    const data: Record<string, unknown> = { name: editData.name.trim() }
    if (editData.milestone) data.milestone = editData.milestone
    else data.milestone = null
    data.note = editData.note.trim() || null
    data.action_date = editData.action_date || null
    await boardStore.updateAction(editData.id, props.goalId, data)
    editVisible.value = false
    emit('updated')
    ElMessage.success('已更新')
  } catch {
    ElMessage.error('更新失败')
  } finally {
    editSubmitting.value = false
  }
}

async function handleDelete(action: Action) {
  try {
    await ElMessageBox.confirm(`确定删除"${action.name}"？`, '提示', { type: 'warning' })
    await boardStore.deleteAction(action.id, props.goalId)
    emit('updated')
    ElMessage.success('已删除')
  } catch { /* cancelled */ }
}
</script>

<style scoped lang="scss">
.quick-add {
  margin-bottom: 16px;
}

.action-list {
  .empty-hint {
    text-align: center;
    padding: 40px 0;
    color: var(--el-text-color-secondary);
    font-size: 14px;
  }
  .action-item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 10px 0;
    border-bottom: 1px solid var(--el-border-color-light);
    &:last-child { border-bottom: none; }
    .action-main {
      flex: 1;
      min-width: 0;
      .action-name { font-size: 14px; font-weight: 500; margin-bottom: 4px; }
      .action-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
      .action-time { font-size: 12px; color: var(--el-text-color-secondary); }
      .action-note { font-size: 13px; color: var(--el-text-color-secondary); line-height: 1.4; }
    }
    .action-ops { display: flex; gap: 4px; flex-shrink: 0; }
  }
}
</style>
