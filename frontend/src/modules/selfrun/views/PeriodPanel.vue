<template>
  <div class="period-panel">
    <!-- ── ① 周期头 ─────────────────────────────────────────── -->
    <div class="pp-head">
      <div class="pp-head-left">
        <h3 class="pp-title">{{ periodType === 'weekly' ? '本周' : '本月' }} · {{ period?.period_key ?? '—' }}</h3>
        <span v-if="period" class="pp-range">
          {{ period.period_start }} ~ {{ period.period_end }}
          <span class="pp-hint">（含起不含止）</span>
        </span>
        <el-tag v-if="period?.is_partial" size="small" type="warning" effect="plain">
          残缺周期 —— 参与展示，不进阶段达标率
        </el-tag>
        <el-tag v-if="period && !view.live" size="small" type="info" effect="plain">
          已归档 · 读的是冻结快照
        </el-tag>
      </div>
      <div class="pp-head-right">
        <el-tooltip v-if="heartbeat?.message" :content="heartbeat.last_seen_at ?? ''" placement="bottom">
          <span class="pp-heartbeat">{{ heartbeat.message }}</span>
        </el-tooltip>
      </div>
    </div>

    <!-- ── ② 判定：分子分母念出来 ───────────────────────────── -->
    <el-card v-if="view.explain" shadow="never" class="pp-judge" :body-style="{ padding: '12px 16px' }">
      <div class="pp-judge-row">
        <span class="pp-judge-value" :style="{ color: statusColor }">{{ statusText }}</span>
        <span class="pp-judge-frac">
          达标 <b>{{ view.explain.ok }}</b> / 计入 <b>{{ view.explain.counted }}</b>
        </span>
        <span class="pp-judge-note">{{ judgeNote }}</span>
      </div>
      <div class="pp-judge-chips">
        <el-tag size="small" effect="plain">共 {{ view.explain.total }} 条</el-tag>
        <el-tag v-if="view.explain.unknown" size="small" effect="plain">
          取不到 {{ view.explain.unknown }}（不进分母）
        </el-tag>
        <el-tag v-if="view.explain.skipped" size="small" effect="plain">
          你说不算 {{ view.explain.skipped }}（不进分母）
        </el-tag>
        <el-tag v-if="view.explain.empty" size="small" effect="plain">
          真的没做 {{ view.explain.empty }}（**进**分母）
        </el-tag>
      </div>
    </el-card>

    <!-- ── ③ 月度三问（只有月度有；归档前后都可改）─────────── -->
    <el-card v-if="periodType === 'monthly' && period" shadow="never" class="pp-questions">
      <template #header>
        <div class="card-header">
          <span>月度三问</span>
          <span class="pp-hint">答「是」的个数 = 本月判定；`未答` 与 `否` 是两回事</span>
        </div>
      </template>
      <div v-for="q in MONTHLY_QUESTIONS" :key="q.key" class="pp-q">
        <div class="pp-q-label">
          {{ q.label }}
          <div class="pp-hint">{{ q.hint }}</div>
        </div>
        <el-radio-group v-model="answers[q.key].answer" size="small">
          <el-radio :value="true">是</el-radio>
          <el-radio :value="false">否</el-radio>
          <el-radio :value="null">未答</el-radio>
        </el-radio-group>
      </div>
      <div class="pp-q-footer">
        <el-button size="small" :loading="savingAnswers" @click="saveAnswers">保存三问</el-button>
        <span class="pp-hint">
          答完之后本月的判定会**跟着重判** —— 这是刻意留的口子：月度要的是结论，不是当月那天的数。
        </span>
      </div>
    </el-card>

    <!-- ── ④ 逐条读数 ──────────────────────────────────────── -->
    <div v-if="readings.length" class="pp-readings">
      <ReadingCard
        v-for="r in readings" :key="r.metric_id"
        :reading="r"
        :editable="canEdit"
        :skipped="skippedIds.includes(r.metric_id)"
        :show-skip="canEdit"
        :metric="metricOf(r.metric_id)"
        @update:skipped="(v: boolean) => toggleSkip(r.metric_id, v)"
        @changed="onChanged"
      />
    </div>
    <el-empty v-else :description="emptyText" />

    <!-- ── ④b 这周留下了什么（v3.62.0）────────────────────────
         🔴 这是全模块**唯一**问「留下了什么」的地方。
            刻意做成**一条扁条**而不是卡片、不是新页签、不是新菜单 ——
            同一个系统里已经有过一次反证：给「输出」单开一个页面，
            它的结局是 23 条、被归档。**新习惯要寄生在既有动线上。**
         ⚠️ 只在**周**视图 + **未归档**时出现：
            · 月度页在讲「这个月」，摆一条「这周」的窄条会串台；
            · 已归档的期里新合成的作品 `created_at` 是今天，
              不可能回填到那一期 —— 摆在这里只会让人以为能补。 -->
    <div v-if="periodType === 'weekly' && !isClosed" class="pp-harvest">
      <span class="pp-harvest-label">这周留下的东西</span>
      <!-- ⚠️ 必须是 `el-popover`，**不能**用 `el-tooltip`：
           两者的插槽语义是**反的** —— `el-tooltip` 的默认插槽是「触发元素」、正文要走 `#content`；
           `el-popover` 才是「`#reference` 触发 + 默认插槽正文」。
           写错**不报错**，只是那段正文被当成触发内容**内联渲染出来、常驻可见**，
           扁条从一行变成三行高 —— 与「就一行、不占位置」的设计意图正好相反。
           本模块其余气泡（SelfRunHub / ReadingCard）也统一用 `el-popover`。 -->
      <el-popover placement="top-start" :width="360" trigger="hover" :show-after="120">
        <template #reference>
          <el-icon class="pp-harvest-icon"><QuestionFilled /></el-icon>
        </template>
        <div class="pp-tip">
          <p><b>作品</b> = 一件从经历里长出来、以后还能再用的东西 —— 可以只有自己看。</p>
          <p>
            这个数就是<b>「留下件数」</b>那条 KPI 的来源：
            这一周你让几件事真的成形了。
          </p>
          <p>
            打勾在各自的页面上（完成里程碑 / 收件箱条目、读完一本书、给日记打「值得留」）；
            在这里只做一件事 —— 把散的东西<b>收成一件</b>。
          </p>
        </div>
      </el-popover>
      <span class="pp-harvest-num">{{ workStore.ready ? `${workStore.currentWorks.length} 件` : '—' }}</span>
      <template v-if="workStore.ready">
        <span class="pp-harvest-sep">·</span>
        <el-button link type="primary" @click="composeVisible = true">
          把这周标记的 {{ pendingThisWeek }} 条整理成一件 →
        </el-button>
      </template>
      <!-- 🔴 「取不到」必须说出来，且**不能显示成 0 件** ——
           `0` 是「这周一件都没留」（事实），`—` 是「读不到」（升级没跑迁移）。
           两者分不开的话，界面会用一句看着合理的话把故障盖过去。 -->
      <span v-else class="pp-hint">
        （读不到作品库 —— 如果刚升级，请先执行迁移：works / selfrun / core）
      </span>
    </div>

    <!-- 🔴 归档后补记入口**关闭**且关闭原因说清 ——
         「点不动又说不出为什么」比「不让点」更糟；而「静默接受」最糟
         （明细里有一笔、结论里没有）。 -->
    <el-alert
      v-if="isClosed" type="info" :closable="false" show-icon class="pp-locked"
      title="这一期已归档定格，补记入口已关闭"
      description="归档之后补记不会、也不该回头改这一期的结论 —— 否则明细账与结论会悄悄分家。要改请先「重开这一期」（在「复盘」页，会留痕）。"
    />

    <!-- ── ⑤ 归档 ──────────────────────────────────────────── -->
    <div v-if="!isClosed && !loading" class="pp-footer">
      <el-button type="primary" :loading="closing" @click="doClose">
        归档这{{ periodType === 'weekly' ? '一周' : '一月' }}
      </el-button>
      <span class="pp-hint">
        🔴 系统**不会自动归档** —— 归不归档、什么时候归是你的动作。
        归档后读数定格，往后重算口径也**不改**它。
      </span>
    </div>
    <div v-else-if="isClosed" class="pp-footer">
      <el-tag type="info" effect="plain">已于 {{ (period?.closed_at ?? '').slice(0, 16) }} 归档</el-tag>
      <el-tag v-if="period?.is_backfilled" type="warning" effect="plain">
        此数是事后补算的（周期结束 {{ backfillDays }} 天后才归档）—— 与「当天归档」不等价
      </el-tag>
      <el-tag v-if="period?.reopen_count" type="info" effect="plain">
        重开过 {{ period.reopen_count }} 次：{{ period?.reopen_reason }}
      </el-tag>
    </div>

    <ComposeDialog v-model="composeVisible" @done="() => {}" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import ReadingCard from '../components/ReadingCard.vue'
