<template>
  <div class="reading-card" :class="{ 'is-skipped': skipped, 'is-unknown': reading.verdict === 'unknown' }">
    <!-- ① 主行：名称 · 档位 · 本期值 · 判定 -->
    <div class="rc-main">
      <div class="rc-left">
        <span class="rc-dot" :style="{ background: verdictColor }" />
        <span class="rc-name">{{ reading.name }}</span>
        <span class="rc-tier">{{ tierText(reading) }}</span>
        <!-- 🔴 「这一期的目标是**哪来的**」必须显示出来 —— 三条全显示成同一个数的话，
             「我这周的目标怎么变了」永远说不清。`metric`（阶段默认）刻意不挂标签。 -->
        <el-tooltip v-if="sourceTip" :content="sourceTip" placement="top">
          <el-tag size="small" effect="plain" :type="TARGET_SOURCE_TAG[reading.target_source] || 'info'">
            {{ reading.target_source_label }}
          </el-tag>
        </el-tooltip>
        <el-tag v-if="reading.source_kind === 'auto_plus_manual'" size="small" effect="plain" type="warning">
          自动 + 补记
        </el-tag>
        <el-tag v-else-if="reading.source_kind === 'manual'" size="small" effect="plain">手工</el-tag>
      </div>
      <div class="rc-right">
        <span class="rc-value" :style="{ color: verdictColor }">{{ valueText }}</span>
        <el-tag size="small" :color="verdictColor" class="rc-verdict" effect="dark">
          {{ VERDICT_LABEL[reading.verdict] ?? reading.verdict }}
        </el-tag>
      </div>
    </div>

    <!-- ② 状态说明：`unknown` / `empty` / `stale` 必须**各自把话说清**
         （未知≠没做，没记≠没做 —— 这三者的界面表现必须不同） -->
    <div v-if="explainText" class="rc-explain" :class="{ 'is-warn': reading.state === 'stale' }">
      <el-icon><InfoFilled /></el-icon>
      <span>{{ explainText }}</span>
      <el-link
        v-if="reading.state === 'stale' && reading.freshness.hint"
        type="primary" :underline="false" class="rc-link"
        @click="$router.push(freshnessRoute)"
      >
        去「{{ reading.freshness.hint }}」补 →
      </el-link>
    </div>

    <!-- ③ 告警：越界值 / 两把尺子打架 / 算不出来 —— 不报就等于没发生 -->
    <el-alert
      v-for="(w, i) in reading.warnings" :key="i"
      :title="w.hint" type="warning" :closable="false" show-icon class="rc-alert"
    />

    <!-- ④ 操作行 -->
    <div v-if="editable" class="rc-actions">
      <el-button v-if="canCheckin" size="small" text type="primary" @click="openCheckin">
        + 补记
      </el-button>
      <el-tooltip v-else content="自动取数项没有补记入口 —— 自动取错了请去改数据源" placement="top">
        <span class="rc-disabled-hint">自动取数 · 不可补记</span>
      </el-tooltip>

      <el-button v-if="canCheckin" size="small" text @click="openHistory">
        明细
      </el-button>
      <el-button v-if="sourceKind !== 'auto'" size="small" text @click="openEdit">
        改这条
      </el-button>

      <el-checkbox
        v-if="showSkip"
        :model-value="skipped"
        size="small"
        class="rc-skip"
        @update:model-value="(v: any) => emit('update:skipped', !!v)"
      >
        本期这条先不算
      </el-checkbox>

      <el-button size="small" text class="rc-fold" @click="showBreakdown = !showBreakdown">
        溯源 {{ reading.breakdown_total }} 条
        <el-icon><component :is="showBreakdown ? ArrowUp : ArrowDown" /></el-icon>
      </el-button>
    </div>

    <!-- ⑤ 溯源：只报「多少个来源」，不报来源 = 你无法验证这个数 -->
    <div v-if="showBreakdown" class="rc-breakdown">
      <div v-if="reading.auto_value !== null" class="rc-mix">
        自动取到 <b>{{ fmt(reading.auto_value, reading.unit) }}</b>
        <template v-if="reading.manual_value">
          ＋ 手工补记 <b>{{ fmt(reading.manual_value, reading.unit) }}</b>
          ＝ <b>{{ fmt(reading.final_value, reading.unit) }}</b>
        </template>
      </div>
      <div v-if="!reading.breakdown.length" class="rc-empty">这一期没有任何明细行。</div>
      <ul v-else class="rc-list">
        <li v-for="(b, i) in reading.breakdown" :key="i">
          <span class="rc-b-label">{{ b.label }}</span>
          <span v-if="b.l2" class="rc-b-l2">{{ b.l2 }}</span>
          <span v-if="b.extra?.note" class="rc-b-note">{{ b.extra.note }}</span>
          <span v-if="b.extra?.title" class="rc-b-note">{{ b.extra.title }}</span>
          <span class="rc-b-value">{{ fmt(b.value, '') }}</span>
          <!-- 结构化事实：金额走 `formatSignedAmount`（唯一口径，含隐私掩码） -->
          <span v-if="b.extra?.facts?.length" class="rc-b-facts">
            <span v-for="(f, fi) in (b.extra?.facts || [])" :key="fi" class="rc-b-fact">
              {{ f.label }}
              <b>{{ f.kind === 'amount' ? formatSignedAmount(f.value) : f.value }}</b>
            </span>
          </span>
        </li>
      </ul>
      <div v-if="reading.breakdown_total > reading.breakdown.length" class="rc-more">
        另有 {{ reading.breakdown_total - reading.breakdown.length }} 条未在此列出（列表上限 50 条）。
      </div>
    </div>

    <!-- 补记弹窗 -->
    <el-dialog v-model="checkinVisible" :title="`补记：${reading.name}`" width="460px">
      <el-form label-width="80px">
        <el-form-item label="日期">
          <el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item :label="`数量（${reading.unit || '无单位'}）`">
          <el-input-number v-model="form.value" :min="0.5" :step="1" style="width: 180px" />
        </el-form-item>
        <!-- 🔴 备注放大：单行输入框里长备注只能看见尾巴，而备注是**唯一**能解释
             「当时为什么这么记」的东西 ⇒ 至少给 3 行，且允许自己再拉高。 -->
        <el-form-item label="备注">
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
            resize="vertical"
            placeholder="可选 —— 顺手写清「为什么」，往后回看时只有这一行能解释得通"
          />
        </el-form-item>
      </el-form>
      <!-- 🔴 整块提示收成一行锚点（用户 2026-10-13 第五轮拍板）。
           判据同 §79：读一次就够的说明进气泡，「记下 / 取消」两个出口留在页面上。
           ⚠️ 锚点必须**自带可悬停的样子**（问号 + 虚线下划线 + `cursor: help`）——
              只把一句话压光标下而不改样貌，等于没人知道这里能悬停。
           ⚠️ 气泡 teleport 到 body：正文样式写在 scoped 里**仍会命中**
              （插槽在本组件编译）；宽度只能走 `:width`，不能靠 popper-class。 -->
      <div class="rc-tip-bar">
        <el-popover placement="top-start" :width="380" trigger="hover" :show-after="120">
          <template #reference>
            <span class="rc-tip-anchor">
              <el-icon><QuestionFilled /></el-icon>
              <span>写错了怎么办</span>
            </span>
          </template>
          <div class="rc-tip-body">
            <p>点「记下」只会<b>新增一笔流水</b>，不动别的数。</p>
            <p>
              写错了不要紧 —— 点「明细」里那一笔的「撤销」，
              系统会<b>补一条负数冲销</b>，原记录保留。
            </p>
            <p class="rc-tip-foot">
              补一条负数而不是删掉它，是为了让已归档的周期和明细账仍对得上。
            </p>
          </div>
        </el-popover>
      </div>
      <template #footer>
        <el-button @click="checkinVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCheckin">记下</el-button>
      </template>
    </el-dialog>

    <!-- 明细弹窗 -->
    <el-dialog v-model="historyVisible" :title="`明细：${reading.name}`" width="560px">
      <el-table :data="checkins" size="small" empty-text="没有手工登记记录">
        <el-table-column prop="checkin_date" label="日期" width="110" />
        <el-table-column label="数量" width="90">
          <template #default="{ row }">{{ fmt(row.value, reading.unit) }}</template>
        </el-table-column>
        <el-table-column prop="note" label="备注" show-overflow-tooltip />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button
              v-if="num(row.value) !== null && num(row.value)! > 0"
              size="small" text type="danger" @click="doReverse(row)"
            >
              撤销
            </el-button>
            <span v-else class="rc-disabled-hint">冲销</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="historyVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 改配置弹窗 -->
    <MetricConfigDialog
      v-model="editVisible"
      :metric="metric"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, ArrowUp, InfoFilled, QuestionFilled } from '@element-plus/icons-vue'
