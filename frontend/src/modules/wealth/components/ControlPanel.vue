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
        <el-input-number
          v-model="form.current_cash" :min="0" :step="10000"
          controls-position="right" size="default"
        />
      </div>
      <div class="control-card__field">
        <span class="control-card__prefix">每日预算</span>
        <el-input-number
          v-model="form.daily_budget" :min="0" :step="10" :precision="2"
          controls-position="right" size="default"
        />
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
      <div class="control-card__result-row">
        <span class="control-card__result-label">可支撑</span>
        <span class="control-card__result-value control-card__result-value--weeks">
          {{ result.support_weeks === Infinity ? '∞' : result.support_weeks }}
          <small>周</small>
        </span>
      </div>
      <div v-if="result.end_age !== null" class="control-card__result-row">
        <span class="control-card__result-label">预计耗尽</span>
        <span class="control-card__result-value control-card__result-value--age">
          {{ result.end_age }}岁 第{{ result.end_week }}周
        </span>
      </div>
      <div v-else class="control-card__result-row">
        <span class="control-card__result-label">预计耗尽</span>
        <span class="control-card__result-value control-card__result-value--never">永不耗尽</span>
      </div>

      <!-- 进度条 -->
      <div class="control-card__progress">
        <div class="control-card__progress-info">
          <span>覆盖进度</span>
          <span>{{ coveragePercent }}%</span>
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
import { reactive, computed, onMounted } from 'vue'
import type { CoverageResult } from '../types/wealthTypes'
import { getCurrentAgeWeek } from '../api/wealthApi'

const emit = defineEmits<{
  calculate: [params: { current_age: number; current_week: number; current_cash: number; daily_budget: number }]
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

const coveragePercent = computed(() => {
  if (!props.result || props.result.support_weeks === Infinity) return 0
  // 总周数按 61年 × 52周 = 3172 计算
  const total = 3172
  const covered = props.result.support_weeks
  return Math.min(Math.round((covered / total) * 100), 100)
})

const progressColor = computed(() => {
  const pct = coveragePercent.value
  if (pct >= 50) return '#67c23a'
  if (pct >= 20) return '#e6a23c'
  return '#f56c6c'
})

function handleCalculate() {
  emit('calculate', {
    current_age: form.current_age,
    current_week: form.current_week,
    current_cash: form.current_cash,
    daily_budget: form.daily_budget,
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
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  &__field {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  &__prefix {
    font-size: 14px;
    color: var(--el-text-color-regular);
    white-space: nowrap;
    min-width: 72px;
  }

  &__calc-btn {
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

  &__result-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
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
</style>
