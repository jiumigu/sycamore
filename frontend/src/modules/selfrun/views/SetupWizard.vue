<template>
  <div id="selfrun-wizard" class="setup-wizard">
    <!-- 步骤条**可点**：往回随便点；往前要逐级过关，过不去就停在那一步、当场说缺什么。
         一条点不动的进度条，读起来就是「找不到配置 KPI 的入口」。 -->
    <el-steps :active="step" align-center finish-status="success" class="sw-steps">
      <el-step
        v-for="(s, i) in STEPS"
        :key="s.title"
        :title="s.title"
        :description="s.description"
        class="sw-step"
        @click="gotoStep(i)"
      />
    </el-steps>

    <!-- ══ STEP 1 · 阶段 ══════════════════════════════════════ -->
    <el-card v-if="step === 0" shadow="never" class="sw-card">
      <el-form :model="form" label-width="110px" style="max-width: 560px">
        <el-form-item label="阶段名称">
          <el-input v-model="form.name" maxlength="100" placeholder="例如：离职后第一季" />
        </el-form-item>
        <el-form-item label="起点">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" />
          <div class="sw-hint">
            默认给你填的是**本周一** —— 起点落在周中，第一个周期就是残缺周
            （它参与展示、但不进阶段达标率）。
          </div>
        </el-form-item>
        <el-form-item label="终点（可选）">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" clearable />
          <div class="sw-hint">不填就一直跑，直到你手动收尾。</div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" maxlength="200" placeholder="可选：这一阶段你想验证什么" />
        </el-form-item>
      </el-form>

      <el-alert
        v-if="closedStages.length" type="info" :closable="false" show-icon
        title="已经跑过一个阶段了？直接用它的配置开新的"
        description="KPI 清单、口径、双档都会带过来 —— 但**目标值仍然是上一阶段的**，需要你逐条重设。历史结论不会复制。"
      />
      <div v-if="closedStages.length" class="sw-copy">
        <el-button size="small" @click="copyVisible = true">复制上一阶段配置</el-button>
      </div>
    </el-card>

    <!-- ══ STEP 2 · 选 KPI ════════════════════════════════════ -->
    <el-card v-else-if="step === 1" shadow="never" class="sw-card">
      <div class="sw-section-head">
        <span>从模板库挑（当前 {{ templates.length }} 条：周 {{ weeklyTplCount }} + 月 {{ templates.length - weeklyTplCount }}）</span>
        <span class="sw-hint">模板只是**起点** —— 抄进你的阶段之后就与模板脱钩了，以后改模板不会回头改你</span>
      </div>
      <div v-if="!store.templates.length" class="sw-empty-tpl">
        模板库是空的 —— 去「制定配置」上区的模板库加一条，或者直接
        <el-button size="small" text type="primary" @click="addCustom">加一条自定义 KPI</el-button>。
      </div>
      <el-checkbox-group v-model="selectedKeys" class="sw-tpl-group">
        <label v-for="t in templates" :key="t.key" class="sw-tpl" :class="{ 'is-on': selectedKeys.includes(t.key) }">
          <el-checkbox :value="t.key" class="sw-tpl-check" />
          <div class="sw-tpl-body">
            <div class="sw-tpl-name">
              {{ t.name }}
              <el-tag size="small" effect="plain">{{ t.period_type === 'weekly' ? '周' : '月' }}</el-tag>
              <el-tag size="small" effect="plain" type="info">{{ SOURCE_KIND_LABEL[t.source_kind] }}</el-tag>
            </div>
            <div class="sw-tpl-tier">
              目标 {{ fmt(t.goal_value, t.unit) }} · 底线 {{ fmt(t.floor_value, t.unit) }}
              <span class="sw-hint">（{{ DIRECTION_LABEL[t.direction] }} · {{ AGG_LABEL[t.agg] }}）</span>
            </div>
            <div v-if="t.goal_why" class="sw-hint">依据：{{ t.goal_why }}</div>
            <div v-if="t.reader_hint" class="sw-hint">取数来源：{{ t.reader_hint }}</div>
          </div>
        </label>
      </el-checkbox-group>

      <div class="sw-add-custom">
        <el-button size="small" text type="primary" @click="addCustom">+ 加一条自定义 KPI</el-button>
        <span class="sw-hint">系统里没有对应模块的（比如宣纸、画）只能手工记 —— 自定义条目默认走手工登记。</span>
      </div>
    </el-card>

    <!-- ══ STEP 3 · 配 KPI ════════════════════════════════════ -->
    <el-card v-else-if="step === 2" shadow="never" class="sw-card">
      <div class="sw-section-head">
        <span>逐条设定目标与底线</span>
        <span class="sw-hint">
          每条都可以先**试算**：拿最近 11 个已过去的周期跑一遍，看看这个数在你的真实历史里落在哪
        </span>
      </div>

      <div v-for="(m, i) in drafts" :key="i" class="sw-kpi">
        <div class="sw-kpi-head">
          <el-input v-model="m.name" size="small" class="sw-kpi-name" placeholder="名称" />
          <el-input v-model="m.unit" size="small" class="sw-kpi-unit" placeholder="单位" />
          <el-tag size="small" effect="plain">{{ m.period_type === 'weekly' ? '周' : '月' }}</el-tag>
          <el-select v-model="m.direction" size="small" class="sw-kpi-dir">
            <el-option v-for="(l, k) in DIRECTION_LABEL" :key="k" :label="l" :value="k" />
          </el-select>
          <el-button size="small" :loading="previewingIdx === i" @click="runPreview(i)">试算</el-button>
          <el-button size="small" text type="danger" @click="drafts.splice(i, 1)">移除</el-button>
        </div>

        <el-row :gutter="12">
          <el-col :span="8">
            <div class="sw-field-label">目标（{{ m.unit || '无单位' }}）</div>
            <el-input-number v-model="m.goal_value" size="small" :min="0" :step="1" style="width: 100%" />
          </el-col>
          <el-col :span="8">
            <div class="sw-field-label">底线（{{ m.unit || '无单位' }}）</div>
            <el-input-number v-model="m.floor_value" size="small" :min="0" :step="1" style="width: 100%" />
          </el-col>
          <el-col :span="8">
            <div class="sw-field-label">达标口径</div>
            <div class="sw-muted">{{ AGG_LABEL[m.agg] ?? m.agg }} · {{ SOURCE_KIND_LABEL[m.source_kind] ?? m.source_kind }}</div>
          </el-col>
        </el-row>

        <el-row :gutter="12" class="sw-why-row">
          <el-col :span="12">
            <el-input v-model="m.goal_why" size="small" maxlength="200" placeholder="目标依据：为什么是这个数" />
          </el-col>
          <el-col :span="12">
            <el-input v-model="m.floor_why" size="small" maxlength="200" placeholder="底线依据：这个底线是从哪来的" />
          </el-col>
        </el-row>

        <!-- 试算结果 -->
        <div v-if="previews[i]" class="sw-preview">
          <div class="sw-preview-head">
            <span>最近 {{ previews[i]!.rows.length }} 个已过去的{{ m.period_type === 'weekly' ? '周' : '月' }}</span>
            <span v-if="statText(i)" class="sw-hint">{{ statText(i) }}</span>
          </div>
          <div class="sw-bars">
            <el-tooltip
              v-for="r in previews[i]!.rows" :key="r.key"
              :content="`${r.key}：${r.value === null ? '取不到' : fmt(r.value, m.unit)}（${VERDICT_LABEL[r.verdict]}）`"
              placement="top"
            >
              <div class="sw-bar-wrap">
                <div
                  class="sw-bar"
                  :style="{ height: barHeight(i, r.value), background: barColor(i, r.value) }"
                />
                <div class="sw-bar-key">{{ r.key.slice(-2) }}</div>
              </div>
            </el-tooltip>
          </div>
          <div v-if="previews[i]!.floor_options.length" class="sw-floor-opts">
            <span class="sw-hint">如果把底线设成：</span>
            <el-tag
              v-for="o in previews[i]!.floor_options" :key="o.floor" size="small" effect="plain"
              :type="m.floor_value === o.floor ? 'success' : 'info'"
              class="sw-floor-opt" @click="m.floor_value = o.floor"
            >
              {{ fmt(o.floor, m.unit) }} → 过去 {{ o.hit }}/{{ o.total }} 期达标
            </el-tag>
            <span class="sw-hint">（点一下就填进去）</span>
          </div>
          <el-alert
            v-for="(w, wi) in previews[i]!.warnings" :key="wi"
            :title="w.hint" type="warning" :closable="false" show-icon class="sw-preview-warn"
          />
        </div>
      </div>

      <el-empty v-if="!drafts.length" description="一条 KPI 都没有 —— 回上一步挑几条" :image-size="60" />
    </el-card>

    <!-- ══ STEP 4 · 生效 ══════════════════════════════════════ -->
    <el-card v-else shadow="never" class="sw-card">
      <div class="sw-section-head"><span>确认一下，然后生效</span></div>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="阶段">{{ form.name || '（未命名）' }}</el-descriptions-item>
        <el-descriptions-item label="起点">{{ form.start_date }}</el-descriptions-item>
        <el-descriptions-item label="终点">{{ form.end_date || '不设（手动收尾）' }}</el-descriptions-item>
        <el-descriptions-item label="KPI 条数">{{ drafts.length }}（周 {{ weeklyCount }} · 月 {{ drafts.length - weeklyCount }}）</el-descriptions-item>
      </el-descriptions>

      <el-table :data="drafts" size="small" class="sw-confirm-table">
        <el-table-column prop="name" label="KPI" min-width="110" />
        <el-table-column label="周期" width="56">
          <template #default="{ row }">{{ row.period_type === 'weekly' ? '周' : '月' }}</template>
        </el-table-column>
        <el-table-column label="目标 / 底线" width="160">
          <template #default="{ row }">{{ fmt(row.goal_value, row.unit) }} / {{ fmt(row.floor_value, row.unit) }}</template>
        </el-table-column>
        <el-table-column label="方向" width="90">
          <template #default="{ row }">{{ DIRECTION_LABEL[row.direction] }}</template>
        </el-table-column>
        <el-table-column label="口径" min-width="130">
          <template #default="{ row }">{{ SOURCE_KIND_LABEL[row.source_kind] }} · {{ AGG_LABEL[row.agg] }}</template>
        </el-table-column>
      </el-table>

      <el-alert
        type="info" :closable="false" show-icon class="sw-write-note"
        title="点「生效」会写这三张表"
        description="selfrun_stage（阶段 1 行）· selfrun_metric（KPI 各 1 行）· selfrun_metric_log（**创建也算一次配置变更**，各 1 行）。一个事务里写完；任何一条校验不过就整批不落库。"
      />
    </el-card>

    <!-- ── 底部导航 ──────────────────────────────────────────
         出口**不关闭自己**：缺东西时按钮照样能点，点了当场说缺什么。
         一个不解释自己的灰按钮，读起来就是「没有入口」。 -->
    <div class="sw-nav">
      <el-button v-if="step > 0" @click="step--">上一步</el-button>
      <span v-if="navHint" class="sw-nav-hint">{{ navHint }}</span>
      <span class="sw-nav-spacer" />
      <el-button v-if="step < 3" type="primary" @click="next">
        下一步 · {{ STEPS[step + 1].title }}
      </el-button>
      <el-button v-else type="primary" :loading="submitting" @click="submit">生效</el-button>
    </div>

    <!-- 复制上一阶段 -->
    <el-dialog v-model="copyVisible" title="复制哪个阶段的配置？" width="460px">
      <el-radio-group v-model="copyFromId" class="sw-copy-list">
        <el-radio v-for="s in closedStages" :key="s.id" :value="s.id" class="sw-copy-item">
          {{ s.name }}（{{ s.start_date }} ~ {{ s.end_date ?? '—' }}）
        </el-radio>
      </el-radio-group>
      <el-alert
        type="warning" :closable="false" show-icon class="sw-write-note"
        title="目标值仍然是上一阶段的，请逐条重设"
        description="否则你改了目标之后会以为「我变差了」，实际是尺子换了。"
      />
      <template #footer>
        <el-button @click="copyVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!copyFromId" :loading="copying" @click="doCopy">复制并开新阶段</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '../api/selfrunApi'
