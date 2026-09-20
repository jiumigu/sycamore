<template>
  <div class="control-card">
    <div class="control-card__header">
      <div class="control-card__title">现金流推演</div>
      <el-radio-group v-model="mode" size="small">
        <el-radio-button value="duration">算能撑多久</el-radio-button>
        <el-radio-button value="budget">算每天可花</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 输入区 -->
    <div class="control-card__form">
      <!-- 起点位置只有「算能撑多久」需要：反算是「从现在起 N 天」，与年龄无关 -->
      <div v-if="mode === 'duration'" class="control-card__field">
        <span class="control-card__prefix">当前年龄</span>
        <el-input-number
          v-model="form.current_age" :min="WINDOW_START_AGE" :max="WINDOW_END_AGE"
          controls-position="right" size="default"
        />
      </div>
      <div v-if="mode === 'duration'" class="control-card__field">
        <span class="control-card__prefix">当前周数</span>
        <el-input-number
          v-model="form.current_week" :min="1" :max="52"
          controls-position="right" size="default"
        />
      </div>
      <div class="control-card__field">
        <span class="control-card__prefix">当前现金</span>
        <div class="control-card__input-group">
          <el-input-number
            v-model="form.current_cash" :min="0" :step="10000"
            controls-position="right" size="default"
          />
          <el-button
            link type="primary" size="small"
            :loading="cashLoading" @click="fillFromCashflow"
          >
            带入活期
          </el-button>
        </div>
      </div>
      <div v-if="mode === 'duration'" class="control-card__field">
        <span class="control-card__prefix">每日预算</span>
        <div class="control-card__input-group">
          <el-input-number
            v-model="form.daily_budget" :min="0" :step="10" :precision="2"
            controls-position="right" size="default"
          />
          <span class="control-card__suffix">元/天</span>
          <el-button
            link type="primary" size="small"
            :loading="budgetLoading" @click="fillFromBills"
          >
            按上月日均
          </el-button>
        </div>
      </div>
      <!-- 反算的目标期限：与「每日预算」互斥（一个是给定期限求预算，一个是给预算求期限） -->
      <div v-else class="control-card__field">
        <span class="control-card__prefix">目标时长</span>
        <div class="control-card__input-group">
          <el-input-number
            v-model="form.target_span" :min="1" :max="500" :step="1" :precision="1"
            controls-position="right" size="default"
          />
          <el-select v-model="form.span_unit" style="width: 80px">
            <el-option label="年" value="year" />
            <el-option label="月" value="month" />
            <el-option label="天" value="day" />
          </el-select>
        </div>
      </div>
      <div class="control-card__field">
        <span class="control-card__prefix">月被动收入</span>
        <div class="control-card__input-group">
          <el-input-number
            v-model="form.monthly_income" :min="0" :step="1000" :precision="2"
            controls-position="right" size="default"
          />
          <span class="control-card__suffix">元/月</span>
        </div>
      </div>
      <div class="control-card__field">
        <span class="control-card__prefix">日利息率</span>
        <div class="control-card__input-group">
          <el-input-number
            v-model="form.daily_interest_rate" :min="0" :max="100" :precision="4" :step="0.1"
            controls-position="right" size="default"
          />
          <span class="control-card__suffix">万分之</span>
        </div>
      </div>
      <div class="control-card__hint">
        <template v-if="mode === 'duration'">
          净消耗 = 每日预算 − 月收入折算（÷30.44），填 0 表示纯靠本金；日利率参考货基日万份收益，如 1.5 = 万分之1.5
        </template>
        <template v-else>
          每日可提取 = 这笔本金在目标期限内刚好花完（含日利息复利）；1 月按 30.44 天、1 年按 365.28 天折算。改任一输入即时出结果，不必点按钮
        </template>
      </div>

      <!-- 反算是输入即算，不需要按钮；只保留「算能撑多久」的显式触发 -->
      <el-button
        v-if="mode === 'duration'"
        type="primary"
        class="control-card__calc-btn"
        :loading="loading"
        @click="handleCalculate"
      >
        计算推演
      </el-button>
    </div>

    <!-- 结果区 A：算能撑多久 -->
    <div v-if="mode === 'duration' && result" class="control-card__result">
      <div v-if="netDailyText" class="control-card__result-row control-card__result-row--net">
        <span class="control-card__result-label">净消耗</span>
        <span class="control-card__result-value control-card__result-value--net">{{ netDailyText }}</span>
      </div>
      <div class="control-card__result-row">
        <span class="control-card__result-label">可支撑</span>
        <span
          v-if="reachedWindowEnd"
          class="control-card__result-value control-card__result-value--weeks"
        >
          至 {{ WINDOW_END_AGE }} 岁 <small>窗口内不耗尽</small>
        </span>
        <!-- 未到窗口末端但 support 为空 = 首周即耗尽（现金/预算极端） -->
        <span
          v-else-if="result.support_weeks === null || result.support_weeks === undefined"
          class="control-card__result-value control-card__result-value--age"
        >
          无法覆盖 <small>首周即耗尽</small>
        </span>
        <span v-else class="control-card__result-value control-card__result-value--weeks">
          {{ result.support_weeks }} <small>周</small>
        </span>
      </div>
      <div v-if="supportDurationText" class="control-card__result-convert">
        {{ supportDurationText }}
      </div>
      <div v-if="result.daily_interest_rate" class="control-card__result-row control-card__result-row--interest">
        <span class="control-card__result-label">含日利息</span>
        <span class="control-card__result-value control-card__result-value--interest">
          万分之{{ (result.daily_interest_rate * 10000).toFixed(4) }}
        </span>
      </div>
      <div v-if="result.end_age !== null" class="control-card__result-row">
        <span class="control-card__result-label">预计耗尽</span>
        <span class="control-card__result-value control-card__result-value--age">
          {{ result.end_age }}岁 第{{ result.end_week }}周
        </span>
      </div>
      <div v-if="result.end_age !== null && exhaustDateText" class="control-card__result-convert">
        ≈ {{ exhaustDateText }}
      </div>
      <div v-if="freeGap" class="control-card__result-row control-card__result-row--gap">
        <span class="control-card__result-label">自由缺口</span>
        <span class="control-card__result-value control-card__result-value--gap">
          <template v-if="freeGap.gap > 0">
            还差 ¥{{ fmtInt(freeGap.gap) }}
            <small>· 达 ¥{{ fmtInt(freeGap.required) }} 后利息可覆盖净支出</small>
          </template>
          <template v-else>当前本金已可利息覆盖 ✓</template>
        </span>
      </div>

      <!-- 进度条 -->
      <div class="control-card__progress">
        <div class="control-card__progress-info">
          <span>已度过 {{ passedWeeks }} 周 ({{ basePercent }}%)</span>
          <span v-if="reachedWindowEnd">+ 覆盖至 {{ WINDOW_END_AGE }} 岁</span>
          <span v-else-if="result.support_weeks !== null && result.support_weeks !== undefined">
            + 可支撑 {{ result.support_weeks }} 周
          </span>
          <span v-else>+ 无法覆盖</span>
          <span>= 覆盖至 {{ coveragePercent }}%</span>
        </div>
        <el-progress
          :percentage="coveragePercent"
          :stroke-width="8"
          :color="progressColor"
          :show-text="false"
        />
      </div>
    </div>

    <!-- 结果区 B：算每天可花（输入即算，无按钮） -->
    <div v-else-if="mode === 'budget'" class="control-card__result">
      <template v-if="budgetReady">
        <div class="control-card__result-row">
          <span class="control-card__result-label">每日可提取</span>
          <span class="control-card__result-value control-card__result-value--weeks">
            ¥{{ reverseDaily.toFixed(2) }} <small>元/天</small>
          </span>
        </div>
        <div class="control-card__result-convert">
          ≈ ¥{{ fmtInt(reverseMonthly) }}/月 · ¥{{ fmtInt(reverseYearly) }}/年
        </div>
        <div v-if="incomePerDay > 0" class="control-card__result-convert">
          含被动收入 ¥{{ incomePerDay.toFixed(2) }}/天 → 实际可花 ¥{{ reverseDailyWithIncome.toFixed(2) }}/天
        </div>
        <div v-if="isPerpetual" class="control-card__result-convert">
          已接近永续：利息可覆盖支出，本金不再减少
        </div>
      </template>
      <div v-else class="control-card__empty">
        输入「当前现金」与「目标时长」后即时显示每日可花金额
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="control-card__empty">
      {{ mode === 'duration'
        ? '输入年龄和预算后点击「计算推演」查看现金流覆盖情况'
        : '输入本金与目标时长，实时算出每天能花多少' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, ref, watch, onMounted } from 'vue'
import type { CoverageResult, BudgetResult } from '../types/wealthTypes'
import { getCurrentAgeWeek, getCashFlowOverview, getMonthlySummary, calculateBudget } from '../api/wealthApi'

const emit = defineEmits<{
  calculate: [params: { current_age: number; current_week: number; current_cash: number; daily_budget: number; daily_interest_rate: number }]
  reset: []
}>()

const props = defineProps<{
  loading: boolean
  result: CoverageResult | null
  defaultAge?: number
  defaultWeek?: number
}>()

type SpanUnit = 'year' | 'month' | 'day'
type Mode = 'duration' | 'budget'

/**
 * 推演模式 —— 同一套现金流假设的**正反两面**：
 *  - duration（默认）：给每日预算 → 算能撑多久。点按钮触发，后端会落推演历史。
 *  - budget：给本金 + 目标期限 → 算每天能花多少。输入即算，**后端零写库**。
 * 两者共用「当前现金 / 月被动收入 / 日利息率」三项输入。
 */
const mode = ref<Mode>('duration')

const form = reactive({
  current_age: props.defaultAge ?? 36,
  current_week: props.defaultWeek ?? 18,
  current_cash: 100000,
  daily_budget: 100,
  monthly_income: 0,
  daily_interest_rate: 0,
  // ── 反算专用 ──
  target_span: 10,
  span_unit: 'year' as SpanUnit,
})

const cashLoading = ref(false)
const budgetLoading = ref(false)

// ── 真实数据带入 ──
/** 当前现金 ← 资产盘点最新快照的流动资金合计 */
async function fillFromCashflow() {
  cashLoading.value = true
  try {
    const res = await getCashFlowOverview()
    const total = res.data?.summary?.flow_total
    if (typeof total === 'number' && total > 0) form.current_cash = Math.round(total)
  } catch {
    // 接口不可用时保持手动输入
  } finally {
    cashLoading.value = false
  }
}

/** 每日预算 ← 上月账单日均支出 */
async function fillFromBills() {
  budgetLoading.value = true
  try {
    const now = new Date()
    let year = now.getFullYear()
    let month = now.getMonth() // 0-based，自然就是上月
    if (month === 0) { year -= 1; month = 12 }
    const res = await getMonthlySummary({ year, month })
    const avg = res.data?.avg_daily_expense
    if (typeof avg === 'number' && avg > 0) form.daily_budget = Math.round(avg * 100) / 100
  } catch {
    // 接口不可用时保持手动输入
  } finally {
    budgetLoading.value = false
  }
}

// ── 时间口径：1 月 = 30.44 天（收入折算与反算的天数换算共用同一把尺子）──
const DAYS_PER_MONTH = 30.44
const DAYS_PER_YEAR = DAYS_PER_MONTH * 12 // 365.28

// ── 收入侧折算 ──
/** 净日消耗 = 每日预算 − 月被动收入折算（一月 = 30.44 天） */
const netDaily = computed(() => {
  const incomeDaily = (form.monthly_income || 0) / DAYS_PER_MONTH
  return Math.max(0, (form.daily_budget || 0) - incomeDaily)
})

const netDailyText = computed(() => {
  if (!(form.monthly_income > 0) || !(form.daily_budget > 0)) return ''
  const offset = (form.daily_budget || 0) - netDaily.value
  return `${netDaily.value.toFixed(1)} 元/天（预算 ${form.daily_budget} − 收入折算 ${offset.toFixed(1)}）`
})

// ─────────────────────────────────────────────────────────────
// 反算：本金 + 目标期限 → 每日可提取额
// 后端 /wealth/calculate_budget/ 与正算互为反函数，共用同一套现金流假设
// ─────────────────────────────────────────────────────────────

const SPAN_UNIT_DAYS: Record<SpanUnit, number> = {
  year: DAYS_PER_YEAR,
  month: DAYS_PER_MONTH,
  day: 1,
}

const targetDays = computed(() => (form.target_span || 0) * SPAN_UNIT_DAYS[form.span_unit])

const budgetResult = ref<BudgetResult | null>(null)
let budgetSeq = 0 // 竞态守卫：只接纳最新一次请求的结果
let budgetTimer: ReturnType<typeof setTimeout> | null = null

const reverseDaily = computed(() => budgetResult.value?.daily_budget ?? 0)
/** 有无可用结果：本金与期限都须为正 */
const budgetReady = computed(() => budgetResult.value !== null && reverseDaily.value > 0)
/** 月被动收入折算到每天（与上方 netDaily 同一口径） */
const incomePerDay = computed(() => (form.monthly_income || 0) / DAYS_PER_MONTH)
/** 叠加被动收入后每天真正能花的钱 */
const reverseDailyWithIncome = computed(() => reverseDaily.value + incomePerDay.value)
const reverseMonthly = computed(() => reverseDaily.value * DAYS_PER_MONTH)
const reverseYearly = computed(() => reverseDaily.value * DAYS_PER_YEAR)

/**
 * 已逼近永续上限：本金日利息 ≈ 提取额，本金不再减少 → 期限再拉长也不会多出多少。
 * 上界为 cash·r/(1+r)（与后端 calculate_daily_budget 的收敛值同源）。
 */
const isPerpetual = computed(() => {
  const cash = form.current_cash || 0
  const rate = (form.daily_interest_rate || 0) / 10000
  if (cash <= 0 || rate <= 0 || reverseDaily.value <= 0) return false
  return reverseDaily.value >= (cash * rate) / (1 + rate) * 0.999
})

async function runReverse() {
  const cash = form.current_cash || 0
  const days = targetDays.value
  if (cash <= 0 || days <= 0) {
    budgetResult.value = null
    return
  }
  const seq = ++budgetSeq
  budgetLoading.value = true
  try {
    const res = await calculateBudget({
      current_cash: cash,
      target_days: Math.round(days * 100) / 100,
      daily_interest_rate: parseFloat(((form.daily_interest_rate || 0) / 10000).toFixed(8)),
    })
    if (seq !== budgetSeq) return // 已有更新的请求发出，丢弃这次的过期结果
    budgetResult.value = res.data
  } catch {
    if (seq === budgetSeq) budgetResult.value = null
  } finally {
    if (seq === budgetSeq) budgetLoading.value = false
  }
}

/**
 * 输入即算（防抖 250ms）—— 反算是纯试算、零副作用，做成滑块式试算体验：
 * 改「撑几年」时数字立刻跟着动。仅在 budget 模式下触发，不打扰正算流程。
 */
watch(
  () => [mode.value, form.current_cash, form.target_span, form.span_unit, form.daily_interest_rate],
  () => {
    if (budgetTimer) clearTimeout(budgetTimer)
    if (mode.value !== 'budget') return
    budgetTimer = setTimeout(runReverse, 250)
  },
  { immediate: true },
)

// ── 自由缺口：本金达 净日消耗 ÷ 日利率 后，利息即可覆盖支出（永不耗尽） ──
const freeGap = computed(() => {
  const rate = Number(props.result?.daily_interest_rate) || 0
  if (rate <= 0 || netDaily.value <= 0) return null
  const required = netDaily.value / rate
  const gap = Math.max(0, required - (form.current_cash || 0))
  return { required, gap }
})

function fmtInt(v: number): string {
  return Math.round(v).toLocaleString('zh-CN')
}

// ── 耗尽绝对日期 ──
const exhaustDateText = computed(() => {
  const w = props.result?.support_weeks
  if (!w || w <= 0) return ''
  const d = new Date(Date.now() + w * 7 * 86400000)
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月`
})

// 动态加载当前年龄和周数
onMounted(async () => {
  try {
    const res = await getCurrentAgeWeek()
    form.current_age = res.data.current_age
    form.current_week = res.data.current_week
  } catch {
    // 接口不可用时保持默认值
  }
})

/**
 * 计量窗口（19–60 岁）—— 与后端 `apps/wealth/constants.py` 的 WINDOW_* 保持一致。
 * 推演上限、进度基数、已度过周数都按此窗口算；窗口外的年份不再关心。
 */
const WINDOW_START_AGE = 19
const WINDOW_END_AGE = 60
const WINDOW_WEEKS = 2184 // 42 年 × 52 周

/**
 * 窗口内**已度过**周数。`week` 是当前所处周（进行中），故减 1 只数已过的完整周，
 * 与后端 `summary.lived_weeks`（同样的已度过口径，当前 661 周）对齐，避免同页两个数字打架。
 */
const passedWeeks = computed(() => {
  const age = form.current_age || WINDOW_START_AGE
  const week = form.current_week || 1
  return Math.max(0, (age - WINDOW_START_AGE) * 52 + (week - 1))
})

const basePercent = computed(() => {
  return Math.round(passedWeeks.value / WINDOW_WEEKS * 100)
})

/** 跑满窗口仍未耗尽（也含「无需净消耗」）→ 视为覆盖至 60 岁 */
const reachedWindowEnd = computed(() => props.result?.reached_window_end === true)

const coveragePercent = computed(() => {
  const r = props.result
  if (!r) return 0
  if (r.support_weeks === null || r.support_weeks === undefined) {
    // null 有两种情形：无需消耗（跑满窗口）→ 100%；首周即耗尽 → 0%
    return reachedWindowEnd.value ? 100 : 0
  }
  return Math.min(100, Math.round((passedWeeks.value + r.support_weeks) / WINDOW_WEEKS * 100))
})

// 「可支撑」周数换算为月 / 年（一年 = 52.14 周，一月 = 4.345 周）
const supportDurationText = computed(() => {
  const w = props.result?.support_weeks
  // 已覆盖到窗口末端时不再换算年数（那个数字只会是「窗口内剩余周数」，易被误读为"只能撑这么久"）
  if (!w || w <= 0 || reachedWindowEnd.value) return ''
  const years = w / 52.14
  const months = w / 4.345
  return `≈ ${months.toFixed(1)} 个月 · ${years.toFixed(1)} 年`
})

const progressColor = computed(() => {
  const pct = coveragePercent.value
  if (pct >= 50) return '#67c23a'
  if (pct >= 20) return '#e6a23c'
  return '#f56c6c'
})

function handleCalculate() {
  emit('calculate', {
    current_age: form.current_age || 36,
    current_week: form.current_week || 1,
    current_cash: form.current_cash || 0,
    daily_budget: Math.round(netDaily.value * 100) / 100,
    daily_interest_rate: parseFloat(((form.daily_interest_rate || 0) / 10000).toFixed(8)),
  })
}
</script>

<style scoped lang="scss">
.control-card {
  padding: 20px;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }

  &__title {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__form {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 24px;
  }

  &__field {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 12px;
    min-width: 0;
  }

  &__input-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;

    :deep(.el-input-number) {
      flex: 1;
      min-width: 0;
    }
  }

  &__prefix {
    font-size: 14px;
    color: var(--el-text-color-regular);
    white-space: nowrap;
    min-width: 72px;
  }

  &__suffix {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    white-space: nowrap;
  }

  &__hint {
    grid-column: 1 / -1;
    font-size: 11px;
    color: var(--el-text-color-placeholder);
    line-height: 1.4;
  }

  &__calc-btn {
    grid-column: 1 / -1;
    width: 100%;
    margin-top: 4px;
    font-size: 14px;
  }

  &__result {
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--el-border-color-light);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__result-convert {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    text-align: right;
    margin-top: -8px;
  }

  &__result-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;

    &--interest {
      .control-card__result-value {
        font-size: 14px;
        font-weight: 500;
        color: var(--el-color-info);
      }
    }

    &--net {
      .control-card__result-value {
        font-size: 14px;
        font-weight: 500;
        color: var(--el-color-info);
      }
    }

    &--gap {
      padding-top: 10px;
      border-top: 1px dashed var(--el-border-color-lighter);

      .control-card__result-value {
        font-size: 16px;
        font-weight: 600;
        color: #e6a23c;

        small {
          font-size: 12px;
          font-weight: 400;
          color: var(--el-text-color-secondary);
        }
      }
    }
  }

  &__result-label {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }

  &__result-value {
    font-size: 20px;
    font-weight: 700;

    small {
      font-size: 13px;
      font-weight: 400;
      color: var(--el-text-color-secondary);
    }

    &--weeks {
      color: #67c23a;
    }

    &--age {
      font-size: 16px;
      color: #f56c6c;
    }

    &--never {
      font-size: 16px;
      color: #67c23a;
    }
  }

  &__progress {
    margin-top: 4px;

    &-info {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: var(--el-text-color-secondary);
      margin-bottom: 4px;
    }
  }

  &__empty {
    margin-top: 16px;
    font-size: 13px;
    color: var(--el-text-color-placeholder);
    text-align: center;
    line-height: 1.6;
    padding: 12px 0;
  }
}

@media (max-width: 768px) {
  .control-card {
    &__form {
      grid-template-columns: 1fr;
    }
  }
}
</style>