import { useSelfRunStore } from '../stores/selfrunStore'
// 「这周留下了什么」扁条要读作品库 —— 这是自我运转与作品的**唯一接合点**。
// ⚠️ 作品有自己的 store（它跨四个模块取来源，不属于自我运转）。
import { useWorkStore } from '@/modules/works/stores/workStore'
import ComposeDialog from '@/modules/works/components/ComposeDialog.vue'
import {
  FALLBACK_COLOR, MONTHLY_QUESTIONS, PERIOD_STATUS_LABEL,
} from '../types/selfrunTypes'
import type { AnswerSheet, PeriodType, Reading, SelfRunMetric } from '../types/selfrunTypes'

const props = defineProps<{
  periodType: PeriodType
  /** 归档后的周期一律只读（补记/跳过都不给） */
  editable: boolean
}>()

const emit = defineEmits<{ (e: 'changed'): void }>()

const store = useSelfRunStore()
const workStore = useWorkStore()
const closing = ref(false)
const savingAnswers = ref(false)
const skippedIds = ref<number[]>([])
const answers = reactive<AnswerSheet>({})
/** 收口台（把标记的东西合成一件）—— 从末尾那条扁条点进来。 */
const composeVisible = ref(false)

/** 这周标记了、还没整理的条数。⚠️ 由后端下发 `in_current_period`，前端只筛。 */
const pendingThisWeek = computed(
  () => workStore.currentCaptures.filter((c) => c.status === 'pending').length,
)