import { useSelfRunStore } from '../stores/selfrunStore'
import {
  AGG_LABEL, DIRECTION_LABEL, SOURCE_KIND_LABEL, VERDICT_LABEL, FALLBACK_COLOR, fmt, num,
} from '../types/selfrunTypes'
import type { KpiTemplate, PreviewResult, SelfRunStage } from '../types/selfrunTypes'

/** 一条待建 KPI 的草稿（**还没落库**，所以 id 不存在） */
interface DraftMetric {
  template_key: string
  name: string
  period_type: 'weekly' | 'monthly'
  unit: string
  direction: 'at_least' | 'at_most'
  goal_value: number | null
  floor_value: number | null
  goal_why: string
  floor_why: string
  agg: string
  source_kind: string
  source_config: Record<string, unknown>
}

const emit = defineEmits<{ (e: 'created'): void }>()

/** 四步的标题与说明：步骤条与「下一步」按钮文案都念这一份，不写两遍 */
const STEPS = [
  { title: '阶段', description: '叫什么、从哪天起' },
  { title: '选 KPI', description: '从模板库挑' },
  { title: '配 KPI', description: '设目标和底线' },
  { title: '生效', description: '写进三张表' },
]

const store = useSelfRunStore()

const step = ref(0)
/**
 * 模板列表**读 store**（不自己拉一份）。
 *
 * 🔴 两份列表迟早分家：刚在上区新建了一条模板，回向导里却挑不到 ——
 *    而界面两处都「看着正常」（不报错，就是少一条）。
 */
