<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import type { ShowroomCase, ShowroomMedia } from '../types/showroomTypes'
import { uploadShowroomMedia } from '../api/showroomApi'
import MediaPicker from '@/shared/components/MediaPicker.vue'

const props = defineProps<{
  modelValue: boolean
  item: ShowroomCase | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: Record<string, unknown>]
}>()

const formRef = ref<FormInstance>()
const form = reactive({
  title: '',
  client: '',
  time_label: '',
  problem: '',
  result: '',
  skill_tags: [] as string[],
  media: [] as ShowroomMedia[],
  is_visible: true,
  sort_order: 0,
})

const rules = {
  title: [{ required: true, message: '给案例起个标题', trigger: 'blur' }],
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const c = props.item
    form.title = c?.title ?? ''
    form.client = c?.client ?? ''
    form.time_label = c?.time_label ?? ''
    form.problem = c?.problem ?? ''
    form.result = c?.result ?? ''
    form.skill_tags = c?.skill_tags ? [...c.skill_tags] : []
    form.media = c?.media ? [...c.media] : []
    form.is_visible = c?.is_visible ?? true
    form.sort_order = c?.sort_order ?? 0
    formRef.value?.clearValidate()
  },
)

function close() {
  emit('update:modelValue', false)
}

async function uploadMedia(file: File) {
  const res = await uploadShowroomMedia(file)
  return res.data
}

async function submit() {
  await formRef.value?.validate()
  emit('submit', { ...form, skill_tags: [...form.skill_tags], media: [...form.media] })
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="item ? '编辑案例' : '新增案例'"
    width="600px"
    destroy-on-close
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :validate-on-rule-change="false"
      label-width="110px"
    >
      <el-form-item label="案例标题" prop="title">
        <el-input v-model="form.title" placeholder="一句话说清这是什么事" />
      </el-form-item>
      <el-form-item label="客户 / 对象">
        <el-input v-model="form.client" placeholder="给谁做的（可留空）" />
      </el-form-item>
      <el-form-item label="时间">
        <el-input v-model="form.time_label" placeholder="如 2026 年 9 月" />
      </el-form-item>
      <el-form-item label="解决了什么问题">
        <el-input v-model="form.problem" type="textarea" :rows="3" placeholder="客户当时卡在哪" />
      </el-form-item>
      <el-form-item label="成果">
        <el-input v-model="form.result" type="textarea" :rows="3" placeholder="做完之后可量化的变化" />
      </el-form-item>
      <el-form-item label="用到的技能">
        <el-select
          v-model="form.skill_tags"
          multiple
          filterable
          allow-create
          default-first-option
          :reserve-keyword="false"
          placeholder="回车添加一个技能"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="配图 / 视频">
        <MediaPicker v-model="form.media" :upload="uploadMedia" />
      </el-form-item>
      <el-form-item label="是否展示">
        <el-switch v-model="form.is_visible" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>
