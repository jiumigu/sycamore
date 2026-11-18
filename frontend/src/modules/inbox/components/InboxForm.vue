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
            <el-select v-model="form.category" placeholder="选择或输入新类型" allow-create filterable style="width: 100%">
              <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="`${c.icon} ${c.label}`" :value="c.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="状态">
            <el-select v-model="form.status" style="width: 100%">
              <!-- 🔴 选项来自 `STATUS_OPTIONS`（唯一一份），不在这里手写。
                   此前这里只写了三项（待处理/犹豫中/已废弃），于是打开一条
                   已完成的条目时，选中值 `done` 在选项里找不到 ⇒ 下拉显示裸
                   英文 `done`，用户既看不懂、也没法把它改回去。 -->
              <el-option v-for="s in SELECTABLE_STATUS" :key="s.value" :label="s.label" :value="s.value" />
              <!-- 「已处理」不是选出来的：它是「转为…」的动作**结果**（带 target）。
                   留着这一项只为两件事：打开一条已转出的条目时仍显示中文；
                   让人看见它不能手选，以及为什么。 -->
              <el-option label="已处理（由「转为…」自动设置）" value="processed" disabled />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="截止日期">
            <el-date-picker v-model="form.due_date" type="date" placeholder="选填" style="width: 100%" value-format="YYYY-MM-DD" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="优先级">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option label="🔴 高" value="high" />
              <el-option label="🟡 中" value="medium" />
              <el-option label="🟢 低" value="low" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item v-if="form.status === 'hesitating'" label="犹豫原因">
        <el-input v-model="form.hesitate_reason" type="textarea" :rows="2"
          placeholder="是什么让你不敢开始？怕失败？怕被评价？还是不确定值不值得？" />
      </el-form-item>
      <!-- 完成备注（v3.64.83）：标记完成时填过，但打开编辑**看不到** ——
           于是想补一句「其实是这样做的」只能重填。与下面两个原因同构：
           状态是哪个，就只露它对应的那一段。 -->
      <el-form-item v-if="form.status === 'done'" label="完成备注">
        <el-input v-model="form.completion_note" type="textarea" :rows="3"
          placeholder="做完了，留下点什么？结果、感受、下次要注意的…（选填）" />
      </el-form-item>
      <el-form-item v-if="form.status === 'abandoned'" label="废弃原因">
        <el-input v-model="form.abandon_reason" type="textarea" :rows="2"
          placeholder="为什么不做了？不合理？时过境迁？" />
      </el-form-item>
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
import { computed, ref, reactive, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import { CATEGORY_OPTIONS, STATUS_OPTIONS } from '../types/inboxTypes'
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

/** 能在下拉里**选**的状态 = 全部状态 −「已处理」。
 *  已处理是转换动作的结果（带 `target_type/target_id`），手选它等于写一条
 *  「转过、但转到哪不知道」的记录。它作为 disabled 项另列，见模板。 */
const SELECTABLE_STATUS = computed(() => STATUS_OPTIONS.filter(s => s.value !== 'processed'))

const form = reactive({
  content: '',
  description: '',
  category: 'other',
  status: 'pending',
  priority: 'medium',
  due_date: '',
  tags: '',
  hesitate_reason: '',
  abandon_reason: '',
  completion_note: '',
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
    form.status = props.item.status || 'pending'
    form.priority = props.item.priority
    form.due_date = props.item.due_date ?? ''
    form.tags = props.item.tags ?? ''
    form.hesitate_reason = props.item.hesitate_reason ?? ''
    form.abandon_reason = props.item.abandon_reason ?? ''
    form.completion_note = props.item.completion_note ?? ''
  } else if (v && !props.item) {
    isEdit.value = false
    form.content = ''
    form.description = ''
    form.category = 'other'
    form.status = 'pending'
    form.priority = 'medium'
    form.due_date = ''
    form.tags = ''
    form.hesitate_reason = ''
    form.abandon_reason = ''
    form.completion_note = ''
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
    status: form.status,
    priority: form.priority,
    tags: form.tags || null,
    due_date: form.due_date || null,
    hesitate_reason: form.hesitate_reason || '',
    abandon_reason: form.abandon_reason || '',
    completion_note: form.completion_note || '',
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
