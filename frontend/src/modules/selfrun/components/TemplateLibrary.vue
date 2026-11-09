<template>
  <el-card shadow="never" class="tl-card">
    <template #header>
      <div class="tl-head">
        <span class="tl-title">KPI 模板库</span>
        <span class="tl-hint">
          这里是<b>起点库</b> —— 挑一条进阶段时，值会被<b>抄进</b>那个阶段；
          以后改这里（或删这里）都<b>不会回头改已建的阶段</b>。增删改都落库，刷新页面还在。
        </span>
        <span class="tl-spacer" />
        <el-button size="small" type="primary" @click="openCreate">+ 新建模板</el-button>
      </div>
    </template>

    <el-table
      :data="store.templates" size="small"
      empty-text="模板库是空的 —— 点右上角「新建模板」加一条"
    >
      <el-table-column label="模板" min-width="200">
        <template #default="{ row }">
          <div class="tl-name">
            <span>{{ row.name }}</span>
            <el-tag v-if="isCustom(row)" size="small" effect="plain" type="info">自建</el-tag>
          </div>
          <div v-if="row.goal_why" class="tl-why">依据：{{ row.goal_why }}</div>
        </template>
      </el-table-column>
      <el-table-column label="周期" width="56">
        <template #default="{ row }">{{ row.period_type === 'weekly' ? '周' : '月' }}</template>
      </el-table-column>
      <el-table-column label="目标 / 底线" width="150">
        <template #default="{ row }">
          {{ fmt(row.goal_value, row.unit) }} / {{ fmt(row.floor_value, row.unit) }}
        </template>
      </el-table-column>
      <el-table-column label="取数" min-width="180">
        <template #default="{ row }">
          {{ SOURCE_KIND_LABEL[row.source_kind] ?? row.source_kind }} · {{ AGG_LABEL[row.agg] ?? row.agg }}
          <div v-if="row.reader_hint" class="tl-why">来源：{{ row.reader_hint }}</div>
          <div v-else-if="row.source_config && row.source_config.kind" class="tl-why">
            取数器：{{ row.source_config.kind }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="被引用" width="86">
        <template #default="{ row }">
          <el-tag v-if="row.used_count" size="small" effect="plain">{{ row.used_count }} 条 KPI</el-tag>
          <span v-else class="tl-muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="112">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openEdit(row)">改</el-button>
          <el-button size="small" text type="danger" @click="doDelete(row)">删</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="tl-foot">
      「被引用」= 有几条<b>已建 KPI</b> 的来源指向这条模板。删掉模板<b>不会动它们</b> ——
      来源只是展示用的标记（template_key 是字符不是外键），不参与取数。
    </div>

    <!-- ── 新建 / 改 ─────────────────────────────────────── -->
    <el-dialog
      v-model="visible"
      :title="editing ? `改模板「${editing.name}」` : '新建 KPI 模板'"
      width="640px"
      top="6vh"
    >
      <el-form :model="form" label-width="96px">
        <el-form-item label="名称">
          <el-input v-model="form.name" maxlength="100" placeholder="例如：习字张数" />
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="周期">
              <el-select v-model="form.period_type" style="width: 100%">
                <el-option
                  v-for="o in opts('period_type', PERIOD_TYPE_LABEL)"
                  :key="o.value" :label="o.label" :value="o.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位">
              <el-input v-model="form.unit" maxlength="20" placeholder="h / 次 / 天 / 张 / 元" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="方向">
              <el-select v-model="form.direction" style="width: 100%">
                <el-option
                  v-for="o in opts('direction', DIRECTION_LABEL)"
                  :key="o.value" :label="o.label" :value="o.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="达标口径">
              <el-select v-model="form.agg" style="width: 100%">
                <el-option
                  v-for="o in opts('agg', AGG_LABEL)"
                  :key="o.value" :label="o.label" :value="o.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item :label="`目标（${form.unit || '无单位'}）`">
              <el-input-number
                v-model="form.goal_value" :min="0" :step="1"
                :value-on-clear="null" style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="`底线（${form.unit || '无单位'}）`">
              <el-input-number
                v-model="form.floor_value" :min="0" :step="1"
                :value-on-clear="null" style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="目标依据">
          <el-input v-model="form.goal_why" maxlength="200" placeholder="为什么是这个数（可空）" />
        </el-form-item>
        <el-form-item label="底线依据">
          <el-input v-model="form.floor_why" maxlength="200" placeholder="这个底线是从哪来的（可空）" />
        </el-form-item>

        <el-divider content-position="left">取数方式</el-divider>

        <!-- 🔴 这块与「改这条 KPI」共用同一个组件：取数器 → 条件字段的分流只此一份 -->
        <SourceConfigFields
          v-model:source-kind="form.source_kind"
          v-model:reader-kind="form.reader_kind"
          v-model:where-value="form.where_value"
          @reader-switch="onReaderSwitch"
        />
      </el-form>

      <el-alert
        type="info" :closable="false" show-icon class="tl-dlg-note"
        title="模板只是起点，不是活引用"
        description="把这条挑进阶段时，上面这些值会被抄进那个阶段的 KPI；此后你再改模板，已建阶段一个字都不会变。"
      />

      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ editing ? '保存' : '新建' }}
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SourceConfigFields from './SourceConfigFields.vue'
import { useSelfRunStore } from '../stores/selfrunStore'
import { buildSourceConfig, toFormValue } from '../utils/sourceConfig'
import {
  AGG_LABEL, DIRECTION_LABEL, PERIOD_TYPE_LABEL, SOURCE_KIND_LABEL,
  fmt, num,
} from '../types/selfrunTypes'
import type {
  Agg, Direction, KpiTemplate, PeriodType, ReaderOption, SelfRunEnumOption,
  SourceKind,
} from '../types/selfrunTypes'

