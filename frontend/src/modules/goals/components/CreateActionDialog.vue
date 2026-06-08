<template>
  <el-dialog
    :model-value="visible"
    :title="dialogTitle"
    width="480px"
    @update:model-value="$emit('update:visible', $event)"
    @close="handleClose"
    destroy-on-close
  >
    <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
      <el-form-item label="行为名称" prop="name">
        <el-input v-model="formData.name" placeholder="请输入行为名称" maxlength="200" />
      </el-form-item>
      <el-form-item label="关联里程碑">
        <el-select v-model="formData.milestone_id" placeholder="不关联（可选）" clearable style="width: 100%">
          <el-option
            v-for="m in mergedMilestones"
            :key="m.id"
            :label="m.title"
            :value="m.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="发生日期">
        <el-date-picker
          v-model="formData.action_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="默认今天，可补录历史日期"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="formData.note" type="textarea" :rows="3" placeholder="备注说明（可选）" maxlength="500" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useGoalBoardStore } from '../stores/goalBoardStore'
import type { Milestone } from '../types/goalTypes'

const props = defineProps<{
  visible: boolean
  goalIds: number[]
  allMilestones: Milestone[]
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  created: []
}>()

const boardStore = useGoalBoardStore()
const formRef = ref()
const submitting = ref(false)

const formData = reactive({
  name: '',
  milestone_id: null as number | null,
  note: '',
  action_date: '',
})

const formRules = {
  name: [{ required: true, message: '请输入行为名称', trigger: 'blur' }],
}

const dialogTitle = computed(() => {
  const count = props.goalIds.length
  return count <= 1 ? '新增行为' : `为 ${count} 个目标新增行为`
})

/** 合并所有选中目标的里程碑，去重 */
const mergedMilestones = computed(() => {
  const seen = new Set<number>()
  const result: Milestone[] = []
  for (const m of props.allMilestones) {
    if (!seen.has(m.id) && props.goalIds.includes(m.goal)) {
      seen.add(m.id)
      result.push(m)
    }
  }
  return result
})

function handleClose() {
  formData.name = ''
  formData.milestone_id = null
  formData.note = ''
  formData.action_date = ''
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await boardStore.batchAddActions(props.goalIds, {
      name: formData.name.trim(),
      milestone_id: formData.milestone_id,
      note: formData.note.trim() || null,
      action_date: formData.action_date || null,
    })
    ElMessage.success('行为已添加')
    emit('created')
    emit('update:visible', false)
  } catch {
    ElMessage.error('添加失败')
  } finally {
    submitting.value = false
  }
}
</script>
