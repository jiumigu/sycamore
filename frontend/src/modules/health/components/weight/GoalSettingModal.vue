<template>
  <el-dialog
    v-model="visible"
    title="🎯 设定减重目标"
    width="520px"
    :close-on-click-modal="false"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" label-position="left">
      <el-form-item label="当前体重" prop="start_weight_jin">
        <el-input-number v-model="form.start_weight_jin" :min="50" :max="400" :precision="1" :step="0.5" style="width: 100%">
          <template #suffix>斤</template>
        </el-input-number>
      </el-form-item>

      <el-form-item label="最终目标体重" prop="target_weight_jin">
        <el-input-number v-model="form.target_weight_jin" :min="50" :max="400" :precision="1" :step="0.5" style="width: 100%">
          <template #suffix>斤</template>
        </el-input-number>
      </el-form-item>

      <el-form-item label="每月减重目标">
        <el-radio-group v-model="form.monthly_target_jin">
          <el-radio-button :value="2">2 斤/月</el-radio-button>
          <el-radio-button :value="3">3 斤/月</el-radio-button>
          <el-radio-button :value="4">4 斤/月</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <!-- 目标分解预览 -->
      <div class="decomposition" v-if="form.start_weight_jin && form.target_weight_jin && form.start_weight_jin > form.target_weight_jin">
        <div class="decomp-title">目标分解</div>
        <div class="decomp-row">
          <span>总需减重：</span>
          <b>{{ totalToLose }} 斤</b>
        </div>
        <div class="decomp-row">
          <span>预计周期：</span>
          <b>{{ totalMonths }} 个月</b>
        </div>
        <div class="decomp-row">
          <span>每月需减：</span>
          <b>{{ form.monthly_target_jin }} 斤</b>
        </div>
        <div class="decomp-months">
          <div v-for="m in monthBreakdown" :key="m.month" class="decomp-month">
            <span class="decomp-month-label">第{{ m.month }}月</span>
            <span class="decomp-month-range">{{ m.from }} 斤 → {{ m.to }} 斤</span>
            <span class="decomp-month-target" v-if="m.diff > 0">-{{ m.diff }} 斤</span>
          </div>
        </div>
      </div>

      <el-divider />

      <el-card shadow="never" class="body-info-card">
        <template #header>
          <span style="font-size:13px;font-weight:600">身体信息（用于计算 BMI）</span>
        </template>
        <el-form :model="form" label-width="50px" size="small">
          <el-row :gutter="12">
            <el-col :span="8">
              <el-form-item label="身高">
                <el-input-number v-model="form.height_cm" :min="100" :max="250" :precision="1" :step="1" style="width: 100%">
                  <template #suffix>cm</template>
                </el-input-number>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="性别">
                <el-select v-model="form.gender" placeholder="选填" clearable style="width: 100%">
                  <el-option label="男" value="male" />
                  <el-option label="女" value="female" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="年龄">
                <el-input-number v-model="form.age" :min="1" :max="150" style="width: 100%" placeholder="选填" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="danger" :loading="submitting" @click="handleSubmit">开始减重之旅 🎯</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { FormInstance } from 'element-plus'

const props = defineProps<{
  modelValue: boolean
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
  start_weight_jin: undefined as number | undefined,
  target_weight_jin: undefined as number | undefined,
  monthly_target_jin: 3,
  height_cm: undefined as number | undefined,
  gender: '',
  age: undefined as number | undefined,
})

const rules = {
  start_weight_jin: [{ required: true, message: '请输入当前体重', trigger: 'blur' }],
  target_weight_jin: [{ required: true, message: '请输入目标体重', trigger: 'blur' }],
}

const totalToLose = computed(() => {
  if (!form.value.start_weight_jin || !form.value.target_weight_jin) return 0
  return (form.value.start_weight_jin - form.value.target_weight_jin).toFixed(1)
})

const totalMonths = computed(() => {
  if (!form.value.start_weight_jin || !form.value.target_weight_jin || !form.value.monthly_target_jin) return 0
  const diff = form.value.start_weight_jin - form.value.target_weight_jin
  return Math.ceil(diff / form.value.monthly_target_jin)
})

const monthBreakdown = computed(() => {
  const months: { month: number; from: string; to: string; diff: number }[] = []
  if (!form.value.start_weight_jin || !form.value.target_weight_jin || !form.value.monthly_target_jin) return months

  let current = form.value.start_weight_jin
  const target = form.value.target_weight_jin
  const monthly = form.value.monthly_target_jin

  for (let m = 1; m <= totalMonths.value; m++) {
    const currentStr = current.toFixed(1)
    const nextTarget = Math.max(current - monthly, target)
    const toStr = nextTarget.toFixed(1)
    const diff = Math.round((current - nextTarget) * 10) / 10
    months.push({ month: m, from: currentStr, to: toStr, diff })
    current = nextTarget
    if (current <= target) break
  }
  return months
})

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  // Convert 斤 → kg for the API
  const data: Record<string, unknown> = {}
  if (form.value.start_weight_jin) data.start_weight_kg = form.value.start_weight_jin / 2
  if (form.value.target_weight_jin) data.target_weight_kg = form.value.target_weight_jin / 2
  data.monthly_target_kg = (form.value.monthly_target_jin || 3) / 2
  if (form.value.height_cm) data.height_cm = form.value.height_cm
  if (form.value.gender) data.gender = form.value.gender
  if (form.value.age) data.age = form.value.age
  emit('submit', data)
}
</script>

<style scoped>
.decomposition { background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.decomp-title { font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 8px; }
.decomp-row { font-size: 13px; color: #6B7280; margin-bottom: 4px; }
.decomp-months { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.decomp-month { background: #fff; border: 1px solid #E5E7EB; border-radius: 6px; padding: 6px 10px; font-size: 12px; display: flex; gap: 6px; align-items: center; }
.decomp-month-label { font-weight: 600; color: #374151; }
.decomp-month-range { color: #6B7280; }
.decomp-month-target { color: #10B981; font-weight: 600; }
.body-info-card { margin-bottom: 8px; }
.body-info-card :deep(.el-card__body) { padding: 12px 16px; }
.el-divider { margin: 16px 0; }
</style>
