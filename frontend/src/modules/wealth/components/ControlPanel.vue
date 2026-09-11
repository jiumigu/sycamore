<template>
  <div class="control-card">
    <div class="control-card__title">现金流推演</div>

    <!-- 输入区 -->
    <div class="control-card__form">
      <div class="control-card__field">
        <span class="control-card__prefix">当前年龄</span>
        <el-input-number
          v-model="form.current_age" :min="18" :max="78"
          controls-position="right" size="default"
        />
      </div>
      <div class="control-card__field">
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
      <div class="control-card__field">
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
        净消耗 = 每日预算 − 月收入折算（÷30.44），填 0 表示纯靠本金；日利率参考货基日万份收益，如 1.5 = 万分之1.5
      </div>

      <el-button
        type="primary"
        class="control-card__calc-btn"
        :loading="loading"
        @click="handleCalculate"
      >
        计算推演
      </el-button>
    </div>

    <!-- 结果区 -->
    <div v-if="result" class="control-card__result">
      <div v-if="netDailyText" class="control-card__result-row control-card__result-row--net">
        <span class="control-card__result-label">净消耗</span>
        <span class="control-card__result-value control-card__result-value--net">{{ netDailyText }}</span>
      </div>
      <div class="control-card__result-row">
        <span class="control-card__result-label">可支撑</span>
        <span class="control-card__result-value control-card__result-value--weeks">
          {{ result.support_weeks === null || result.support_weeks === undefined ? '∞' : result.support_weeks }}
          <small>周</small>
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
      <div v-if="result.end_age === null" class="control-card__result-row">
        <span class="control-card__result-label">预计耗尽</span>
        <span class="control-card__result-value control-card__result-value--never">永不耗尽</span>
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
          <span v-if="result.support_weeks !== null">+ 可支撑 {{ result.support_weeks }} 周</span>
          <span v-else>+ 永不耗尽</span>
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

    <!-- 空状态 -->
    <div v-else class="control-card__empty">
      输入年龄和预算后点击「计算推演」查看现金流覆盖情况
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, ref, onMounted } from 'vue'
import type { CoverageResult } from '../types/wealthTypes'
import { getCurrentAgeWeek, getCashFlowOverview, getMonthlySummary } from '../api/wealthApi'

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

const form = reactive({
  current_age: props.defaultAge ?? 36,
  current_week: props.defaultWeek ?? 18,
  current_cash: 100000,
  daily_budget: 100,
  monthly_income: 0,
  daily_interest_rate: 0,
})

const cashLoading = ref(false)
const budgetLoading = ref(false)

// ── 真实数据带入 ──
/** 当前现金 ← 现金盘点最新快照的活期总额 */
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

// ── 收入侧折算 ──
/** 净日消耗 = 每日预算 − 月被动收入折算（一月 = 30.44 天） */
const netDaily = computed(() => {
  const incomeDaily = (form.monthly_income || 0) / 30.44
  return Math.max(0, (form.daily_budget || 0) - incomeDaily)
})

const netDailyText = computed(() => {
  if (!(form.monthly_income > 0) || !(form.daily_budget > 0)) return ''
  const offset = (form.daily_budget || 0) - netDaily.value
  return `${netDaily.value.toFixed(1)} 元/天（预算 ${form.daily_budget} − 收入折算 ${offset.toFixed(1)}）`
})

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

const totalWeeks = 3172

const passedWeeks = computed(() => {
  const age = form.current_age || 31
  const week = form.current_week || 1
  return (age - 18) * 52 + week
})

const basePercent = computed(() => {
  return Math.round(passedWeeks.value / totalWeeks * 100)
})

const coveragePercent = computed(() => {
  if (!props.result) return 0
  if (props.result.support_weeks === null || props.result.support_weeks === undefined) return 100
  const covered = passedWeeks.value + props.result.support_weeks
  return Math.min(100, Math.round(covered / totalWeeks * 100))
})

// 「可支撑」周数换算为月 / 年（一年 = 52.14 周，一月 = 4.345 周）
const supportDurationText = computed(() => {
  const w = props.result?.support_weeks
  if (!w || w <= 0) return ''
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

  &__title {
    font-size: 16px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 16px;
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
