<template>
  <el-dialog
    :model-value="modelValue"
    title="改这条 KPI"
    width="520px"
    class="kpi-cfg-dialog"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <el-form v-if="metric" ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" maxlength="100" />
      </el-form-item>

      <el-divider content-position="left">这条数从哪来</el-divider>

      <!-- 🔴 与模板库共用同一个组件：取数器 → 条件字段的分流只此一份。
           以前这里**没有**这一块 —— 建完 KPI 才发现「这条该自动取数」就只能退役重建，
           而退役会把手工登记一起带走。 -->
      <SourceConfigFields
        v-model:source-kind="form.source_kind"
        v-model:reader-kind="form.reader_kind"
        v-model:where-value="form.where_value"
        manual-hint="手工项不需要取数器：每周/每月自己去「本周状态」里补一笔，系统不替你数。"
        @reader-switch="onReaderSwitch"
      />

      <!-- 已有手工登记 ⇒ 换方式前后**必须**说清它会不会被重复算一遍 -->
      <el-alert
        v-if="sourceTouched && form.source_kind !== 'manual' && checkinCount > 0"
        type="warning" :closable="false" show-icon class="kpi-warn"
        :title="`这条已有 ${checkinCount} 笔手工登记`"
      >
        <div>{{ checkinWarnText }}</div>
        <div class="kpi-warn-recent">最近几笔：{{ recentCheckins }}</div>
      </el-alert>

      <el-divider content-position="left">怎么判</el-divider>

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
        <div class="hint">清空 = 只展示不判目标（显示「—」，<b>不是 0</b>）。</div>
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
      description="目标值/底线/取数方式改完不会回溯改写往期结论 —— 往期是快照，改口径只影响以后。"
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
import SourceConfigFields from './SourceConfigFields.vue'
import * as api from '../api/selfrunApi'
import { useSelfRunStore } from '../stores/selfrunStore'
import { buildSourceConfig, toFormValue } from '../utils/sourceConfig'
import { CHANGE_REASON_LABEL, DIRECTION_LABEL, num } from '../types/selfrunTypes'
import type { SelfRunCheckin, SelfRunMetric, SourceKind } from '../types/selfrunTypes'
import type { WhereValue } from '../utils/sourceConfig'

const props = defineProps<{
  modelValue: boolean
  metric: SelfRunMetric | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'saved', metric: SelfRunMetric): void
}>()

const store = useSelfRunStore()

const formRef = ref<FormInstance>()
const saving = ref(false)

/** 被改的那条原来带着的 `where`（不在界面上的固定条件，比如收入验证的 `transaction_type`） */
let baseWhere: Record<string, unknown> = {}

const form = ref({
  name: '',
  unit: '',
  direction: 'at_least' as 'at_least' | 'at_most',
  goal_value: null as number | null,
  floor_value: null as number | null,
  goal_why: '',
  floor_why: '',
  source_kind: 'manual' as SourceKind,
  reader_kind: '',
  where_value: '' as WhereValue,
  reason: '',
  reason_note: '',
})

/** 这条已有的手工登记（换方式时要说清「它们会被怎么算」，并让人认出哪笔是重复的） */
const checkins = ref<SelfRunCheckin[]>([])
const checkinCount = computed(() => checkins.value.length)

const rules: FormRules = {
  name: [{ required: true, message: '名称不能为空', trigger: 'blur' }],
}

const readerChoices = computed(() => store.templateEnum?.readers ?? [])

/** 打开时按当前配置回填（每次打开都重来，不残留上一次的编辑） */
watch(() => props.modelValue, async (v) => {
  if (!v || !props.metric) return
  // 🔴 先把枚举拉回来**再**回填：取数器 → `where_key` 的对照在枚举里，
  //    枚举没到就回填，界面上的「活动类型」会是空的 —— 而 `sourceTouched`
  //    会以为「你把条件删了」，保存时静默丢掉那个过滤。
  if (!store.templateEnum) {
    try { await store.loadTemplates() } catch { /* 拉不到时组件会自曝「拿不到取数器清单」 */ }
  }
  const m = props.metric
  const cfg = (m.source_config ?? {}) as { kind?: string; where?: Record<string, unknown> }
  baseWhere = { ...cfg.where }
  const wk = readerChoices.value.find(r => r.value === cfg.kind)?.where_key
  form.value = {
    name: m.name,
    unit: m.unit,
    direction: m.direction,
    goal_value: num(m.goal_value),
    floor_value: num(m.floor_value),
    goal_why: m.goal_why,
    floor_why: m.floor_why,
    source_kind: m.source_kind,
    reader_kind: cfg.kind ?? '',
    where_value: wk ? toFormValue(baseWhere[wk], wk === 'l2') : '',
    reason: '',
    reason_note: '',
  }
  checkins.value = []
  try {
    const res = await api.listCheckins({ metric_id: m.id })
    checkins.value = res.data
  } catch {
    // 拉不到就**不提示**：宁可少说一句，也不要拿 0 去糊弄成「没有登记」
    checkins.value = []
  }
})