import MetricConfigDialog from './MetricConfigDialog.vue'
import * as api from '../api/selfrunApi'
import { useSelfRunStore } from '../stores/selfrunStore'
import {
  FALLBACK_COLOR, TARGET_SOURCE_TAG, VERDICT_LABEL, fmt, num, tierText,
} from '../types/selfrunTypes'
import { formatSignedAmount } from '@/shared/utils/format'
import type { Reading, SelfRunCheckin, SelfRunMetric } from '../types/selfrunTypes'

const props = withDefaults(defineProps<{
  reading: Reading
  /** 可操作（归档后的周期一律只读 ⇒ false） */
  editable?: boolean
  /** 本期你勾了「这条先不算」 */
  skipped?: boolean
  /** 是否显示「本期这条先不算」（只有归档前才需要） */
  showSkip?: boolean
  metric?: SelfRunMetric | null
}>(), {
  editable: false,
  skipped: false,
  showSkip: false,
  metric: null,
})

const emit = defineEmits<{
  (e: 'update:skipped', v: boolean): void
  (e: 'changed'): void
}>()

const store = useSelfRunStore()

const showBreakdown = ref(false)
const checkinVisible = ref(false)
const historyVisible = ref(false)
const editVisible = ref(false)
const saving = ref(false)
const checkins = ref<SelfRunCheckin[]>([])
const form = ref({ date: '', value: 1, note: '' })

