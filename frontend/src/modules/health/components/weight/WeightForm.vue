<template>
  <el-dialog
    v-model="visible"
    title="✏️ 记录体重"
    width="480px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" label-position="left">
      <el-form-item label="日期" prop="record_date">
        <el-date-picker v-model="form.record_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
      </el-form-item>

      <el-form-item label="体重" prop="weight_jin">
        <el-input-number v-model="form.weight_jin" :min="50" :max="400" :precision="1" :step="0.5" style="width: 100%">
          <template #suffix>斤</template>
        </el-input-number>
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="体脂率" prop="body_fat">
            <el-input-number v-model="form.body_fat" :min="5" :max="50" :precision="1" :step="0.1" style="width: 100%" placeholder="选填" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="测量时间" prop="measure_time">
            <el-select v-model="form.measure_time" placeholder="选填" clearable style="width: 100%">
              <el-option v-for="item in MEASURE_TIME_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="备注" prop="notes">
        <el-input v-model="form.notes" placeholder="如：早餐前空腹" maxlength="200" show-word-limit />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { FormInstance } from 'element-plus'
import { MEASURE_TIME_OPTIONS } from '../../types/healthTypes'
import type { WeightRecord } from '../../types/healthTypes'

const props = defineProps<{
  modelValue: boolean
  record?: WeightRecord | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [data: Record<string, unknown>]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const formRef = ref<FormInstance>()

const form = ref({
  record_date: '',
  weight_jin: undefined as number | undefined,
  body_fat: undefined as number | undefined,
  measure_time: '',
  notes: '',
})

const rules = {
  record_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  weight_jin: [{ required: true, message: '请输入体重', trigger: 'blur' }],
}

function resetForm() {
  form.value = {
    record_date: '',
    weight_jin: undefined,
    body_fat: undefined,
    measure_time: '',
    notes: '',
  }
}

function loadRecord(record: WeightRecord | null) {
  if (record) {
    form.value = {
      record_date: record.record_date,
      weight_jin: record.weight_jin || undefined,
      body_fat: record.body_fat ? parseFloat(record.body_fat) : undefined,
      measure_time: record.measure_time || '',
      notes: record.notes || '',
    }
  } else {
    resetForm()
  }
}

defineExpose({ loadRecord })

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  // Convert 斤 → kg for the API
  const data: Record<string, unknown> = { ...form.value }
  data.weight_kg = (form.value.weight_jin || 0) / 2
  delete data.weight_jin
  emit('submit', data)
}

function handleClose() {
  formRef.value?.resetFields()
  resetForm()
}
</script>