const templates = computed<KpiTemplate[]>(() => store.templates)
const weeklyTplCount = computed(() => templates.value.filter(t => t.period_type === 'weekly').length)
const selectedKeys = ref<string[]>([])
const drafts = ref<DraftMetric[]>([])
const previews = reactive<Record<number, PreviewResult | null>>({})
const previewingIdx = ref(-1)
const submitting = ref(false)
const closedStages = ref<SelfRunStage[]>([])
const copyVisible = ref(false)
const copyFromId = ref<number | null>(null)
const copying = ref(false)

const form = reactive({
  name: '',
  start_date: '',
  end_date: '' as string | null,
  note: '',
})

/** 本周一 —— 起点对齐周一，避免第一个周期天生是残缺周。 */
function thisMonday(): string {
  const d = new Date()
  const day = (d.getDay() + 6) % 7          // 周一 = 0
  d.setDate(d.getDate() - day)
  return d.toISOString().slice(0, 10)
}

onMounted(async () => {
  form.start_date = thisMonday()
  // 模板库一般已由父页拉过（`SelfRunHub.reload`）；单独打开时补一次
  try {
    if (!store.templates.length) await store.loadTemplates()
  } catch {
    ElMessage.error('加载模板库失败')
  }
  try {
    const res = await api.listStages({ status: 'closed' })
    closedStages.value = res.data
  } catch {
    closedStages.value = []
  }
})