/** 🔴 配色**由后端下发**；拿不到才用中性兜底灰（前端不做第二份彩色表）。 */
const verdictColor = computed(
  () => store.colors.verdict[props.reading.verdict] ?? FALLBACK_COLOR,
)

const sourceKind = computed(() => props.reading.source_kind)
/** 自动取数项**没有**补记入口（「一个写口」原则） */
const canCheckin = computed(() => sourceKind.value !== 'auto')

/**
 * 「这一期的目标是谁定的」——`metric`（阶段默认）返回空串，**不挂标签**。
 * 挂悬停说明是为了回答「哪里改的」，否则你只知道变了、不知道怎么变回去。
 */
const sourceTip = computed(() => {
  const r = props.reading
  if (!r.target_source || r.target_source === 'metric') return ''
  const how = r.plan_scope === 'from' ? '从某一期起一直用它' : '只改了那一期'
  const note = r.plan_note ? `；备注：${r.plan_note}` : ''
  return `${r.target_source_label}（${how}）—— 去「制定配置 → 按期修订」能看到与改回${note}`
})

/**
 * 🔴 本期值展示的**三分支**（`null ≠ 0` 的落点）：
 *   - `unknown`（取不到 / 未配置 / 源过期）⇒ 「—」，**不是 0**；
 *   - 真 0（源里一条都没有）⇒ 「0h」；
 *   - 有数 ⇒ 带单位。
 */
const valueText = computed(() => {
  const r = props.reading
  if (r.verdict === 'unknown') return '—'
  return fmt(r.final_value, r.unit)
})

/**
 * 🔴 状态说明必须把「为什么是这个判定」说出来 ——
 * 三个最容易混的口径：`unknown`（系统不知道）/ `empty`（真的没做）/ `stale`（源没更新）。
 */
const explainText = computed(() => {
  const r = props.reading
  if (r.state === 'unconfigured') {
    return '这条还没设目标线 —— 只展示数值，不参与判定。'
  }
  if (r.state === 'stale') {
    const f = r.freshness
    const days = f.days ?? '?'
    const limit = f.limit ?? '?'
    return `数据源已 ${days} 天没更新（上限 ${limit} 天）—— 这不是「你没做」，是「没有数据」。本期不计入判定。`
  }
  if (r.verdict === 'unknown') {
    const w = r.warnings.find(x => x.code === 'uncomputable')
    return w?.hint ?? '系统取不到这个数 —— 「没记」不等于「没做」，本期不计入判定。'
  }
  if (r.verdict === 'empty') {
    return '本期一条记录都没有 —— 这是「真的没做」，会计入分母。'
  }
  if (r.skipped) {
    return '你本期勾了「这条先不算」—— 不进分母。'
  }
  return ''
})

/** 「数据源过期」时给一个**出口**（否则等于只报错不解决） */
const freshnessRoute = computed(() => {
  const hint = props.reading.freshness.hint ?? ''
  const map: Record<string, string> = {
    时间统计: '/temporal',
    日记流: '/temporal/daily',
    健康管理: '/health',
    财务管理: '/wealth',
  }
  return map[hint] ?? '/dashboard'
})

function openCheckin() {
  form.value = { date: new Date().toISOString().slice(0, 10), value: 1, note: '' }
  checkinVisible.value = true
}

async function submitCheckin() {
  saving.value = true
  try {
    await store.checkin(
      props.reading.metric_id, form.value.value, form.value.date, form.value.note || undefined,
    )
    checkinVisible.value = false
    ElMessage.success('已记下')
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '登记失败')
  } finally {
    saving.value = false
  }
}

