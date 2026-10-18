<template>
  <el-dialog
    :model-value="modelValue"
    :title="`改「${row?.name ?? ''}」在 ${periodLabel} 的目标`"
    width="560px"
    @update:model-value="(v: any) => emit('update:modelValue', !!v)"
  >
    <template v-if="row">
      <!-- 现况：这一期现在拿的是哪把尺子 -->
      <el-descriptions :column="2" border size="small" class="tp-now">
        <el-descriptions-item label="阶段默认">
          {{ fmt(row.base_goal, row.unit) }} / {{ fmt(row.base_floor, row.unit) }}
        </el-descriptions-item>
        <el-descriptions-item label="这一期现在">
          <b class="tp-nowval">{{ fmt(row.goal_value, row.unit) }} / {{ fmt(row.floor_value, row.unit) }}</b>
          <el-tag v-if="sourceTag" size="small" effect="plain" :type="sourceTag" class="tp-tag">
            {{ row.target_source_label }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-form label-width="110px" class="tp-form">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="`目标（${row.unit || '无单位'}）`">
              <el-input-number
                v-model="form.goal_value" :min="0" :step="1"
                :value-on-clear="null" style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="`底线（${row.unit || '无单位'}）`">
              <el-input-number
                v-model="form.floor_value" :min="0" :step="1"
                :value-on-clear="null" style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="tp-quick">
          <el-button size="small" text @click="usePlan">沿用现况（{{ fmt(row.goal_value, row.unit) }} / {{ fmt(row.floor_value, row.unit) }}）</el-button>
          <el-button size="small" text @click="useBase">填回阶段默认（{{ fmt(row.base_goal, row.unit) }} / {{ fmt(row.base_floor, row.unit) }}）</el-button>
        </div>

        <el-form-item label="作用范围">
          <el-radio-group v-model="form.scope">
            <el-radio value="single">只这一期</el-radio>
            <el-radio value="from">从这一期起</el-radio>
          </el-radio-group>
          <div class="tp-hint">
            <template v-if="form.scope === 'single'">
              `{{ periodLabel }}` 用完就完 —— 下一期自动落回默认（或更晚的那条「从这一期起」）。
            </template>
            <template v-else>
              🔴 **它会一直生效**，直到出现一条更晚的「从这一期起」为止 ——
              不是只改这一期。想只改一期请选左边。
            </template>
          </div>
        </el-form-item>

        <el-form-item label="为什么改">
          <el-input v-model="form.note" maxlength="200" placeholder="例如：这周出差，先把线放低一点" />
        </el-form-item>
        <el-form-item label="目标依据">
          <el-input v-model="form.goal_why" maxlength="200" placeholder="可空 —— 空着就沿用阶段里的依据" />
        </el-form-item>
        <el-form-item label="底线依据">
          <el-input v-model="form.floor_why" maxlength="200" placeholder="可空 —— 空着就沿用阶段里的依据" />
        </el-form-item>
      </el-form>

      <el-alert
        type="info" :closable="false" show-icon
        title="两档都能留空 —— 空 ≠ 0"
        description="清空某一档 = 「这一期不要这一档」（只展示不判定）；填 0 = 「这一期就是 0」。两者不是一回事。清空与填 0 都会写进变更记录。"
      />
    </template>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">
        {{ row?.plan_id && form.scope === row.plan_scope ? '保存' : '设定' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useSelfRunStore } from '../stores/selfrunStore'
import { TARGET_SOURCE_TAG, fmt, num } from '../types/selfrunTypes'
import type { PlanScope, TargetRow } from '../types/selfrunTypes'

const props = withDefaults(defineProps<{
  modelValue: boolean
  row: TargetRow | null
  /** 周期标识（`2026-W43` / `2026-10`）—— 🔴 **由后端下发**，前端不自己算 */
  periodKey: string
  /** 给人看的那份说法（「2026-W43 · 往后第 1 期」） */
  periodLabel: string
}>(), {
  row: null,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'saved'): void
}>()

const store = useSelfRunStore()
const saving = ref(false)

const form = ref<{
  goal_value: number | null
  floor_value: number | null
  scope: PlanScope
  note: string
  goal_why: string
  floor_why: string
}>({
  goal_value: null, floor_value: null,
  scope: 'single', note: '', goal_why: '', floor_why: '',
})

const sourceTag = computed(() => {
  const s = props.row?.target_source
  if (!s || s === 'metric') return ''
  return TARGET_SOURCE_TAG[s] ?? ''
})

/**
 * 打开时把**这一期现在生效的**值填进表单。
 *
 * 🔴 默认作用域是 `single`（只这一期）—— 不能默认成 `from`：
 *    那会让「我就想调这周」的人**无声地**把以后每一周都改掉。
 */
watch(() => props.modelValue, (open) => {
  if (!open || !props.row) return
  form.value = {
    goal_value: num(props.row.goal_value),
    floor_value: num(props.row.floor_value),
    scope: 'single',
    note: '',
    goal_why: '',
    floor_why: '',
  }
})

function usePlan() {
  if (!props.row) return
  form.value.goal_value = num(props.row.goal_value)
  form.value.floor_value = num(props.row.floor_value)
}

function useBase() {
  if (!props.row) return
  form.value.goal_value = num(props.row.base_goal)
  form.value.floor_value = num(props.row.base_floor)
}

async function submit() {
  if (!props.row) return
  const r = props.row
  const g = num(form.value.goal_value)
  const f = num(form.value.floor_value)
  // 方向性校验：目标不能比底线松（**本地先挡一道**，后端还会再挡一次）
  if (g !== null && f !== null) {
    const loose = r.direction === 'at_least' ? g < f : g > f
    if (loose) {
      ElMessage.warning(
        r.direction === 'at_least'
          ? `目标 ${fmt(g, r.unit)} 低于底线 ${fmt(f, r.unit)} —— 目标不能低于底线`
          : `目标 ${fmt(g, r.unit)} 高于底线 ${fmt(f, r.unit)} —— 目标不能高于底线`,
      )
      return
    }
  }
  saving.value = true
  try {
    const res = await store.setPlan(r.metric_id, {
      period_key: props.periodKey,
      scope: form.value.scope,
      // 🔴 显式传（可为 null）—— 「省略」与「显式传 null」是两件事
      goal_value: g,
      floor_value: f,
      goal_why: form.value.goal_why,
      floor_why: form.value.floor_why,
      note: form.value.note,
    })
    const w = res.written
    ElMessage.success(
      `已设定 ${r.name} · ${props.periodKey}`
      + (Object.keys(w).length ? `（写了 ${Object.entries(w).map(([k, v]) => `${k} ${v} 行`).join(' · ')}）` : ''),
    )
    emit('update:modelValue', false)
    emit('saved')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '设定失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.tp-now { margin-bottom: 12px; }
.tp-nowval { font-weight: 700; }
.tp-tag { margin-left: 6px; }
.tp-form :deep(.el-form-item) { margin-bottom: 14px; }
.tp-quick {
  display: flex; gap: 8px; flex-wrap: wrap;
  margin: -6px 0 12px 110px;
}
.tp-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.7; margin-top: 4px; }
</style>