const weeklyCount = computed(() => drafts.value.filter(d => d.period_type === 'weekly').length)

/**
 * 第 i 步「过不去」的原因（null = 能过）。
 *
 * 🔴 同一份判据喂三个地方：按钮的拦截、步骤条的拦截、导航栏那行小字 ——
 *    写三遍就一定会有一天只改了其中一处（而且不报错）。
 * 🔴 校验的是**最终生效值**：两条数都在时，目标不能比底线松。
 *    某条只填了目标、没填底线是**合法**的 —— 那是「没有底线」，不是「填错了」。
 */
function blockReasonAt(i: number): string | null {
  if (i === 0) {
    if (!form.name.trim()) return '先给这个阶段起个名字'
    if (!form.start_date) return '先选一个起点（默认已填本周一）'
    return null
  }
  if (i === 1) {
    // 🔴 这一步要判的是「**勾选**了几条」，不是「草稿里有几条」——
    //    `drafts` 要等离开这一步（`watch(step)` → `syncDrafts()`）才被填上，
    //    在第二步读 `drafts.length` 永远是 0 ⇒ 勾了一屏也会说「一条都没挑」，
    //    而且**下一步按钮照样能点**（出口不关闭自己），点下去只弹一句警告，
    //    界面就变成「勾了却说没勾」（用户报的就是这个）。
    //    自定义条目是直接 push 进 `drafts` 的，所以两边都要看。
    const custom = drafts.value.filter(d => !d.template_key).length
    if (!selectedKeys.value.length && !custom) {
      return '先挑至少一条 KPI（没有合适的就自己加一条）'
    }
    return null
  }
  if (i === 2) {
    const nameless = drafts.value.find(d => !d.name.trim())
    if (nameless) return '有个 KPI 还没填名称'
    const loose = drafts.value.find((d) => {
      const g = num(d.goal_value as any)
      const f = num(d.floor_value as any)
      if (g === null || f === null) return false
      return d.direction === 'at_least' ? g < f : g > f
    })
    if (loose) {
      const g = fmt(loose.goal_value as any, loose.unit)
      const f = fmt(loose.floor_value as any, loose.unit)
      return loose.direction === 'at_least'
        ? `「${loose.name}」目标 ${g} 低于底线 ${f} —— 目标不能低于底线`
        : `「${loose.name}」目标 ${g} 高于底线 ${f} —— 目标不能高于底线`
    }
    return null
  }
  return null
}

