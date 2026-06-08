<template>
  <el-dialog
    v-model="visible"
    :title="editingId ? '编辑产出记录' : '记录事项'"
    width="600px"
    :close-on-click-modal="false"
    @closed="handleClose"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="事项名称">
        <el-input v-model="form.title" placeholder="如：完成项目评审" />
      </el-form-item>

      <el-form-item label="类别">
        <el-select v-model="form.category" style="width: 100%">
          <el-option value="work" label="💼 工作" />
          <el-option value="writing" label="✍️ 写作" />
          <el-option value="social" label="💬 社交" />
          <el-option value="study" label="📚 学习" />
          <el-option value="health" label="🏃 健康" />
          <el-option value="life" label="生活" />
          <el-option value="other" label="其他" />
        </el-select>
      </el-form-item>

      <el-form-item label="质量判定">
        <el-radio-group v-model="form.quality" class="quality-group">
          <el-radio value="good" class="quality-radio">
            ✅ 良品（达到预期）
          </el-radio>
          <el-radio value="defective" class="quality-radio">
            ⚠️ 不良品（未达预期，可接受）
          </el-radio>
          <el-radio value="waste" class="quality-radio">
            ❌ 废品（彻底搞砸）
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="难度">
        <el-radio-group v-model="form.difficulty" class="difficulty-group">
          <el-radio :value="1" class="difficulty-radio">1 轻车熟路</el-radio>
          <el-radio :value="2" class="difficulty-radio">2 稍需思考</el-radio>
          <el-radio :value="3" class="difficulty-radio">3 需要努力</el-radio>
          <el-radio :value="4" class="difficulty-radio">4 挑战较大</el-radio>
          <el-radio :value="5" class="difficulty-radio">5 完全未知</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="预期结果">
        <el-input v-model="form.expected_result" type="textarea" :rows="2" placeholder="做这件事之前，你期望的结果是什么？" />
      </el-form-item>

      <el-form-item label="实际结果">
        <el-input v-model="form.actual_result" type="textarea" :rows="2" placeholder="实际发生了什么？" />
      </el-form-item>

      <template v-if="form.quality !== 'good'">
        <el-form-item label="失败原因">
          <el-input v-model="form.fail_reason" type="textarea" :rows="2" placeholder="为什么没达到预期？" />
        </el-form-item>
        <el-form-item label="失败类型">
          <el-select v-model="form.fail_type" placeholder="选择主要失败类型" style="width: 100%">
            <el-option v-for="f in FAIL_TYPE_OPTIONS" :key="f.value" :label="f.label" :value="f.value" />
          </el-select>
        </el-form-item>
      </template>

      <el-form-item label="经验教训">
        <el-input v-model="form.lesson_learned" type="textarea" :rows="2" placeholder="从中学到了什么？" />
      </el-form-item>

      <el-form-item label="发生日期">
        <el-date-picker v-model="form.occurred_at" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { FAIL_TYPE_OPTIONS } from '../types/outputTypes'
import type { OutputRecord } from '../types/outputTypes'
import { useOutputStore } from '../stores/outputStore'

const store = useOutputStore()

const props = defineProps<{
  visible: boolean
  record?: OutputRecord | null
}>()

const emit = defineEmits<{
  'update:visible': [v: boolean]
  saved: []
}>()

const visible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = reactive({
  title: '',
  category: 'other',
  quality: 'good',
  difficulty: 3,
  expected_result: '',
  actual_result: '',
  fail_reason: '',
  fail_type: '',
  lesson_learned: '',
  occurred_at: '',
})

function resetForm() {
  form.title = ''
  form.category = 'other'
  form.quality = 'good'
  form.difficulty = 3
  form.expected_result = ''
  form.actual_result = ''
  form.fail_reason = ''
  form.fail_type = ''
  form.lesson_learned = ''
  form.occurred_at = ''
}

watch(() => props.visible, (v) => {
  visible.value = v
  if (v && props.record) {
    editingId.value = props.record.id
    form.title = props.record.title
    form.category = props.record.category
    form.quality = props.record.quality
    form.difficulty = props.record.difficulty
    form.expected_result = props.record.expected_result || ''
    form.actual_result = props.record.actual_result || ''
    form.fail_reason = props.record.fail_reason || ''
    form.fail_type = props.record.fail_type || ''
    form.lesson_learned = props.record.lesson_learned || ''
    form.occurred_at = props.record.occurred_at || ''
  } else if (v && !props.record) {
    editingId.value = null
    resetForm()
    form.occurred_at = new Date().toISOString().slice(0, 10)
  }
})
watch(visible, (v) => { emit('update:visible', v) })

function handleClose() {
  resetForm()
  editingId.value = null
}

async function handleSubmit() {
  if (!form.title.trim()) {
    ElMessage.warning('请输入事项名称')
    return
  }
  saving.value = true
  try {
    const data: Record<string, unknown> = {
      title: form.title.trim(),
      category: form.category,
      quality: form.quality,
      difficulty: form.difficulty,
      expected_result: form.expected_result || '',
      actual_result: form.actual_result || '',
      fail_reason: form.fail_reason || '',
      fail_type: form.fail_type || '',
      lesson_learned: form.lesson_learned || '',
      occurred_at: form.occurred_at || null,
    }

    if (editingId.value) {
      await store.updateRecord(editingId.value, data)
    } else {
      await store.createRecord(data)
    }
    visible.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.quality-group, .difficulty-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quality-radio, .difficulty-radio {
  margin-right: 0;
}
</style>