const store = useSelfRunStore()

const visible = ref(false)
const saving = ref(false)
const editing = ref<KpiTemplate | null>(null)

/** `where` 的原始值（从被编辑那条抄来）—— 换取数器时清空，避免两个取数器的条件串味 */
let baseWhere: Record<string, unknown> = {}

interface TplForm {
  name: string
  period_type: PeriodType
  unit: string
  direction: Direction
  goal_value: number | null
  floor_value: number | null
  goal_why: string
  floor_why: string
  agg: Agg
  source_kind: SourceKind
  reader_kind: string
  /** ⚠️ **不用 `null`**：`l2` 是多选（数组），白名单键是单选（字符串）——
   *  空数组与空串都表示「不加这个条件」。混进 `null` 会让 `el-select` 的
   *  类型判定在两个模式下都不成立。 */
  where_value: string | string[]
}

function blankForm(): TplForm {
  return {
    name: '', period_type: 'weekly', unit: '次', direction: 'at_least',
    goal_value: null, floor_value: null, goal_why: '', floor_why: '',
    agg: 'manual_sum', source_kind: 'manual', reader_kind: '', where_value: '',
  }
}

const form = ref<TplForm>(blankForm())

// ── 枚举：一律读后端下发的那一份，前端不抄 ────────────────────

/** 有枚举的那几个键（`readers` / `l2_options` / `module_value_keys` 结构不同，不在此列） */
type EnumKey = 'agg' | 'source_kind' | 'direction' | 'period_type' | 'plan_scope'

/**
 * 下拉选项：**后端给了就用后端的**（`label` 与后端 `*_CHOICES` 同源），
 * 拿不到才落回本地兜底表 —— 后端一挂，下拉至少不是空的。
 */
function opts(key: EnumKey, fallback: Record<string, string>): SelfRunEnumOption[] {
  const list = store.templateEnum?.[key]
  if (list && list.length) return list
  return Object.entries(fallback).map(([value, label]) => ({ value, label }))
}

/** 自建的 key 前缀 —— 一眼看出哪条是「内置」哪条是「我的」 */
function isCustom(row: KpiTemplate): boolean {
  return (row.key ?? '').startsWith('custom_')
}

const readerChoices = computed<ReaderOption[]>(() => store.templateEnum?.readers ?? [])

/**
 * 换了取数器 ⇒ 丢掉上一条的 `where`（两个取数器的条件键往往不同，留着就是串味）。
 *
 * 🔴 用事件带来的**新 kind** 去查 `where_key`，不读 `form.reader_kind` ——
 *    事件先于 `update:readerKind` 到达，此刻表单里还是旧值；靠「谁先赋值」
 *    这种隐式顺序，哪天调一下就会把多选清成空串（`el-select multiple` 会报类型错）。
 */
function onReaderSwitch(nextKind: string) {
  baseWhere = {}
  const wk = readerChoices.value.find(r => r.value === nextKind)?.where_key
  form.value.where_value = wk === 'l2' ? [] : ''
}