/** 常驻小字：现在还差什么。不差就不渲染（不占地方，也不说废话） */
const navHint = computed(() => blockReasonAt(step.value))

/**
 * 下一步：缺东西**不拦按钮**，点了才说。
 * 🔴 出口控件不得关闭自己 —— 恒灰的按钮不解释自己，读起来就是「没入口」。
 */
function next() {
  const miss = blockReasonAt(step.value)
  if (miss) {
    ElMessage.warning(miss)
    return
  }
  step.value++
}

/** 点步骤条：往回随便点；往前逐级过关，过不去就停在那一步并说原因 */
function gotoStep(i: number) {
  if (i === step.value) return
  if (i < step.value) {
    step.value = i
    return
  }
  for (let j = step.value; j < i; j++) {
    const miss = blockReasonAt(j)
    if (miss) {
      step.value = j
      ElMessage.warning(miss)
      return
    }
  }
  step.value = i
}

/** 按模板抄一条草稿（**拷贝不是引用** —— 抄进阶段之后与模板脱钩）。 */
function draftOfTemplate(t: KpiTemplate): DraftMetric {
  return {
    template_key: t.key,
    name: t.name,
    period_type: t.period_type,
    unit: t.unit,
    direction: t.direction,
    goal_value: num(t.goal_value),
    floor_value: num(t.floor_value),
    goal_why: t.goal_why,
    floor_why: t.floor_why,
    agg: t.agg,
    source_kind: t.source_kind,
    source_config: t.source_config,
  }
}

/**
 * 选完模板、进第二步时同步草稿（**拷贝不是引用**）。
 *
 * 🔴 已经配过的条目**不许被重建**，两类都要保住：
 *    · **自定义条目**（`template_key === ''`）不属于任何模板 —— 若按 `selectedKeys`
 *      重建，正好把它整条抹掉：「+ 加一条自定义 KPI」→ 点下一步 → 那条没了，
 *      而且**不报错**（用户会以为自己没点中）；
 *    · **模板条目按 `template_key` 认身份**，不把名称算进去 —— 否则你一改名，
 *      再回上一步就发现这条被当成新的、改动全丢。
 */
function syncDrafts() {
  const keptCustom = drafts.value.filter(d => !d.template_key)
  const keptByKey = new Map(
    drafts.value.filter(d => d.template_key).map(d => [d.template_key, d]),
  )
  drafts.value = selectedKeys.value
    .map(k => templates.value.find(t => t.key === k))
    .filter((t): t is KpiTemplate => !!t)
    .map(t => keptByKey.get(t.key) ?? draftOfTemplate(t))
    .concat(keptCustom)
}

/**
 * 「+ 加一条自定义 KPI」。
 *
 * 🔴 点了必须**立刻看得见**：新条目进的是第二步的草稿列表（`drafts`），
 *    而第一步根本不渲染它 —— 只 push 不跳步的话，屏幕上一动不动
 *    （正是「赋值了却没人读 = 点不动」那一类）。所以直接送到第二步并滚到那一条。
 */