/** `source_config` 是这一版界面拼出来的（与模板库同一份拼法） */
function buildCfg(): Record<string, unknown> {
  const wk = readerChoices.value.find(r => r.value === form.value.reader_kind)?.where_key
  return buildSourceConfig(
    form.value.source_kind, form.value.reader_kind, wk ?? undefined,
    form.value.where_value, baseWhere,
  )
}

const sourceTouched = computed(() => {
  const m = props.metric
  if (!m) return false
  if (m.source_kind !== form.value.source_kind) return true
  return JSON.stringify(m.source_config ?? {}) !== JSON.stringify(buildCfg())
})

const checkinWarnText = computed(() => form.value.source_kind === 'auto_plus_manual'
  ? '切成「自动 + 手工补记」后，它们会和自动数相加。'
    + '若有几笔其实已经进了自动源（比如同一张画既有作品、又手记过一次），'
    + '这一期就会重复计数 —— 去「本周状态」把重复那笔撤销（撤销不是删除，原记录保留）。'
  : '切成「自动取数」后，它们不再计入这一条。想两边相加就选「自动 + 手工补记」。')

/** 最近几笔的「日期 + 备注」—— 让人自己认出哪一笔是重复的那张画 */
const recentCheckins = computed(() => {
  const rows = checkins.value.slice(0, 3).map(c => {
    const day = (c.checkin_date || '').slice(5)      // `2026-11-03` → `11-03`
    const note = (c.note || '').trim()
    return note ? `${day} ${note}` : `${day} ${c.value}`
  })
  const more = checkins.value.length > rows.length ? ` … 共 ${checkins.value.length} 笔` : ''
  return rows.join('；') + more
})

// ── 表单校验 / 变更检测 ──────────────────────────────────────

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
  if (sourceTouched.value) out.push('取数方式')
  push('方向', m.direction, form.value.direction)
  push('目标', num(m.goal_value), form.value.goal_value)
  push('底线', num(m.floor_value), form.value.floor_value)
  push('目标依据', m.goal_why || '', form.value.goal_why || '')
  push('底线依据', m.floor_why || '', form.value.floor_why || '')
  return out
})

/** 改数值/口径 ⇒ **必须**说原因（改名不用）。
 *  🔴 「换尺子」比改一个数影响大得多，所以取数方式也算在内。 */
const needReason = computed(() =>
  changes.value.some(c => ['目标', '底线', '方向', '取数方式'].includes(c)),
)

/** 换了取数器 ⇒ 丢掉上一条的 `where`（两个取数器的条件键往往不同，留着就是串味） */
function onReaderSwitch(nextKind: string) {
  baseWhere = {}
  const wk = readerChoices.value.find(r => r.value === nextKind)?.where_key
  form.value.where_value = wk === 'l2' ? [] : ''
}

function close() {
  emit('update:modelValue', false)
}

async function submit() {
  const m = props.metric
  if (!m) return
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  if (form.value.source_kind !== 'manual' && !form.value.reader_kind) {
    ElMessage.warning('选了自动取数，就得挑一个取数器')
    return
  }
  if (needReason.value && !form.value.reason) {
    ElMessage.warning('改了目标/底线/方向/取数方式 —— 请选一下这次为什么改。')
    return
  }
  saving.value = true
  try {
    // 🔴 取数方式**只在真改过时**才发：没动它却带上 `source_config`，
    //    等于让后端按界面拼的那一份重算一遍 `agg` —— 界面没显示的条件会跟着变。
    const source = sourceTouched.value
      ? { source_kind: form.value.source_kind, source_config: buildCfg() }
      : {}
    const res = await api.patchMetric(m.id, {
      name: form.value.name,
      direction: form.value.direction,
      goal_value: form.value.goal_value,
      floor_value: form.value.floor_value,
      goal_why: form.value.goal_why,
      floor_why: form.value.floor_why,
      reason: form.value.reason || undefined,
      reason_note: form.value.reason_note || '',
      ...source,
    })
    ElMessage.success('已改（往期结论不受影响）')
    emit('saved', res.data.metric)
    close()
  } catch (e: any) {
    // 后端的 400 是**显式校验**（如「取数器拼错」「目标低于底线」），必须原样念出来
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; }
.change-preview { margin-top: 4px; }
.kpi-warn { margin: 4px 0 8px; }
.kpi-warn-recent { margin-top: 4px; font-size: 12px; opacity: 0.85; }
</style>

<style>
/* 加了「取数方式」一段后弹窗会超出屏幕 ⇒ 只滚中间那块，标题与按钮钉住。
   ⚠️ 用非 scoped + 类名限定：`el-dialog` 是 teleport 到 body 的，scoped 够不着。 */
.kpi-cfg-dialog .el-dialog__body { max-height: 64vh; overflow-y: auto; }
</style>
