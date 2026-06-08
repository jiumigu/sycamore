<template>
  <el-dialog
    :model-value="visible"
    :title="goalId ? '编辑目标' : '新建目标'"
    width="760px"
    destroy-on-close
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" class="goal-form">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="目标标题" prop="title">
            <el-input v-model="form.title" placeholder="请输入目标标题" maxlength="100" show-word-limit />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="目标类型" prop="category">
            <el-select v-model="form.category" placeholder="请选择" style="width: 100%">
              <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="描述" prop="description">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="目标描述" maxlength="500" show-word-limit />
      </el-form-item>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="状态" prop="status">
            <el-select v-model="form.status" style="width: 100%">
              <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="优先级" prop="priority">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="标签" prop="tags">
            <el-select v-model="form.tags" multiple filterable allow-create default-first-option placeholder="选择或输入" style="width: 100%">
              <el-option v-for="t in COMMON_TAGS" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="奖励/里程碑" prop="reward_value">
            <el-input-number v-model="form.reward_value" :min="0" :precision="2" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="启用奖励">
            <el-switch v-model="form.enable_reward" active-text="奖励池联动" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row v-if="form.enable_reward" :gutter="20">
        <el-col :span="12">
          <el-form-item label="默认奖励金" prop="default_reward_amount">
            <el-input-number v-model="form.default_reward_amount" :min="0" :precision="2" :step="5" style="width: 100%" placeholder="每完成一个里程碑发放" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="开始日期" prop="start_date">
            <el-date-picker v-model="form.start_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="截止日期" prop="deadline">
            <el-date-picker v-model="form.deadline" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" :disabled-date="(d: Date) => form.start_date ? d < new Date(form.start_date) : false" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注信息" maxlength="500" show-word-limit />
      </el-form-item>

      <el-divider>里程碑</el-divider>
      <div v-if="goalId" class="milestones-editor">
        <div v-for="(m, i) in form.milestones" :key="i" class="milestone-row">
          <el-input v-model="m.title" placeholder="里程碑描述" class="milestone-input" />
          <el-button type="danger" :icon="Delete" circle size="small" @click="removeMilestone(i)" />
        </div>
        <el-button type="primary" :icon="Plus" @click="addMilestone">添加里程碑</el-button>
      </div>
      <el-alert v-else type="info" :closable="false" description="请先保存目标后再管理里程碑" class="action-hint" />
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import { useGoalStore } from '../stores/goalStore'
import { CATEGORY_OPTIONS, PRIORITY_OPTIONS, STATUS_OPTIONS, COMMON_TAGS } from '../types/goalTypes'
import type { Milestone } from '../types/goalTypes'

const props = defineProps<{ visible: boolean; goalId?: number }>()
const emit = defineEmits<{ 'update:visible': [v: boolean]; saved: [] }>()

const goalStore = useGoalStore()
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  title: '', description: '', category: '', status: '', priority: 'p2', tags: [] as string[],
  reward_value: 0, enable_reward: false, default_reward_amount: 0, start_date: '', deadline: '', notes: '',
  milestones: [] as Array<{ title: string; status: string }>,
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

function addMilestone() { form.milestones.push({ title: '', status: 'pending' }) }
function removeMilestone(i: number) { form.milestones.splice(i, 1) }

watch(() => props.goalId, async (id) => {
  if (!id) {
    form.title = ''; form.description = ''; form.category = ''; form.status = ''
    form.priority = 'p2'; form.tags = []; form.reward_value = 0
    form.enable_reward = false; form.default_reward_amount = 0
    form.start_date = ''; form.deadline = ''; form.notes = ''
    form.milestones = []
    return
  }
  try {
    const goal = await goalStore.fetchGoalById(id)
    if (!goal) return
    form.title = goal.title || ''
    form.description = goal.description || ''
    form.category = goal.category || ''
    form.priority = goal.priority || 'p2'
    form.status = goal.status || ''
    form.tags = goal.tags || []
    form.reward_value = Number(goal.reward_value) || 0
    form.enable_reward = goal.enable_reward ?? false
    form.default_reward_amount = Number(goal.default_reward_amount) || 0
    form.start_date = goal.start_date || ''
    form.deadline = goal.deadline || ''
    form.notes = goal.notes || ''
    form.milestones = (goal.milestones || []).map((m: Milestone) => ({ title: m.title, status: m.status }))
    if (!form.milestones.length) form.milestones.push({ title: '', status: 'pending' })
  } catch { ElMessage.error('加载目标失败') }
})

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const data: Record<string, unknown> = {
      title: form.title?.trim(),
      description: form.description?.trim(),
      category: form.category,
      priority: form.priority,
      status: form.status || undefined,
      tags: form.tags,
      reward_value: form.reward_value,
      enable_reward: form.enable_reward,
      default_reward_amount: form.default_reward_amount,
      start_date: form.start_date || null,
      deadline: form.deadline || null,
      notes: form.notes?.trim(),
      milestones: form.milestones.filter(m => m.title?.trim()),
    }

    if (props.goalId) {
      await goalStore.updateExistingGoal(props.goalId, data)
      ElMessage.success('更新成功')
    } else {
      await goalStore.createNewGoal(data)
      ElMessage.success('创建成功')
    }
    emit('saved')
  } catch { ElMessage.error('操作失败') }
  finally { submitting.value = false }
}
</script>

<style scoped lang="scss">
.goal-form { max-height: 65vh; overflow-y: auto; padding-right: 8px; }
.milestones-editor { display: flex; flex-direction: column; gap: 8px;
  .milestone-row { display: flex; gap: 8px; align-items: center;
    .milestone-input { flex: 1; }
  }
}

.action-hint { margin-top: 4px; }

:deep(.el-divider__text) { font-size: 14px; font-weight: 500; }
</style>