function addCustom() {
  drafts.value.push({
    template_key: '',
    name: '',
    period_type: 'weekly',
    unit: '次',
    direction: 'at_least',
    goal_value: null,
    floor_value: null,
    goal_why: '',
    floor_why: '',
    agg: 'manual_sum',
    source_kind: 'manual',
    source_config: { kind: 'manual_sum' },
  })
  step.value = 2
  nextTick(() => {
    const cards = document.querySelectorAll('#selfrun-wizard .sw-kpi')
    cards[cards.length - 1]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

// ── 试算可视化（纯 CSS 柱，不走图表库）────────────────────
function maxOf(i: number): number {
  const rows = previews[i]?.rows ?? []
  return Math.max(1, ...rows.map(r => num(r.value) ?? 0))
}
function barHeight(i: number, v: number | null): string {
  const n = num(v)
  if (n === null) return '4px'
  return `${Math.max(4, Math.round((n / maxOf(i)) * 64))}px`
}
function barColor(i: number, v: number | null): string {
  const n = num(v)
  if (n === null) return FALLBACK_COLOR
  const d = drafts.value[i]
  if (!d) return FALLBACK_COLOR
  const f = num(d.floor_value as any)
  if (f === null) return '#93C5FD'
  const hit = d.direction === 'at_least' ? n >= f : n <= f
  return hit ? '#10B981' : FALLBACK_COLOR
}
function statText(i: number): string {
  const p = previews[i]
  if (!p) return ''
  const s: any = p.stats
  if (!s?.count) return '这段时间里取不到任何数 —— 先确认数据源有没有在用'
  return `中位数 ${s.median} · 均值 ${s.mean} · 区间 ${s.min}~${s.max}（共 ${s.count} 期有数）`
}

async function runPreview(i: number) {
  const d = drafts.value[i]
  if (!d) return
  previewingIdx.value = i
  try {
    const res = await api.previewMetric({
      period_type: d.period_type,
      name: d.name,
      unit: d.unit,
      direction: d.direction,
      agg: d.agg,
      source_kind: d.source_kind,
      source_config: d.source_config,
      goal_value: d.goal_value,
      floor_value: d.floor_value,
      periods: 11,
    })
    previews[i] = res.data
  } catch (e: any) {
    previews[i] = null
    ElMessage.error(e?.response?.data?.detail ?? '试算失败')
  } finally {
    previewingIdx.value = -1
  }
}

async function doCopy() {
  const src = closedStages.value.find(s => s.id === copyFromId.value)
  if (!src || !form.name.trim()) {
    ElMessage.warning('先在上面填好新阶段的名称')
    return
  }
  copying.value = true
  try {
    const res = await api.copyStage({
      from_stage_id: src.id, name: form.name.trim(), start_date: form.start_date,
    })
    ElMessage.success(res.data.note)
    copyVisible.value = false
    emit('created')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '复制失败')
  } finally {
    copying.value = false
  }
}

async function submit() {
  submitting.value = true
  try {
    const res = await api.createStage({
      name: form.name.trim(),
      start_date: form.start_date,
      end_date: form.end_date || null,
      note: form.note,
      metrics: drafts.value.map(d => ({
        template_key: d.template_key,
        name: d.name,
        period_type: d.period_type,
        unit: d.unit,
        direction: d.direction,
        goal_value: d.goal_value,
        floor_value: d.floor_value,
        goal_why: d.goal_why,
        floor_why: d.floor_why,
        agg: d.agg,
        source_kind: d.source_kind,
        source_config: d.source_config,
      })),
    })
    const w = res.data.written
    ElMessage.success(
      `已生效 —— 写了 ${Object.entries(w).map(([k, v]) => `${k} ${v} 行`).join(' · ')}`,
    )
    emit('created')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '生效失败')
  } finally {
    submitting.value = false
  }
}

// 第二步 → 第三步 时同步草稿：**模板是拷贝不是引用** ——
// 把模板值抄进草稿之后，草稿与模板就脱钩了（模板以后改了不影响你已经配好的）。
// 已经是第二次进这一步的条目按「模板 key + 名称」保留原编辑，不覆盖你的输入。
watch(step, (v, old) => {
  if (old === 1 && v === 2) syncDrafts()
  if (v === 3) {
    // 进最后一步时把「试算面板」收起来，避免被误读成最终结果
    Object.keys(previews).forEach(k => delete previews[Number(k)])
  }
})

/**
 * 给父页用的显式入口（空态卡片上那个「开始配置 KPI」）：
 * 回到第一步 → 滚过来 → 光标放进「阶段名称」。
 * 目的就一个：让人一眼看见**从哪儿开始**，而不是在这一屏里自己找按钮。
 * ⚠️ 要 `nextTick`：`step` 改回 0 之后 DOM 才重建，早一步滚不到、也聚焦不了。
 */
function focusStart() {
  step.value = 0
  nextTick(() => {
    document.getElementById('selfrun-wizard')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    ;(document.querySelector('#selfrun-wizard input') as HTMLInputElement | null)?.focus()
  })
}

defineExpose({ focusStart })
</script>

<style scoped>
.setup-wizard { display: flex; flex-direction: column; gap: 14px; }
.sw-steps { margin-bottom: 4px; }
/* 步骤条可点 —— scoped 样式能命中子组件的根元素 */
.sw-step { cursor: pointer; }
.sw-step:hover :deep(.el-step__title) { color: var(--el-color-primary); }
.sw-card { border-radius: 10px; }
.sw-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }
.sw-muted { font-size: 12px; color: var(--el-text-color-regular); }