async function openHistory() {
  historyVisible.value = true
  try {
    const res = await api.listCheckins({ metric_id: props.reading.metric_id })
    checkins.value = res.data
  } catch {
    checkins.value = []
  }
}

async function doReverse(row: SelfRunCheckin) {
  try {
    await ElMessageBox.confirm(
      '撤销会新增一条负数流水，原记录保留（撤销 ≠ 删除）—— 否则已归档的周期会和明细账对不上。',
      '撤销这一笔？',
      { confirmButtonText: '撤销', cancelButtonText: '算了', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await store.reverseCheckin(row.id)
    ElMessage.success('已冲销')
    await openHistory()
    emit('changed')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '冲销失败')
  }
}

function openEdit() {
  editVisible.value = true
}

async function onSaved() {
  await store.refreshAfterWrite()
  emit('changed')
}
</script>

<style scoped>
.reading-card {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  margin-bottom: 8px;
  background: var(--el-bg-color);
}
.reading-card.is-skipped { opacity: 0.55; }
.reading-card.is-unknown { background: var(--el-fill-color-lighter); }

.rc-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.rc-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
.rc-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.rc-name { font-weight: 600; font-size: 14px; }
.rc-tier { font-size: 12px; color: var(--el-text-color-secondary); }
.rc-right { display: flex; align-items: center; gap: 8px; }
.rc-value { font-size: 18px; font-weight: 700; min-width: 64px; text-align: right; }
.rc-verdict { border: none; }

.rc-explain {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary);
}
.rc-explain.is-warn { color: var(--el-color-warning); }
.rc-link { font-size: 12px; }

.rc-alert { margin-top: 6px; }

.rc-actions {
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
  margin-top: 6px;
}
.rc-skip { margin-left: auto; font-size: 12px; }
.rc-fold { margin-left: 0; }
.rc-disabled-hint { font-size: 12px; color: var(--el-text-color-disabled); }

.rc-breakdown {
  margin-top: 8px; padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px;
}
.rc-mix { margin-bottom: 6px; color: var(--el-text-color-regular); }
.rc-list { list-style: none; margin: 0; padding: 0; }
.rc-list li {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  padding: 3px 0;
}
.rc-b-label { min-width: 88px; color: var(--el-text-color-regular); }
.rc-b-l2 { color: var(--el-text-color-secondary); }
.rc-b-note { color: var(--el-text-color-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rc-b-value { margin-left: auto; font-weight: 600; }
/* 结构化事实（科目 / 总资产 / 负债 / 净资产…）
   —— 独占第二行，`padding-left` = label 的 min-width + gap，与首列对齐；
   用 `flex-basis:100%` 换行而不是另起一个 <li>：一条溯源就是一行，不许多算。 */
.rc-b-facts {
  flex-basis: 100%; display: flex; flex-wrap: wrap; gap: 2px 12px;
  padding-left: 96px; color: var(--el-text-color-secondary);
}
.rc-b-fact b { font-weight: 600; color: var(--el-text-color-regular); }
.rc-empty, .rc-more { color: var(--el-text-color-secondary); }

/* ── 补记弹窗：提示收成一行锚点（正文在悬停气泡里）──────────────
   与「制定配置」那条同款（问号图标 + 虚线下划线 + `cursor: help`）——
   同一个交互在模块里只有一种长相，别让人学两遍。 */
.rc-tip-bar {
  margin-top: 4px; padding: 8px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px; background: var(--el-fill-color-blank);
}
.rc-tip-anchor {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--el-text-color-regular);
  cursor: help;
  border-bottom: 1px dashed var(--el-border-color);
}
.rc-tip-anchor:hover { color: var(--el-color-primary); border-bottom-color: var(--el-color-primary); }
.rc-tip-anchor .el-icon { color: var(--el-text-color-placeholder); }

/* 气泡正文。
   ⚠️ 它被 teleport 到 `body`，但元素是在**本组件**的模板里编译的、仍带 scope id
      ⇒ scoped 样式照常命中；气泡**外壳**（`.el-popper`）没有 scope id，
      宽度只能靠 popover 的 `:width` 给。 */
.rc-tip-body { font-size: 12px; line-height: 1.85; color: var(--el-text-color-regular); }
.rc-tip-body p { margin: 0 0 6px; }
.rc-tip-body p:last-child { margin-bottom: 0; }
.rc-tip-body b { color: var(--el-text-color-primary); }
.rc-tip-foot {
  padding-top: 6px;
  border-top: 1px dashed var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
}
</style>
