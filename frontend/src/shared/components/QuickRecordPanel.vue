<template>
  <el-dialog
    v-model="dialogVisible"
    title="快速记录"
    :width="isBill || isWeight ? '460px' : '420px'"
    append-to-body
    @update:model-value="onVisibleChange"
    @keydown.ctrl.enter="onHotkey"
    @keydown.meta.enter="onHotkey"
  >
    <el-form>
      <el-form-item label="类型">
        <el-radio-group v-model="form.module">
          <el-radio value="temporal">日记</el-radio>
          <el-radio value="sugar">小确幸</el-radio>
          <el-radio value="goals">待办</el-radio>
          <el-radio value="wealth">记账</el-radio>
          <el-radio value="weight">体重</el-radio>
        </el-radio-group>
      </el-form-item>

      <!--
        🔴 记账走的是 `POST /wealth/bill/create/`（与月度页「记一笔」同一个接口），
           不是 `core/QuickRecordView` —— 后者只认 diary/sugar/todo 三类文本记录。
      -->
      <QuickBillInlineForm v-if="isBill" ref="billRef" />

      <!--
        体重同理：`core/QuickRecordView` 不认识 weight，硬塞进去会掉进它的 else 分支。
        这里直连 `POST /health/weight/records/` —— 与体重页「+ 记录体重」同一个接口。
      -->
      <div v-else-if="isWeight" class="quick-weight">
        <div class="qw-row">
          <el-input-number
            v-model="weightValue"
            :min="weightUnit.min"
            :max="weightUnit.max"
            :precision="weightUnit.precision"
            :step="weightUnit.step"
            class="qw-input"
            @keyup.enter="saveWeight"
          >
            <template #suffix>{{ weightUnit.suffix }}</template>
          </el-input-number>
          <el-radio-group :model-value="weightUnitMode" size="small" @change="onUnitChange">
            <el-radio-button v-for="u in WEIGHT_UNIT_OPTIONS" :key="u.value" :value="u.value">
              {{ u.label }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="qw-hint">
          <template v-if="weightKgPreview !== null">
            入库为 <b>{{ weightKgPreview }}</b> kg · 日期为今天（{{ todayText }}）
          </template>
          <template v-else>
            只填一个数就够，日期默认为今天（{{ todayText }}）
          </template>
        </div>
      </div>

      <el-form-item v-else label="内容">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="3"
          placeholder="记录此刻的想法..."
          @keyup.enter.ctrl="handleSave"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button
        v-if="isBill"
        type="primary"
        :loading="billSaving"
        @click="saveBill"
      >保存</el-button>
      <el-button
        v-else-if="isWeight"
        type="primary"
        :loading="weightSaving"
        @click="saveWeight"
      >保存</el-button>
      <el-button v-else type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { quickRecord } from '@/shared/api/coreApi'
import QuickBillInlineForm from '@/modules/wealth/components/common/QuickBillInlineForm.vue'
import { createWeightRecord } from '@/modules/health/api/healthApi'
import { todayLocal } from '@/shared/utils/datetime'
import { apiErrorText } from '@/shared/utils/apiError'
// 🔴 单位刻度、换算系数、上次用过的单位与体重页**同一份**（见 utils/weightUnits.ts）
import {
  WEIGHT_UNITS, WEIGHT_UNIT_OPTIONS,
  readStoredWeightUnit, storeWeightUnit, toKg, convertBetweenUnits,
  type WeightUnit,
} from '@/modules/health/utils/weightUnits'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [v: boolean] }>()

const dialogVisible = ref(false)
const form = ref({ module: 'temporal', content: '' })

const billRef = ref<InstanceType<typeof QuickBillInlineForm> | null>(null)
const billSaving = ref(false)

// ─── 体重 ───
const weightValue = ref<number | undefined>(undefined)
const weightUnitMode = ref<WeightUnit>(readStoredWeightUnit())
const weightSaving = ref(false)

const isBill = computed(() => form.value.module === 'wealth')
const isWeight = computed(() => form.value.module === 'weight')
const weightUnit = computed(() => WEIGHT_UNITS[weightUnitMode.value])
const weightKgPreview = computed(() => toKg(weightValue.value, weightUnitMode.value))
/** 只用于说明「记到哪一天」，取本地日期（禁 `toISOString()`：UTC 会在晚上 8 点后变昨天） */
const todayText = computed(() => todayLocal())

watch(() => props.visible, (v) => {
  dialogVisible.value = v
  if (v) {
    form.value = { module: 'temporal', content: '' }
    // 每次打开都从空开始：上次填了一半的体重留在框里，会被当成这次称的数存下去
    weightValue.value = undefined
    weightUnitMode.value = readStoredWeightUnit()
  }
})

const onVisibleChange = (v: boolean) => {
  emit('update:visible', v)
}

/** ⌘/Ctrl + Enter 在任何一种类型下都能保存 —— 记账/体重面板里没有 textarea，热键要提到外层 */
function onHotkey() {
  if (isBill.value) saveBill()
  else if (isWeight.value) saveWeight()
  else handleSave()
}

async function saveBill() {
  if (!billRef.value || billSaving.value) return
  billSaving.value = true
  try {
    await billRef.value.submit()
  } finally {
    billSaving.value = false
  }
}

function onUnitChange(value: string | number | boolean | undefined) {
  const next: WeightUnit | null = value === 'kg' ? 'kg' : value === 'jin' ? 'jin' : null
  if (!next || next === weightUnitMode.value) return
  const current = weightValue.value
  if (current !== undefined && current !== null && Number.isFinite(current)) {
    weightValue.value = convertBetweenUnits(current, weightUnitMode.value, next)
  }
  weightUnitMode.value = next
  storeWeightUnit(next)
}

async function saveWeight() {
  if (weightSaving.value) return
  // 空值不发请求：发出去换个 400 回来，读起来像「保存按钮坏了」
  const kg = toKg(weightValue.value, weightUnitMode.value)
  if (kg === null) {
    ElMessage.warning('先填一个体重')
    return
  }
  weightSaving.value = true
  try {
    await createWeightRecord({ record_date: todayLocal(), weight_kg: kg })
    dialogVisible.value = false
    emit('update:visible', false)
    // 体重页若正开着，让它自己重取 —— 否则「刚记的那条」要等下次进页面才出现
    window.dispatchEvent(new CustomEvent('weight-recorded'))
    ElMessage.success(`已记录 ${kg} kg`)
  } catch (e) {
    ElMessage.error(apiErrorText(e, '记录失败'))
  } finally {
    weightSaving.value = false
  }
}

const handleSave = async () => {
  if (!form.value.content.trim()) {
    ElMessage.warning('请先写点什么')
    return
  }
  try {
    await quickRecord({ module: form.value.module, content: form.value.content })
    dialogVisible.value = false
    emit('update:visible', false)
    ElMessage.success('已记录')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '记录失败')
  }
}
</script>

<style scoped>
.quick-weight {
  padding: 4px 0 0 0;
}
.qw-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
/* 🔴 `flex: 1 1 0` 而不是 `1 1 auto`：auto 的基准是内容宽度（输入框很长），
   会把右边的单位按钮挤到贴边、甚至裁掉圆角。基准为 0 才真的让它让位。 */
.qw-input {
  flex: 1 1 0;
  min-width: 120px;
}
.qw-row .el-radio-group {
  flex: 0 0 auto;
}
.qw-hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--lm-text-secondary, #909399);
}
.qw-hint b {
  font-weight: 500;
  color: var(--lm-text-primary, #606266);
}
</style>
