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
          <el-radio-button v-for="item in UNIT_OPTIONS" :key="item.value" :value="item.value">
            {{ item.label }}
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

type UnitMode = 'kg' | 'jin'

interface UnitSpec {
  value: UnitMode
  label: string
  suffix: string
  min: number
  max: number
  precision: number
  step: number
}

/**
 * 两个称重单位（家里一台秤读 kg、一台读斤，随机用）。
 * 🔴 min / max / precision 必须跟着模式走，不能沿用对方的刻度：
 *    沿用对方的 min=50 ⇒ 在 kg 模式下输 45 会被组件静默钳到 50；
 *    kg 只给 1 位小数 ⇒ 125.3 斤换来的 62.65 被抹成 62.7，再显示回斤就是 125.4。
 */
const UNITS: Record<UnitMode, UnitSpec> = {
  kg: { value: 'kg', label: 'KG模式', suffix: 'kg', min: 25, max: 200, precision: 2, step: 0.1 },
  jin: { value: 'jin', label: '斤模式', suffix: '斤', min: 50, max: 400, precision: 1, step: 0.5 },
}

const UNIT_OPTIONS = [UNITS.kg, UNITS.jin]

/** 1 kg = 2 斤。换算系数只此一份，别在别处再写 2。 */
const JIN_PER_KG = 2

/** 库列 weight_kg 是 Decimal(5,2)，入库值必须落在 2 位小数内，否则 DRF 拒收。 */
const KG_DECIMALS = 2

/** 记住上次用的模式：两个秤随机换着用，每次都重选太费事。 */
const UNIT_STORAGE_KEY = 'sycamore.health.weightUnit'

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

function roundTo(value: number, precision: number): number {
  const factor = 10 ** precision
  return Math.round(value * factor) / factor
}

function readStoredUnit(): UnitMode {
  try {
    const stored = localStorage.getItem(UNIT_STORAGE_KEY)
    return stored === 'kg' || stored === 'jin' ? stored : 'jin'
  } catch {
    // 隐私模式 / 存储被禁用：回退到「斤」，不影响录入
    return 'jin'
  }
}

const unitMode = ref<UnitMode>(readStoredUnit())
const activeUnit = computed(() => UNITS[unitMode.value])

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
const weightKgPreview = computed(() => {
  const value = form.value.weight
  if (value === undefined || value === null || !Number.isFinite(value)) return null
  const kg = unitMode.value === 'kg' ? value : value / JIN_PER_KG
  return Number(roundTo(kg, KG_DECIMALS).toFixed(KG_DECIMALS))
})

/**
 * 🔴 切换模式时，已填的数字必须按「同一个物理重量」换算过去。
 *    若只换单位标签不动数字，125（斤）会原地变成 125 kg（= 250 斤）——
 *    链路上没有任何一步会报错，只会在趋势图上多一根暴涨柱。
 */
function handleUnitChange(value: string | number | boolean | undefined): void {
  const next: UnitMode | null = value === 'kg' ? 'kg' : value === 'jin' ? 'jin' : null
  if (!next || next === unitMode.value) return

  const prev = unitMode.value
  const current = form.value.weight
  if (current !== undefined && current !== null && Number.isFinite(current)) {
    const kg = prev === 'kg' ? current : current / JIN_PER_KG
    const converted = next === 'kg' ? kg : kg * JIN_PER_KG
    form.value.weight = roundTo(converted, UNITS[next].precision)
  }

  unitMode.value = next
  try {
    localStorage.setItem(UNIT_STORAGE_KEY, next)
  } catch {
    // 存不进去不影响本次录入，下次打开回落默认值
  }
}

function resetForm() {
  form.value = {
    record_date: '',
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
  const kg = Number(record.weight_kg)
  const ratio = unitMode.value === 'kg' ? 1 : JIN_PER_KG
  form.value = {
    record_date: record.record_date,
    weight: Number.isFinite(kg) ? roundTo(kg * ratio, activeUnit.value.precision) : undefined,
    body_fat: record.body_fat ? parseFloat(record.body_fat) : undefined,
    measure_time: record.measure_time || '',
    notes: record.notes || '',
  }
}

defineExpose({ loadRecord })

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const displayed = form.value.weight
  const kg = unitMode.value === 'kg' ? (displayed ?? 0) : (displayed ?? 0) / JIN_PER_KG
  emit('submit', {
    record_date: form.value.record_date,
    weight_kg: roundTo(kg, KG_DECIMALS),
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