// ── 开弹窗 ───────────────────────────────────────────────────

function openCreate() {
  editing.value = null
  baseWhere = {}
  form.value = blankForm()
  // 模板库非空时，默认带上第一条的取数器 —— 少一次手选
  const first = readerChoices.value[0]
  if (first) form.value.reader_kind = first.value
  visible.value = true
}

function openEdit(row: KpiTemplate) {
  editing.value = row
  const cfg = (row.source_config ?? {}) as { kind?: string; where?: Record<string, unknown> }
  baseWhere = { ...cfg.where }        // 摊 undefined 得空对象，不必再兜一层 `?? {}`
  const reader = readerChoices.value.find(r => r.value === cfg.kind)
  const wk = reader?.where_key
  form.value = {
    name: row.name,
    period_type: row.period_type,
    unit: row.unit,
    direction: row.direction,
    goal_value: num(row.goal_value),
    floor_value: num(row.floor_value),
    goal_why: row.goal_why ?? '',
    floor_why: row.floor_why ?? '',
    agg: row.agg,
    source_kind: row.source_kind,
    reader_kind: cfg.kind ?? '',
    where_value: wk ? toFormValue(baseWhere[wk], wk === 'l2') : '',
  }
  visible.value = true
}

// ── 组装 / 保存 ──────────────────────────────────────────────

/** 当前表单 → `source_config`（拼法在 `utils/sourceConfig`，与「改这条 KPI」同一份） */
function buildCfg(): Record<string, unknown> {
  const wk = readerChoices.value.find(r => r.value === form.value.reader_kind)?.where_key
  return buildSourceConfig(
    form.value.source_kind, form.value.reader_kind, wk ?? undefined,
    form.value.where_value, baseWhere,
  )
}

async function save() {
  if (!form.value.name.trim()) {
    ElMessage.warning('先给模板起个名字')
    return
  }
  if (form.value.source_kind !== 'manual' && !form.value.reader_kind) {
    ElMessage.warning('选了自动取数，就得挑一个取数器')
    return
  }
  const payload = {
    name: form.value.name.trim(),
    period_type: form.value.period_type,
    unit: form.value.unit,
    direction: form.value.direction,
    goal_value: form.value.goal_value,
    floor_value: form.value.floor_value,
    goal_why: form.value.goal_why,
    floor_why: form.value.floor_why,
    agg: form.value.agg,
    source_kind: form.value.source_kind,
    source_config: buildCfg(),
  }
  saving.value = true
  try {
    if (editing.value) {
      const res = await store.updateTemplate(editing.value.id, payload)
      const n = res.changed.length
      ElMessage.success(n ? `已保存（改了 ${n} 个字段）` : '没有变化')
    } else {
      const res = await store.createTemplate(payload)
      ElMessage.success(`已新建模板「${res.template.name}」—— 去「创建阶段」里就能挑到它`)
    }
    visible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

/**
 * 删模板。
 *
 * 🔴 必须**先说清影响面**再问 —— 后端的 `used_count` 是「曾被几条 KPI 引用过」。
 *    好消息是：那些 KPI 与读数**一点都不受影响**（模板不是外键）。
 */
async function doDelete(row: KpiTemplate) {
  const used = row.used_count ?? 0
  const body = used
    ? `有 ${used} 条已建 KPI 的来源指向它 —— 删掉之后那些 KPI、它们的读数、往期结论`
      + `一个字都不会变，只是「来源」不再指向任何模板。`
    : '还没有任何 KPI 用过它，删掉不影响任何东西。'
  try {
    await ElMessageBox.confirm(body, `删掉模板「${row.name}」？`, {
      confirmButtonText: '删掉', cancelButtonText: '算了', type: 'warning',
    })
  } catch {
    return
  }
  try {
    const res = await store.deleteTemplate(row.id)
    ElMessage.success(res.note || '已删掉')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '删除失败')
  }
}

defineExpose({ openCreate })
</script>

<style scoped>
.tl-card { border-radius: 10px; }
.tl-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.tl-title { font-weight: 600; }
.tl-spacer { flex: 1; }
.tl-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }
.tl-name { display: flex; align-items: center; gap: 6px; font-weight: 600; }
.tl-why { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.tl-muted { font-size: 12px; color: var(--el-text-color-secondary); }
.tl-foot {
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.7;
}
.tl-dlg-note { margin-top: 6px; }
</style>