const view = computed(() => (props.periodType === 'weekly' ? store.weekly : store.monthly))
const period = computed(() => view.value.period)
const readings = computed<Reading[]>(() => period.value?.readings ?? [])
const heartbeat = computed(() => store.heartbeatInfo)
const isClosed = computed(() => !!period.value?.closed_at)
const loading = computed(() => store.loading)
/**
 * 🔴 可补记/可勾「先不算」= 阶段没收尾 **且** 这一期还没归档。
 *    归档后仍可写**只有** `review_text` / `answer_sheet`（记忆型 ≠ 数据型）。
 */
const canEdit = computed(() => props.editable && !isClosed.value)

const statusText = computed(() => {
  const v = view.value.explain?.value
  if (!v) return '—'
  return PERIOD_STATUS_LABEL[v] ?? v
})
const statusColor = computed(
  () => store.colors.period[view.value.explain?.value ?? ''] ?? FALLBACK_COLOR,
)
/**
 * 🔴 判定档位文案**不写死阈值** —— 从后端下发的 `thresholds` 念出来，
 *    前端 0 个阈值数字（写死 = 哪天后端调线，界面还在说旧线）。
 */
const judgeNote = computed(() => {
  const v = view.value.explain?.value
  if (v === 'fallow') return '阶段暂停中 —— 休耕不是失败'
  if (v === 'no_record') return '计入的条数为 0 —— 这周什么都没记'
  const bands = view.value.explain?.thresholds ?? {}
  const parts = Object.entries(bands)
    .sort((a, b) => b[1] - a[1])
    .map(([k, lower]) => `≥${Math.round(lower * 100)}% ${PERIOD_STATUS_LABEL[k] ?? k}`)
  return parts.length ? `判定线：${parts.join(' · ')}` : ''
})
const backfillDays = computed(() => {
  const p = period.value
  if (!p?.backfilled_at) return 0
  const d = (new Date(p.backfilled_at).getTime() - new Date(p.period_end).getTime()) / 86400000
  return Math.max(Math.round(d), 0)
})
const emptyText = computed(() =>
  props.periodType === 'weekly' ? '还没有周度 KPI' : '还没有月度 KPI',
)

function metricOf(id: number): SelfRunMetric | null {
  return store.metrics.find(m => m.id === id) ?? null
}

/** 把服务端已保存的 `skipped_metric_ids` / `answer_sheet` 回灌到本地编辑态。 */
watch(period, (p) => {
  skippedIds.value = [...(p?.skipped_metric_ids ?? [])]
  const sheet = p?.answer_sheet ?? {}
  for (const q of MONTHLY_QUESTIONS) {
    answers[q.key] = { answer: sheet[q.key]?.answer ?? null, note: sheet[q.key]?.note ?? '' }
  }
}, { immediate: true, deep: true })

function toggleSkip(metricId: number, v: boolean) {
  if (v && !skippedIds.value.includes(metricId)) skippedIds.value.push(metricId)
  if (!v) skippedIds.value = skippedIds.value.filter(x => x !== metricId)
}

