<template>
  <el-dialog
    v-model="visible"
    :title="editingId ? '编辑记录' : '记一件事'"
    width="560px"
    :close-on-click-modal="false"
    @closed="handleClose"
  >
    <el-form :model="form" label-width="88px">
      <el-form-item label="事项" required>
        <el-input v-model="form.title" placeholder="一句话说清做了什么" maxlength="200" show-word-limit />
      </el-form-item>

      <el-form-item label="结果" required>
        <!-- 🔴 不给默认值：原来默认「良品」，等于把不选的人一律算成成功，
             良品率被这个默认值悄悄抬高。必须真的选一次。 -->
        <el-radio-group v-model="form.quality" class="quality-group">
          <el-radio value="good" class="quality-radio">✅ 良品（达到预期）</el-radio>
          <el-radio value="defective" class="quality-radio">⚠️ 不良品（没到预期，可接受）</el-radio>
          <el-radio value="waste" class="quality-radio">❌ 废品（这次白做）</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="发生在" required>
        <el-date-picker
          v-model="form.occurred_at"
          type="date"
          placeholder="选择日期"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="类别" required>
        <el-select v-model="form.category" placeholder="选一个" style="width: 100%">
          <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
      </el-form-item>

      <!-- 没达到预期才要答案：为什么 + 属于哪一类（后者是「下次改什么」的唯一来源） -->
      <template v-if="form.quality && form.quality !== 'good'">
        <el-form-item label="类型" required>
          <el-select v-model="form.fail_type" placeholder="主要是什么原因" style="width: 100%">
            <el-option v-for="f in FAIL_TYPE_OPTIONS" :key="f.value" :label="f.label" :value="f.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="为什么">
          <el-input
            v-model="form.fail_reason"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="一句话就够，不用写检讨"
          />
        </el-form-item>
      </template>

      <el-collapse class="more-box">
        <el-collapse-item title="补充（选填）" name="more">
          <el-form-item label="实际结果">
            <el-input
              v-model="form.actual_result"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 5 }"
              placeholder="实际发生了什么？"
            />
          </el-form-item>
          <el-form-item label="下次改什么">
            <el-input
              v-model="form.lesson_learned"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 5 }"
              placeholder="写一句下次能照着做的动作"
            />
          </el-form-item>
        </el-collapse-item>
      </el-collapse>
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
import { CATEGORY_OPTIONS, FAIL_TYPE_OPTIONS } from '../types/outputTypes'
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

/** 本地今天（不能用 `toISOString()`：那是 UTC，晚上 8 点后会跳成明天） */
function todayLocal(): string {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

const form = reactive({
  title: '',
  category: '',
  quality: '',
  actual_result: '',
  fail_reason: '',
  fail_type: '',
  lesson_learned: '',
  occurred_at: '',
})

function resetForm() {
  form.title = ''
  form.category = ''
  form.quality = ''
  form.actual_result = ''
  form.fail_reason = ''
  form.fail_type = ''
  form.lesson_learned = ''
  form.occurred_at = todayLocal()
}

watch(() => props.visible, (v) => {
  visible.value = v
  if (v && props.record) {
    editingId.value = props.record.id
    form.title = props.record.title
    form.category = props.record.category
    form.quality = props.record.quality
    form.actual_result = props.record.actual_result || ''
    form.fail_reason = props.record.fail_reason || ''
    form.fail_type = props.record.fail_type || ''
    form.lesson_learned = props.record.lesson_learned || ''
    // 老记录可能没有发生日期（历史上选填），编辑时补上而不是留空
    form.occurred_at = props.record.occurred_at || todayLocal()
  } else if (v && !props.record) {
    editingId.value = null
    resetForm()
  }
})
watch(visible, (v) => { emit('update:visible', v) })

function handleClose() {
  resetForm()
  editingId.value = null
}

async function handleSubmit() {
  if (!form.title.trim()) {
    ElMessage.warning('写一句做了什么')
    return
  }
  if (!form.quality) {
    ElMessage.warning('选一下结果（良品 / 不良品 / 废品）')
    return
  }
  if (!form.occurred_at) {
    // 不填日期 ⇒ 这条记录进不了任何按日期过滤的统计，等于白记
    ElMessage.warning('选一下发生日期')
    return
  }
  if (!form.category) {
    ElMessage.warning('选一下类别')
    return
  }
  if (form.quality !== 'good' && !form.fail_type) {
    ElMessage.warning('选一下失败类型 —— 「最常见原因」全靠这一项')
    return
  }

  saving.value = true
  try {
    const data: Record<string, unknown> = {
      title: form.title.trim(),
      category: form.category,
      quality: form.quality,
      actual_result: form.actual_result || '',
      fail_reason: form.fail_reason || '',
      // 良品不该带失败类型，否则「按类型统计」会把成功的也算进去
      fail_type: form.quality === 'good' ? '' : (form.fail_type || ''),
      lesson_learned: form.lesson_learned || '',
      occurred_at: form.occurred_at,
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
.quality-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quality-radio {
  margin-right: 0;
}

.more-box {
  margin-top: 4px;
  border-top: 1px solid #F3F4F6;

  :deep(.el-collapse-item__header) {
    font-size: 13px;
    color: #6B7280;
    border-bottom: none;
  }
  :deep(.el-collapse-item__wrap) { border-bottom: none; }
}
</style>
