<template>
  <el-dialog
    :model-value="modelValue"
    title="改这条 KPI"
    width="520px"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <el-form v-if="metric" ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" maxlength="100" />
      </el-form-item>

      <el-form-item label="判定方向">
        <el-radio-group v-model="form.direction">
          <el-radio value="at_least">至少（≥）</el-radio>
          <el-radio value="at_most">至多（≤）</el-radio>
        </el-radio-group>
        <div class="hint">「戒掉」类才是「至多」—— 绝大多数是「至少」。</div>
      </el-form-item>

      <el-form-item :label="`目标（${form.unit || '无单位'}）`">
        <el-input-number v-model="form.goal_value" :min="0" :step="1" style="width: 180px" />
        <el-button size="small" text @click="form.goal_value = null">清空</el-button>
        <div class="hint">清空 = 只展示不判目标（显示「—」，**不是 0**）。</div>
      </el-form-item>

      <el-form-item :label="`底线（${form.unit || '无单位'}）`">
        <el-input-number v-model="form.floor_value" :min="0" :step="1" style="width: 180px" />
        <el-button size="small" text @click="form.floor_value = null">清空</el-button>
        <div class="hint">{{ floorHint }}</div>
      </el-form-item>

      <el-form-item label="目标依据">
        <el-input v-model="form.goal_why" maxlength="200" placeholder="为什么是这个数（写下依据，三个月后回看）" />
      </el-form-item>
      <el-form-item label="底线依据">
        <el-input v-model="form.floor_why" maxlength="200" placeholder="底线是从哪来的（如：近 11 周中位数）" />
      </el-form-item>

      <el-divider content-position="left">
        <span class="hint">改了就要说一声（系统不判断对错，只记录）</span>
      </el-divider>

      <el-form-item label="这次为什么改">
        <el-select v-model="form.reason" placeholder="选一个" style="width: 100%">
          <el-option
            v-for="(label, key) in CHANGE_REASON_LABEL" :key="key"
            :label="label" :value="key"
          />
        </el-select>
        <div class="hint">
          不是审批 —— 是为了让你在「尺子时间轴」上看得出模式
          （连续三次「状态」+ 达标率一直掉，那是一种信号）。
        </div>
      </el-form-item>
      <el-form-item label="补充说明">
        <el-input v-model="form.reason_note" maxlength="200" placeholder="可选" />
      </el-form-item>
    </el-form>

    <el-alert
      v-if="changes.length" type="info" :closable="false" show-icon class="change-preview"
      :title="`会改这几项：${changes.join('、')}`"
      description="目标值/底线改完**不会**回溯改写往期结论 —— 往期是快照，改口径只影响以后。"
    />
    <el-alert
      v-else type="info" :closable="false" show-icon
      title="还没改动任何一项"
    />

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!changes.length" @click="submit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import * as api from '../api/selfrunApi'
import { CHANGE_REASON_LABEL, DIRECTION_LABEL, num } from '../types/selfrunTypes'
import type { SelfRunMetric } from '../types/selfrunTypes'

const props = defineProps<{
  modelValue: boolean
  metric: SelfRunMetric | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'saved', metric: SelfRunMetric): void
}>()

const formRef = ref<FormInstance>()
const saving = ref(false)
const form = ref({
  name: '',
  unit: '',
  direction: 'at_least' as 'at_least' | 'at_most',
  goal_value: null as number | null,
  floor_value: null as number | null,
  goal_why: '',
  floor_why: '',
  reason: '',
  reason_note: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '名称不能为空', trigger: 'blur' }],
}

/** 打开时按当前配置回填（每次打开都重来，不残留上一次的编辑） */
watch(() => props.modelValue, (v) => {
  if (!v || !props.metric) return
  const m = props.metric
  form.value = {
    name: m.name,
    unit: m.unit,
    direction: m.direction,
    goal_value: num(m.goal_value),
    floor_value: num(m.floor_value),
    goal_why: m.goal_why,
    floor_why: m.floor_why,
    reason: '',
    reason_note: '',
  }
})

const floorHint = computed(() => {
  const g = form.value.goal_value
  const f = form.value.floor_value
  if (g === null && f === null) {
    return '两条都空 ⇒ 这条只展示不判定（状态 = 未配置目标）。'
  }
  if (g !== null && f !== null) {
    const op = DIRECTION_LABEL[form.value.direction]
    const bad = form.value.direction === 'at_least' ? g < f : g > f
    return bad
      ? `⚠️ 方向是「${op}」，但目标 ${g} 与底线 ${f} 的关系反了 —— 保存时后端会退回。`
      : '达底线即算达标（「保住」也算数）。'
  }
  return '只有一档时，它就是判定线。'
})

/** 只列出**真的变了**的字段 —— 保存按钮据此启用/禁用。 */
const changes = computed(() => {
  const m = props.metric
  if (!m) return []
  const out: string[] = []
  const push = (label: string, a: unknown, b: unknown) => {
    if (a !== b) out.push(label)
  }
  push('名称', m.name, form.value.name)
  push('方向', m.direction, form.value.direction)
  push('目标', num(m.goal_value), form.value.goal_value)
  push('底线', num(m.floor_value), form.value.floor_value)
  push('目标依据', m.goal_why || '', form.value.goal_why || '')
  push('底线依据', m.floor_why || '', form.value.floor_why || '')
  return out
})

/** 改数值/口径 ⇒ **必须**说原因（改名不用）。 */
const needReason = computed(() =>
  changes.value.some(c => ['目标', '底线', '方向'].includes(c)),
)

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  const m = props.metric
  if (!m) return
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  if (needReason.value && !form.value.reason) {
    ElMessage.warning('改了目标/底线/方向 —— 请选一下这次为什么改。')
    return
  }
  saving.value = true
  try {
    const res = await api.patchMetric(m.id, {
      name: form.value.name,
      direction: form.value.direction,
      goal_value: form.value.goal_value,
      floor_value: form.value.floor_value,
      goal_why: form.value.goal_why,
      floor_why: form.value.floor_why,
      reason: form.value.reason || undefined,
      reason_note: form.value.reason_note || '',
    })
    ElMessage.success('已改（往期结论不受影响）')
    emit('saved', res.data.metric)
    close()
  } catch (e: any) {
    // 后端的 400 是**显式校验**（如「目标低于底线」），必须原样念出来
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; }
.change-preview { margin-top: 4px; }
</style>
