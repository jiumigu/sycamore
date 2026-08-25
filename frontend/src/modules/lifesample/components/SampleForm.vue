<template>
  <el-dialog
    :title="editingId ? '编辑人生样本' : '新建人生样本'"
    v-model="visible"
    width="560px"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="姓名" prop="name">
        <el-input v-model="form.name" placeholder="请输入姓名" />
      </el-form-item>

      <el-form-item label="别名">
        <el-input v-model="form.alias" placeholder="请输入别名" />
      </el-form-item>

      <el-form-item label="类型" prop="sample_type">
        <el-select v-model="form.sample_type" placeholder="请选择类型">
          <el-option
            v-for="(label, value) in SampleTypeLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="标签">
        <el-select
          v-model="form.tags"
          multiple
          filterable
          allow-create
          default-first-option
          placeholder="输入标签，回车创建"
        >
          <el-option
            v-for="tag in existingTags"
            :key="tag"
            :label="tag"
            :value="tag"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="一句话简介">
        <el-input
          v-model="form.summary"
          placeholder="一句话概括这个人"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <el-divider content-position="left">📋 状态与审阅</el-divider>

      <el-form-item label="状态" prop="status">
        <el-radio-group v-model="form.status">
          <el-radio-button
            v-for="(config, key) in StatusConfig"
            :key="key"
            :value="key"
          >
            {{ config.icon }} {{ config.label }}
          </el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="借鉴意义" prop="relevance">
        <el-radio-group v-model="form.relevance">
          <el-radio-button
            v-for="(config, key) in RelevanceConfig"
            :key="key"
            :value="key"
          >
            {{ config.icon }} {{ config.label }}
          </el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="评级理由">
        <el-input
          v-model="form.relevance_reason"
          placeholder="为什么这个样本对你有这个级别的借鉴意义？"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="Obsidian路径">
        <el-input
          v-model="form.obsidian_path"
          placeholder="如：LifeSamples/曾国藩.md"
        />
        <div class="form-hint">相对于 Obsidian 仓库根目录的路径</div>
      </el-form-item>

      <el-form-item label="我的笔记">
        <el-input
          v-model="form.my_note"
          type="textarea"
          :rows="3"
          placeholder="这个人教会了我什么？"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="submitting">
        {{ editingId ? '更新' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, reactive } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { SampleTypeLabels, StatusConfig, RelevanceConfig } from '../types'
import type { LifeSample, LifeSampleForm } from '../types'

const props = defineProps<{
  modelValue: boolean
  initialData?: LifeSample | null
  existingTags?: string[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'submit', data: LifeSampleForm): void
}>()

const visible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number | null>(null)

const defaultForm: LifeSampleForm = {
  name: '',
  alias: '',
  sample_type: 'historical',
  tags: [],
  summary: '',
  obsidian_path: '',
  my_note: '',
  status: 'collected',
  relevance: 'knowledge',
  relevance_reason: '',
}

const form = reactive<LifeSampleForm>({ ...defaultForm })

const rules: FormRules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  sample_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
    if (val && props.initialData) {
      editingId.value = props.initialData.id
      Object.assign(form, {
        name: props.initialData.name || '',
        alias: props.initialData.alias || '',
        sample_type: props.initialData.sample_type || 'historical',
        tags: props.initialData.tags || [],
        summary: props.initialData.summary || '',
        obsidian_path: props.initialData.obsidian_path || '',
        my_note: props.initialData.my_note || '',
        status: props.initialData.status || 'collected',
        relevance: props.initialData.relevance || 'knowledge',
        relevance_reason: props.initialData.relevance_reason || '',
      })
    } else if (val) {
      editingId.value = null
      Object.assign(form, { ...defaultForm })
    }
  },
)

const handleClose = () => {
  emit('update:modelValue', false)
}

const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (valid) {
    submitting.value = true
    try {
      emit('submit', { ...form })
    } finally {
      submitting.value = false
    }
  }
}
</script>

<style scoped>
.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