.sw-section-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 10px; font-weight: 600;
}
.sw-copy { margin-top: 10px; }

.sw-empty-tpl {
  font-size: 13px; color: var(--el-text-color-regular); line-height: 1.8;
  padding: 10px 12px; margin-bottom: 10px;
  border: 1px dashed var(--el-border-color); border-radius: 8px;
  background: var(--el-fill-color-lighter);
}
/* 🔴 `font-size` / `line-height` 必须在这里顶掉，不是样式口味问题：
   这个元素**就是** `el-checkbox-group` 的根（class 传下去会落在同一个节点上），
   而 Element 自带的 `.el-checkbox-group{font-size:0;line-height:0}` 会一路继承下去 ——
   卡里的文字（`.sw-tpl-name` / `.sw-tpl-tier`）自己没写 line-height，
   就会拿到 0 ⇒ 行盒高度算成 0。
   目前看着还行**纯属侥幸**：那两行里各塞了自带样式的 Element 子件
   （`el-tag`、行内的 `.sw-hint`），是它们把行盒撑起来的 —— 哪天文案改了、
   某个子件没了，文字就会开始互相压。同款坑的实拍见 ComposeDialog 文件头。
   ⚠️ 未实测（当前有在跑的阶段，向导第一步进不去），下次开新阶段时看一眼。 */
.sw-tpl-group {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px;
  font-size: 14px; line-height: 1.6;
}
.sw-tpl {
  display: flex; gap: 8px; padding: 10px 12px; cursor: pointer;
  border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  transition: border-color .15s, background .15s;
}
.sw-tpl.is-on { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.sw-tpl-check { height: 22px; }
.sw-tpl-body { min-width: 0; }
.sw-tpl-name { display: flex; align-items: center; gap: 6px; font-weight: 600; font-size: 14px; flex-wrap: wrap; }
.sw-tpl-tier { font-size: 12px; color: var(--el-text-color-regular); margin-top: 2px; }
.sw-add-custom { margin-top: 12px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.sw-kpi {
  border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  padding: 12px; margin-bottom: 12px;
}
.sw-kpi-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.sw-kpi-name { width: 180px; }
.sw-kpi-unit { width: 80px; }
.sw-kpi-dir { width: 140px; }
.sw-field-label { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.sw-why-row { margin-top: 8px; }

.sw-preview {
  margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.sw-preview-head { display: flex; align-items: baseline; gap: 12px; font-size: 13px; margin-bottom: 8px; flex-wrap: wrap; }
.sw-bars { display: flex; align-items: flex-end; gap: 4px; height: 80px; }
.sw-bar-wrap { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; flex: 1; height: 100%; }
.sw-bar { width: 100%; max-width: 34px; border-radius: 3px 3px 0 0; transition: height .2s; }
.sw-bar-key { font-size: 10px; color: var(--el-text-color-secondary); margin-top: 2px; }
.sw-floor-opts { margin-top: 8px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.sw-floor-opt { cursor: pointer; }
.sw-preview-warn { margin-top: 8px; }

.sw-confirm-table { margin-top: 12px; }
.sw-write-note { margin-top: 12px; }

.sw-nav { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.sw-nav-spacer { flex: 1; }
.sw-nav-hint {
  font-size: 12px;
  color: var(--el-color-warning);
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--el-color-warning-light-9);
}
.sw-copy-list { display: flex; flex-direction: column; gap: 6px; }
.sw-copy-item { margin-right: 0; }

@media (max-width: 900px) {
  .sw-tpl-group { grid-template-columns: 1fr; }
}
</style>
