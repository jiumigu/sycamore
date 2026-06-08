<template>
  <el-dialog v-model="visible" :title="isEdit ? '✏️ 编辑条目' : '📝 条目详情'" width="520px">
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="内容" prop="content">
        <el-input v-model="form.content" :rows="2" type="textarea" />
      </el-form-item>
      <el-form-item label="详细描述">
        <el-input v-model="form.description" :rows="3" type="textarea" placeholder="选填" />
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="8">
          <el-form-item label="类别">
            <el-select v-model="form.category" style="width: 100%">
              <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="`${c.icon} ${c.label}`" :value="c.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="优先级">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option label="🔴 高" value="high" />
              <el-option label="🟡 中" value="medium" />
              <el-option label="🟢 低" value="low" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="截止日期">
            <el-date-picker v-model="form.due_date" type="date" placeholder="选填" style="width: 100%" value-format="YYYY-MM-DD" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="标签">
        <el-input v-model="form.tags" placeholder="逗号分隔，如：生活,工作" />
      </el-form-item>

      <div v-if="item?.process_logs?.length" class="process-logs">
        <div class="logs-title">处理记录</div>
        <div v-for="log in item.process_logs" :key="log.id" class="log-item">
          <span class="log-action">{{ log.action_display }}</span>
          <span class="log-date">{{ log.created_at?.slice(0, 10) }}</span>
          <span v-if="log.notes" class="log-notes">{{ log.notes }}</span>
        </div>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="store.saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import { CATEGORY_OPTIONS } from '../types/inboxTypes'
import type { InboxItem } from '../types/inboxTypes'
import { useInboxStore } from '../stores/inboxStore'

const store = useInboxStore()

const props = defineProps<{
  visible: boolean
  item: InboxItem | null
}>()

const emit = defineEmits<{
  'update:visible': [v: boolean]
}>()

const visible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  content: '',
  description: '',
  category: 'other',
  priority: 'medium',
  due_date: '',
  tags: '',
})

const rules = {
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

watch(() => props.visible, (v) => {
  visible.value = v
  if (v && props.item) {
    isEdit.value = true
    form.content = props.item.content
    form.description = props.item.description ?? ''
    form.category = props.item.category
    form.priority = props.item.priority
    form.due_date = props.item.due_date ?? ''
    form.tags = props.item.tags ?? ''
  } else if (v && !props.item) {
    isEdit.value = false
    form.content = ''
    form.description = ''
    form.category = 'other'
    form.priority = 'medium'
    form.due_date = ''
    form.tags = ''
  }
})
watch(visible, (v) => { emit('update:visible', v) })

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const data: Record<string, unknown> = {
    content: form.content,
    description: form.description || null,
    category: form.category,
    priority: form.priority,
    tags: form.tags || null,
    due_date: form.due_date || null,
  }

  if (props.item) {
    await store.updateItem(props.item.id, data)
  } else {
    await store.createItem(data)
  }
}
</script>

<style scoped>
.process-logs {
  border-top: 1px solid #E5E7EB;
  padding-top: 12px;
  margin-top: 8px;
}
.logs-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}
.log-item {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #6B7280;
  padding: 4px 0;
}
.log-action {
  font-weight: 500;
  color: #374151;
}
.log-notes {
  color: #9CA3AF;
}
</style>
