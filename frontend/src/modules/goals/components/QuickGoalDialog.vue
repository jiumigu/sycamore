<template>
  <el-dialog
    v-model="dialogVisible"
    title="快速创建目标"
    width="680px"
    :close-on-click-modal="false"
    @closed="handleClose"
  >
    <el-form :model="form" label-width="120px" class="form-body">
      <el-form-item label="目标名称">
        <el-input v-model="form.goal_name" placeholder="如：2026年日更计划" />
      </el-form-item>

      <el-form-item label="里程碑前缀">
        <el-input v-model="form.milestone_prefix" placeholder="如：日更第" />
      </el-form-item>

      <el-form-item label="时间模式">
        <el-radio-group v-model="form.time_mode">
          <el-radio value="year">年度（1-12月）</el-radio>
          <el-radio value="custom">自定义时间段</el-radio>
        </el-radio-group>
      </el-form-item>

      <template v-if="form.time_mode === 'year'">
        <el-form-item label="年份">
          <el-select v-model="form.year" style="width: 120px">
            <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
          </el-select>
        </el-form-item>
      </template>

      <template v-if="form.time_mode === 'custom'">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始日期">
              <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期">
              <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="频率">
            <el-select v-model="form.frequency" style="width:100%">
              <el-option label="每天" value="daily" />
              <el-option label="每周" value="weekly" />
              <el-option label="每月" value="monthly" />
              <el-option label="每季度" value="quarterly" />
              <el-option label="每年" value="yearly" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="内容排序">
            <el-radio-group v-model="form.content_order">
              <el-radio value="asc">正序（第1天、第2天...）</el-radio>
              <el-radio value="desc">倒序（倒计时84天...倒计时1天）</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="显示排序">
            <el-radio-group v-model="form.display_order">
              <el-radio value="asc">日期从早到晚</el-radio>
              <el-radio value="desc">日期从晚到早</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-col>
      </el-row>

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
      <div v-for="item in previewItems" :key="item.idx" class="preview-milestone">
        <span class="preview-indent">{{ item.name }}</span>
        <span class="preview-date" v-if="item.date">📅 {{ item.date }}</span>
        <span v-if="form.reward > 0" class="preview-reward">💰 ¥{{ form.reward }}</span>
      </div>
      <div v-if="milestoneCount > hiddenCount" class="preview-summary">...共 {{ milestoneCount }} 个里程碑</div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        创建目标 + {{ milestoneCount }} 个里程碑
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
  time_mode: 'year' as 'year' | 'custom',
  start_date: '',
  end_date: '',
  year: new Date().getFullYear(),
  frequency: 'monthly' as 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly',
  content_order: 'asc' as 'asc' | 'desc',
  display_order: 'asc' as 'asc' | 'desc',
  reward: 10,
})

const previewGoalName = computed(() => form.goal_name || '新目标')

const hiddenCount = 5

const milestoneCount = computed(() => {
  const { frequency, start_date, end_date, year } = form
  if (frequency === 'daily') {
    if (!start_date || !end_date) return 0
    const s = new Date(start_date)
    const e = new Date(end_date)
    return Math.floor((e.getTime() - s.getTime()) / 86400000) + 1
  }
  if (frequency === 'weekly') return 52
  if (frequency === 'monthly') return 12
  if (frequency === 'quarterly') return 4
  if (frequency === 'yearly') {
    if (form.time_mode === 'custom' && start_date && end_date) {
      return new Date(end_date).getFullYear() - new Date(start_date).getFullYear() + 1
    }
    return 1
  }
  return 0
})

const previewItems = computed(() => {
  const { milestone_prefix, frequency, start_date, end_date, content_order, display_order, year } = form
  if (!milestone_prefix) return []
  const items: { idx: number; name: string; date?: string }[] = []

  let raw: { idx: number; name: string; date?: string }[] = []

  if (frequency === 'daily') {
    if (!start_date || !end_date) return []
    const s = new Date(start_date)
    const e = new Date(end_date)
    const count = Math.floor((e.getTime() - s.getTime()) / 86400000) + 1
    if (count > 365) return [{ idx: 0, name: '日期范围过长（超过365天），请缩短' }]
    for (let i = 0; i < count; i++) {
      const d = new Date(s.getTime() + i * 86400000)
      const ds = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      const daysLeft = Math.floor((e.getTime() - d.getTime()) / 86400000) + 1
      const name = content_order === 'desc'
        ? `${milestone_prefix}${daysLeft}天`
        : `${milestone_prefix}${i + 1}天`
      raw.push({ idx: i, name, date: ds })
    }
  } else if (frequency === 'weekly') {
    for (let w = 1; w <= 52; w++) raw.push({ idx: w, name: `第${w}周${milestone_prefix}` })
  } else if (frequency === 'monthly') {
    for (let m = 1; m <= 12; m++) raw.push({ idx: m, name: `${m}月${milestone_prefix}` })
  } else if (frequency === 'quarterly') {
    for (let q = 1; q <= 4; q++) raw.push({ idx: q, name: `Q${q}${milestone_prefix}` })
  } else if (frequency === 'yearly') {
    let startY = year
    let endY = year
    if (form.time_mode === 'custom' && start_date && end_date) {
      startY = new Date(start_date).getFullYear()
      endY = new Date(end_date).getFullYear()
    }
    for (let y = startY; y <= endY; y++) raw.push({ idx: y, name: `${y}年${milestone_prefix}` })
  }

  const total = raw.length
  if (display_order === 'desc') raw.reverse()

  const showCount = Math.min(total, hiddenCount)
  for (let i = 0; i < showCount; i++) items.push(raw[i])

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
    const params: Record<string, any> = {
      name: form.goal_name.trim(),
      milestone_prefix: form.milestone_prefix.trim(),
      year: form.year,
      frequency: form.frequency,
      reward_per_milestone: form.reward,
      content_order: form.content_order,
      display_order: form.display_order,
    }
    if (form.start_date) params.start_date = form.start_date
    if (form.end_date) params.end_date = form.end_date
    await goalStore.quickCreateGoal(params)
    ElMessage.success(`目标「${form.goal_name.trim()}」已创建，含 ${milestoneCount.value} 个里程碑`)
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
  form.time_mode = 'year'
  form.start_date = ''
  form.end_date = ''
  form.year = new Date().getFullYear()
  form.frequency = 'monthly'
  form.content_order = 'asc'
  form.display_order = 'asc'
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

  .preview-date {
    font-size: 11px;
    color: var(--el-text-color-secondary);
  }

  .preview-summary {
    padding: 4px 0 0 16px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .preview-reward {
    color: var(--el-color-success);
    font-size: 12px;
  }
}
</style>
