<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance } from 'element-plus'
import { useShowroomStore } from '../stores/showroomStore'
import type { ShowroomSkill } from '../types/showroomTypes'

const props = defineProps<{
  modelValue: boolean
  item: ShowroomSkill | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: Record<string, unknown>]
}>()

const store = useShowroomStore()

// 熟练度三级由后端下发，前端不写第二份文案（口径单一真源）。
const levelOptions = computed(() => store.meta?.skill_levels ?? [])

const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  level: 'proficient',
  is_visible: true,
  sort_order: 0,
})

const rules = {
  name: [{ required: true, message: '填技能名', trigger: 'blur' }],
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const s = props.item
    form.name = s?.name ?? ''
    form.level = s?.level ?? 'proficient'
    form.is_visible = s?.is_visible ?? true
    form.sort_order = s?.sort_order ?? 0
    formRef.value?.clearValidate()
  },
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  await formRef.value?.validate()
  emit('submit', { ...form })
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="item ? '编辑技能' : '新增技能'"
    width="440px"
    destroy-on-close
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      :validate-on-rule-change="false"
      label-width="90px"
    >
      <el-form-item label="技能名" prop="name">
        <el-input v-model="form.name" placeholder="如 Python、AI 工作流" />
      </el-form-item>
      <el-form-item label="熟练度">
        <el-select v-model="form.level" style="width: 100%">
          <el-option
            v-for="o in levelOptions"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
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
