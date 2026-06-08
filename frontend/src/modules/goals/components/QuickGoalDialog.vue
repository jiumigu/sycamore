<template>
  <el-dialog
    v-model="dialogVisible"
    title="快速创建目标"
    width="520px"
    :close-on-click-modal="false"
    @closed="handleClose"
  >
    <el-form :model="form" label-width="120px" class="form-body">
      <el-form-item label="目标名称">
        <el-input v-model="form.goal_name" placeholder="如：2026年月度复盘" />
      </el-form-item>

      <el-form-item label="里程碑名称前缀">
        <el-input v-model="form.milestone_prefix" placeholder="如：复盘" />
      </el-form-item>

      <el-form-item label="年份">
        <el-select v-model="form.year" style="width: 120px">
          <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
        </el-select>
      </el-form-item>

      <el-form-item label="频率">
        <el-radio-group v-model="form.frequency">
          <el-radio value="monthly">每月</el-radio>
          <el-radio value="quarterly">每季度</el-radio>
          <el-radio value="weekly">每周</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="奖励金额">
        <el-input-number v-model="form.reward" :min="0" :precision="2" :step="5" />
        <span class="suffix">元/里程碑</span>
      </el-form-item>
    </el-form>

    <!-- 预览 -->
    <el-alert
      title="预览"
      type="info"
      :closable="false"
      style="margin-top: 12px;"
    />
    <div class="preview-list">
      <div class="preview-goal">
        <el-icon style="margin-right: 4px;"><Flag /></el-icon>
        <strong>{{ previewGoalName }}</strong>
      </div>
      <div v-for="item in milestoneLabels" :key="item.idx" class="preview-milestone">
        <span class="preview-indent">{{ item.name }}</span>
        <span v-if="form.reward > 0" class="preview-reward">💰 ¥{{ form.reward }}</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        创建目标 + {{ milestoneLabels.length }} 个里程碑
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Flag } from '@element-plus/icons-vue'
import { useGoalStore } from '../stores/goalStore'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  created: []
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const goalStore = useGoalStore()
const submitting = ref(false)

const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return [y - 1, y, y + 1, y + 2]
})

const form = reactive({
  goal_name: '',
  milestone_prefix: '',
  year: new Date().getFullYear(),
  frequency: 'monthly' as 'monthly' | 'quarterly' | 'weekly',
  reward: 10,
})

const previewGoalName = computed(() => form.goal_name || `${form.year}年月度复盘`)

const milestoneLabels = computed(() => {
  const { milestone_prefix, frequency } = form
  if (!milestone_prefix) return []
  const items: { idx: number; name: string }[] = []
  if (frequency === 'monthly') {
    for (let m = 1; m <= 12; m++) items.push({ idx: m, name: `${m}月${milestone_prefix}` })
  } else if (frequency === 'quarterly') {
    for (let q = 1; q <= 4; q++) items.push({ idx: q, name: `Q${q}${milestone_prefix}` })
  } else if (frequency === 'weekly') {
    for (let w = 1; w <= 52; w++) items.push({ idx: w, name: `第${w}周${milestone_prefix}` })
  }
  return items
})

async function handleSubmit() {
  if (!form.goal_name.trim()) {
    ElMessage.warning('请输入目标名称')
    return
  }
  if (!form.milestone_prefix.trim()) {
    ElMessage.warning('请输入里程碑名称前缀')
    return
  }
  submitting.value = true
  try {
    await goalStore.quickCreateGoal({
      name: form.goal_name.trim(),
      milestone_prefix: form.milestone_prefix.trim(),
      year: form.year,
      frequency: form.frequency,
      reward_per_milestone: form.reward,
    })
    ElMessage.success(`目标「${form.goal_name.trim()}」已创建，含 ${milestoneLabels.value.length} 个里程碑`)
    emit('created')
    dialogVisible.value = false
  } catch {
    ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  form.goal_name = ''
  form.milestone_prefix = ''
  form.year = new Date().getFullYear()
  form.frequency = 'monthly'
  form.reward = 10
}
</script>

<style scoped lang="scss">
.form-body {
  margin-top: 8px;
}

.suffix {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.preview-list {
  max-height: 260px;
  overflow-y: auto;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 10px 12px;
  margin-top: 4px;

  .preview-goal {
    display: flex;
    align-items: center;
    font-size: 14px;
    margin-bottom: 6px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--el-border-color-light);
  }

  .preview-milestone {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 0;
    font-size: 13px;

    .preview-indent {
      padding-left: 16px;
    }
  }

  .preview-reward {
    color: var(--el-color-success);
    font-size: 12px;
  }
}
</style>
