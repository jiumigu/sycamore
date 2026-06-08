<template>
  <el-dialog v-model="visible" title="🔄 转为其他模块" width="480px" :close-on-click-modal="false">
    <div class="convert-options">
      <div
        v-for="opt in convertOptions"
        :key="opt.action"
        class="convert-option"
        :class="{ selected: action === opt.action }"
        @click="action = opt.action"
      >
        <span class="convert-icon">{{ opt.icon }}</span>
        <div class="convert-info">
          <div class="convert-title">{{ opt.title }}</div>
          <div class="convert-desc">{{ opt.desc }}</div>
        </div>
      </div>
    </div>

    <el-form v-if="item" class="convert-form" label-position="top">
      <el-form-item label="内容">
        <el-input :model-value="item.content" disabled type="textarea" :rows="2" />
      </el-form-item>

      <!-- 转为里程碑时：选择目标、里程碑名称、截止日期 -->
      <template v-if="action === 'convert_to_milestone'">
        <el-form-item label="所属目标">
          <el-select v-model="goalId" placeholder="选择目标" filterable style="width: 100%" :loading="goalsLoading">
            <el-option
              v-for="g in goals"
              :key="g.id"
              :label="g.title"
              :value="g.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="里程碑名称">
          <el-input v-model="milestoneName" :placeholder="'默认为：' + (item?.content || '')" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="targetDate" type="date" placeholder="选填" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </template>

      <el-form-item label="备注">
        <el-input v-model="notes" placeholder="可选备注" :rows="2" type="textarea" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="store.saving" @click="handleConvert">确认转换</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useInboxStore } from '../stores/inboxStore'
import type { InboxItem } from '../types/inboxTypes'
import * as goalsApi from '@/modules/goals/api/goalApi'

interface GoalItem {
  id: number
  title: string
  status: string
}

const store = useInboxStore()

const props = defineProps<{
  visible: boolean
  item: InboxItem | null
}>()

const emit = defineEmits<{
  'update:visible': [v: boolean]
}>()

const visible = ref(false)
const action = ref('convert_to_goal')
const notes = ref('')

// 里程碑专用字段
const goalId = ref<number | null>(null)
const milestoneName = ref('')
const targetDate = ref('')
const goals = ref<GoalItem[]>([])
const goalsLoading = ref(false)

const convertOptions = [
  { action: 'convert_to_goal', icon: '🎯', title: '转为目标', desc: '移到目标管理，长期跟进' },
  { action: 'convert_to_milestone', icon: '🏁', title: '转为里程碑', desc: '关联到已有目标，持续追踪' },
  { action: 'convert_to_sugar', icon: '⚡', title: '转为能量', desc: '移到能量清单，提升幸福感' },
]

watch(() => props.visible, (v) => {
  visible.value = v
  if (v) {
    action.value = 'convert_to_goal'
    notes.value = ''
    goalId.value = null
    milestoneName.value = ''
    targetDate.value = ''
    fetchGoals()
  }
})
watch(visible, (v) => { emit('update:visible', v) })

async function fetchGoals() {
  goalsLoading.value = true
  try {
    const res = await goalsApi.getGoalList({ status: 'in-progress' })
    const data = res.data
    goals.value = (data.results || data) as GoalItem[]
  } catch {
    goals.value = []
  } finally {
    goalsLoading.value = false
  }
}

async function handleConvert() {
  if (!props.item) return

  const extra: Record<string, unknown> = { notes: notes.value }

  if (action.value === 'convert_to_milestone') {
    if (!goalId.value) {
      ElMessage.warning('请选择所属目标')
      return
    }
    extra.goal_id = goalId.value
    extra.milestone_name = milestoneName.value || ''
    extra.target_date = targetDate.value || ''
  }

  await store.convertItem(props.item.id, action.value, extra)
  action.value = 'convert_to_goal'
  notes.value = ''
  goalId.value = null
  milestoneName.value = ''
  targetDate.value = ''
}
</script>

<style scoped>
.convert-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.convert-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.convert-option:hover {
  border-color: #3B82F6;
  background: #EFF6FF;
}
.convert-option.selected {
  border-color: #3B82F6;
  background: #EFF6FF;
}
.convert-icon {
  font-size: 24px;
}
.convert-title {
  font-weight: 600;
  font-size: 14px;
  color: #1F2937;
}
.convert-desc {
  font-size: 12px;
  color: #6B7280;
}
.convert-form {
  border-top: 1px solid #E5E7EB;
  padding-top: 16px;
}
</style>