async function doClose() {
  const p = period.value
  if (!p) return
  const label = props.periodType === 'weekly' ? '这一周' : '这一个月'
  const skipTip = skippedIds.value.length
    ? `\n你勾了 ${skippedIds.value.length} 条「本期先不算」—— 它们不进分母。`
    : ''
  try {
    await ElMessageBox.confirm(
      `归档 ${p.period_key}：读数会在这一刻**定格**，以后重算口径不会改它。\n`
      + `归档之后你仍然可以补写「这一期的话」和月度三问。${skipTip}`,
      `归档${label}？`,
      { confirmButtonText: '归档', cancelButtonText: '再等等', type: 'warning' },
    )
  } catch {
    return
  }
  closing.value = true
  try {
    const res = await store.closePeriod({
      period_type: props.periodType,
      period_key: p.period_key,
      skipped_metric_ids: skippedIds.value,
      answer_sheet: props.periodType === 'monthly' ? answers : undefined,
    })
    ElMessage.success(
      res.note || `已归档 ${p.period_key}`,
    )
    emit('changed')
  } catch (e: any) {
    // 409 = 已经归档过了（后端不静默覆盖）—— 原样念出来
    ElMessage.error(e?.response?.data?.detail ?? '归档失败')
  } finally {
    closing.value = false
  }
}

async function saveAnswers() {
  const p = period.value
  if (!p?.id) {
    ElMessage.warning('本期还没有任何记录 —— 先归档一次，三问才会落库。')
    return
  }
  savingAnswers.value = true
  try {
    await store.saveReview(p.id, { answer_sheet: { ...answers } })
    ElMessage.success('已保存，本月判定已重判')
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    savingAnswers.value = false
  }
}

/**
 * 扁条用的两个数（这周成形了几件 / 这周标记了几条）。
 *
 * ⚠️ **失败不许炸整页** —— 作品库还没迁移时这两个 GET 会 500，
 *    而「本周状态」是每天都要看的页，不能因为一个附加区块全白。
 *    吞掉异常后由扁条自己说「读不到作品库」。
 * ⚠️ 必须包含 `loadOverview()` —— 它是本模块**唯一**的就绪判据
 *   （`meta` / `channels` 不碰新表，表没建也回 200，判不出所以然）。
 */
onMounted(async () => {
  try {
    await Promise.all([
      workStore.loadMeta(),
      workStore.loadOverview(),
      workStore.loadWorks(),
      workStore.loadCaptures(),
    ])
  } catch {
    /* 见上：附加区块，失败不阻断主视图 */
  }
})

function onChanged() {
  emit('changed')
}
</script>

<style scoped>
.period-panel { display: flex; flex-direction: column; gap: 12px; }
.pp-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.pp-head-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pp-title { margin: 0; font-size: 17px; font-weight: 600; }
.pp-range { font-size: 13px; color: var(--el-text-color-secondary); }
.pp-heartbeat { font-size: 12px; color: var(--el-text-color-secondary); font-style: italic; }
.pp-hint { font-size: 12px; color: var(--el-text-color-secondary); }

.pp-judge-row { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
.pp-judge-value { font-size: 20px; font-weight: 700; }
.pp-judge-frac { font-size: 14px; color: var(--el-text-color-regular); }
.pp-judge-note { font-size: 12px; color: var(--el-text-color-secondary); }
.pp-judge-chips { margin-top: 8px; display: flex; gap: 6px; flex-wrap: wrap; }

.card-header { display: flex; align-items: center; justify-content: space-between; font-weight: 600; }
.pp-q { padding: 8px 0; border-bottom: 1px dashed var(--el-border-color-lighter); }
.pp-q:last-of-type { border-bottom: none; }
.pp-q-label { font-size: 14px; margin-bottom: 4px; }
.pp-q-footer { display: flex; align-items: center; gap: 10px; margin-top: 10px; flex-wrap: wrap; }

.pp-readings { display: flex; flex-direction: column; }
.pp-locked { margin-top: 4px; }
.pp-footer { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding-top: 4px; }

/* 「这周留下了什么」扁条 —— 一条，不占位置（与页头两把尺子的做法一致） */
.pp-harvest {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 12px; border-radius: 6px;
  background: var(--el-fill-color-light); font-size: 13px;
}
.pp-harvest-label { color: var(--el-text-color-regular); }
.pp-harvest-num { font-weight: 600; font-variant-numeric: tabular-nums; }
.pp-harvest-sep { color: var(--el-text-color-secondary); }
.pp-harvest-icon {
  color: var(--el-text-color-secondary); cursor: help;
  border-bottom: 1px dashed var(--el-border-color); vertical-align: middle;
}
.pp-harvest-icon:hover { color: var(--el-color-primary); }
.pp-tip { max-width: 340px; font-size: 12px; line-height: 1.8; }
.pp-tip p { margin: 0 0 6px; }
.pp-tip p:last-child { margin-bottom: 0; }
</style>
