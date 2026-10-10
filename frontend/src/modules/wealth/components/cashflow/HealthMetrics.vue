<template>
  <div class="health-metrics">
    <div class="health-metrics__title">资产健康指标</div>
    <div v-if="!metrics" class="health-metrics__empty">暂无数据</div>
    <div v-else class="health-metrics__items">
      <div class="health-metrics__item" v-for="item in items" :key="item.key">
        <div class="health-metrics__item-top">
          <span class="health-metrics__item-label">
            {{ item.label }}
            <!-- 口径气泡：公式 / 要点 / 档位全部来自后端，前端一句文案都不写 -->
            <MetricTooltip :meta="metaOf(item.metaKey)">
              <template v-if="item.key === 'emergency' && pertLines.length">
                <div class="metric-tooltip__pert">
                  <div class="metric-tooltip__pert-title">本次取值</div>
                  <div
                    v-for="line in pertLines"
                    :key="line.label"
                    class="metric-tooltip__pert-row"
                  >
                    <span>{{ line.label }}</span>
                    <span>{{ line.value }}</span>
                  </div>
                  <div v-if="pertSample" class="metric-tooltip__pert-sample">
                    {{ pertSample }}
                  </div>
                </div>
              </template>
            </MetricTooltip>
            <span v-if="item.levelLabel" class="health-metrics__item-level">
              {{ item.levelLabel }}
            </span>
          </span>
          <span class="health-metrics__item-value" :class="item.status">
            {{ item.display }}
          </span>
        </div>
        <PercentageBar
          v-if="item.pct !== undefined && item.pct !== null"
          :percentage="item.pct"
          :color="item.color"
        />
        <div v-if="item.hint" class="health-metrics__item-hint">{{ item.hint }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PercentageBar from '../common/PercentageBar.vue'
import MetricTooltip from '../common/MetricTooltip.vue'
import { formatSignedAmount } from '@/shared/utils/format'
import { levelClass, levelColor } from '../../utils/ratioLevel'
import type { HealthMetrics, RatioMeta } from '../../types/wealthTypes'

const props = defineProps<{
  metrics: HealthMetrics | null
  /**
   * 口径元信息（key → 元信息），来自 /wealth/ratios/meta/。
   *
   * 传空对象时**不显示** ⓘ —— 宁可没有提示，也不要一个只有标题的空气泡。
   */
  ratioMeta?: Record<string, RatioMeta>
}>()

/**
 * 本卡片只做两件事：**上色**与**排版**。
 *
 * 🔴 一个阈值数字都不许出现。四项指标的档位（`*_level` / `*_level_label`）
 *   全部由后端按 `constants.RATIO_BANDS` 判好下发。
 *   这里曾写过 `months >= target / 2`、`ratio > 30 ? 'warn' : ...` ——
 *   那等于阈值仍由前端定义：改后端常量不会改变界面结论。
 *   要调档位请去 `backend/apps/wealth/constants.py`，不要回到这个文件里加判断。
 *
 * 色表也不在这里：与比率面板共用 `utils/ratioLevel.ts`，
 * 否则同一个 danger 会在这张卡和比率卡上不是一个红。
 */

const items = computed(() => {
  if (!props.metrics) return []
  const m = props.metrics
  const months = m.emergency_fund_months
  const gap = m.emergency_gap
  const target = m.emergency_months_target

  return [
    {
      key: 'emergency',
      // 与后端 constants.RATIO_BANDS 的键一致 —— 口径说明靠它取
      metaKey: 'emergency_months',
      label: '应急金月数',
      display: months === null ? '数据不足' : `${months} 个月`,
      pct: m.emergency_months_pct,
      color: levelColor(m.emergency_months_level),
      status: levelClass(m.emergency_months_level),
      levelLabel: m.emergency_months_level_label,
      hint: months === null
        ? (m.expense_estimate?.reason
            ?? `需近 ${m.monthly_expense_window} 个月支出记录`)
        : (gap && gap > 0
            ? `目标 ${target} 个月，缺口 ${formatSignedAmount(gap, 0)}`
            : `已达目标 ${target} 个月`),
    },
    {
      key: 'liquidity',
      metaKey: 'liquidity_ratio',
      label: '活期占比',
      display: m.liquidity_ratio + '%',
      pct: m.liquidity_ratio,
      color: levelColor(m.liquidity_ratio_level),
      status: levelClass(m.liquidity_ratio_level),
      levelLabel: m.liquidity_ratio_level_label,
    },
    {
      key: 'debt',
      metaKey: 'debt_ratio',
      label: '负债率',
      display: m.debt_ratio + '%',
      pct: m.debt_ratio,
      color: levelColor(m.debt_ratio_level),
      status: levelClass(m.debt_ratio_level),
      levelLabel: m.debt_ratio_level_label,
    },
    {
      key: 'pf',
      metaKey: 'provident_fund_ratio',
      label: '公积金占比',
      display: m.provident_fund_ratio + '%',
      pct: m.provident_fund_ratio,
      color: levelColor(m.provident_fund_ratio_level),
      status: levelClass(m.provident_fund_ratio_level),
      levelLabel: m.provident_fund_ratio_level_label,
    },
  ]
})

/** 找不到口径说明时返回 null —— 由气泡组件决定「不渲染」，而不是渲染空气泡 */
function metaOf(metaKey: string): RatioMeta | null {
  return props.ratioMeta?.[metaKey] ?? null
}

/**
 * 应急金分母的**本次实际取值**（O / M / P / E）。
 *
 * 气泡里的公式回答「怎么算」，这一块回答「这次算出来是什么」——
 * 两件事缺一不可：只有公式时无法判断这批样本厚不厚，
 * 只有数字时无法判断它稳不稳。
 */
const pertLines = computed(() => {
  const est = props.metrics?.expense_estimate
  if (!est || est.value === null) return []
  return [
    { label: 'O 最小月', value: formatSignedAmount(est.optimistic ?? 0, 0) },
    { label: 'M 中位数', value: formatSignedAmount(est.likely ?? 0, 0) },
    { label: 'P 最大月', value: formatSignedAmount(est.pessimistic ?? 0, 0) },
    { label: 'E = (O+4M+P)÷6', value: formatSignedAmount(est.value, 0) },
  ]
})

/** 样本厚薄：12 个月窗口里实际有几个月有支出记录 */
const pertSample = computed(() => {
  const est = props.metrics?.expense_estimate
  if (!est) return ''
  return `样本 ${est.months_with_records} / ${est.window_months} 个月`
})
</script>

<style scoped>
.health-metrics__title {
  font-size: 15px; font-weight: 600; margin-bottom: 14px;
}
.health-metrics__items {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.health-metrics__item-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 13px;
}
.health-metrics__item-label {
  color: var(--el-text-color-regular);
}
/* 档位中文标签 —— 由后端下发（如「闲置偏多」），前端不自己起名 */
.health-metrics__item-level {
  margin-left: 6px;
  padding: 0 5px;
  font-size: 11px;
  border-radius: 3px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
}
.health-metrics__item-value { font-weight: 600; }
.health-metrics__item-value.good { color: #52c41a; }
.health-metrics__item-value.warn { color: #e6a23c; }
.health-metrics__item-value.danger { color: #f5222d; }
.health-metrics__item-value.normal { color: var(--el-text-color-primary); }
.health-metrics__item-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.health-metrics__empty {
  padding: 24px; text-align: center; color: var(--el-text-color-placeholder);
}

/* 气泡内「本次取值」块 —— 随 slot 一起 teleport，scoped 属性跟着元素走，故仍生效 */
.metric-tooltip__pert {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.metric-tooltip__pert-title {
  margin-bottom: 4px;
  color: var(--el-text-color-secondary);
}
.metric-tooltip__pert-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--el-text-color-regular);
}
.metric-tooltip__pert-sample {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
}
</style>
