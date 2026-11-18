<template>
  <el-dialog
    v-model="visible"
    width="480px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <template #header>
      <div class="form-header">
        <span class="form-title">✏️ 记录体重</span>
        <el-radio-group :model-value="unitMode" size="small" @change="handleUnitChange">
          <el-radio-button v-for="item in WEIGHT_UNIT_OPTIONS" :key="item.value" :value="item.value">
            {{ item.fullLabel }}
          </el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" label-position="left">
      <el-form-item label="日期" prop="record_date">
        <el-date-picker v-model="form.record_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
      </el-form-item>

      <el-form-item label="体重" prop="weight">
        <div class="weight-field">
          <el-input-number
            v-model="form.weight"
            :min="activeUnit.min"
            :max="activeUnit.max"
            :precision="activeUnit.precision"
            :step="activeUnit.step"
            style="width: 100%"
          >
            <template #suffix>{{ activeUnit.suffix }}</template>
          </el-input-number>
          <div v-if="weightKgPreview !== null" class="weight-hint">
            入库为 <b>{{ weightKgPreview }}</b> kg
          </div>
        </div>
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
import { todayLocal } from '@/shared/utils/datetime'
// 🔴 单位刻度、换算系数、上次用过的单位都在这里 —— 与「快速记录」里的体重共用一份。
//    在组件里再写一遍 `2`，就是第二套尺子（见 utils/weightUnits.ts 的注释）。
import {
  WEIGHT_UNITS, WEIGHT_UNIT_OPTIONS,
  readStoredWeightUnit, storeWeightUnit, toKg, fromKg, convertBetweenUnits,
  type WeightUnit,
} from '../../utils/weightUnits'

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

const unitMode = ref<WeightUnit>(readStoredWeightUnit())
const activeUnit = computed(() => WEIGHT_UNITS[unitMode.value])

const form = ref({
  record_date: '',
  weight: undefined as number | undefined,
  body_fat: undefined as number | undefined,
  measure_time: '',
  notes: '',
})

const rules = {
  record_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  weight: [{ required: true, message: '请输入体重', trigger: 'blur' }],
}

/** 录入值换算成 kg（真源口径），空值不给数。用于消除「最后一跳」的困惑。 */
const weightKgPreview = computed(() => toKg(form.value.weight, unitMode.value))

function handleUnitChange(value: string | number | boolean | undefined): void {
  const next: WeightUnit | null = value === 'kg' ? 'kg' : value === 'jin' ? 'jin' : null
  if (!next || next === unitMode.value) return

  const current = form.value.weight
  if (current !== undefined && current !== null && Number.isFinite(current)) {
    form.value.weight = convertBetweenUnits(current, unitMode.value, next)
  }

  unitMode.value = next
  storeWeightUnit(next)
}

function resetForm() {
  form.value = {
    // 默认「今天」：体重记录的就是「刚称的这一下」，日期几乎总是今天。
    // 🔴 用本地的 `todayLocal()`，不用 `new Date().toISOString().slice(0,10)` ——
    //    后者是 UTC，晚上 8 点后会变成昨天，而界面上看不出任何异常。
    record_date: todayLocal(),
    weight: undefined,
    body_fat: undefined,
    measure_time: '',
    notes: '',
  }
}

function loadRecord(record: WeightRecord | null) {
  if (!record) {
    resetForm()
    return
  }
  // 🔴 真源只有 weight_kg 一列：无论当前是哪个模式，都从它派生显示值。
  //    库里不记录「这条是用哪个秤量的」，所以不许反推，只能换算。
  const shown = fromKg(Number(record.weight_kg), unitMode.value)
  form.value = {
    record_date: record.record_date,
    weight: shown === null ? undefined : shown,
    body_fat: record.body_fat ? parseFloat(record.body_fat) : undefined,
    measure_time: record.measure_time || '',
    notes: record.notes || '',
  }
}

defineExpose({ loadRecord })

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 校验已通过 ⇒ 这里一定是个数。用 `?? 0` 兜住类型，但别让它变成「没填也存 0 kg」的路径。
  emit('submit', {
    record_date: form.value.record_date,
    weight_kg: toKg(form.value.weight ?? 0, unitMode.value),
    body_fat: form.value.body_fat,
    measure_time: form.value.measure_time,
    notes: form.value.notes,
  })
}

function handleClose() {
  formRef.value?.resetFields()
  resetForm()
}
</script>

<style scoped>
.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-right: 32px;
}
.form-title {
  font-size: 16px;
  font-weight: 500;
  color: #1f2937;
}
.weight-field {
  width: 100%;
}
.weight-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #909399;
}
.weight-hint b {
  font-weight: 500;
  color: #606266;
}
</style>
