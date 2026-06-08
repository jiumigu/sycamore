<template>
  <div class="heatmap">
    <!-- 列头：周数 -->
    <div class="heatmap__header">
      <div class="heatmap__corner" />
      <div
        v-for="week in 52"
        :key="'h' + week"
        class="heatmap__col-header"
        :style="{ width: cellSize + 'px' }"
      >
        <span v-if="week % 5 === 1 || week === 52">{{ week }}</span>
      </div>
    </div>

    <!-- 行：年龄 × 周 -->
    <div class="heatmap__body">
      <template v-for="age in 61" :key="'r' + age">
        <div class="heatmap__row-label">
          {{ START_AGE + age - 1 }}岁
        </div>
        <div
          v-for="week in 52"
          :key="'c' + age + '-' + week"
          class="heatmap__cell"
          :class="cellClasses(globalIndex(age - 1, week))"
          :style="{
            width: cellSize + 'px',
            height: cellSize + 'px',
            backgroundColor: cellColor(globalIndex(age - 1, week)),
          }"
          @click="handleClick(globalIndex(age - 1, week))"
          @mouseenter="handleHover(globalIndex(age - 1, week))"
          @mouseleave="handleLeave"
        />
      </template>
    </div>

    <!-- 悬浮提示 -->
    <div
      v-if="tooltip.visible"
      class="heatmap__tooltip"
      :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
    >
      <div class="heatmap__tooltip-title">
        ￥{{ tooltip.data?.age_year }}岁 · 第{{ tooltip.data?.week_number }}周
      </div>
      <div class="heatmap__tooltip-row">
        <span>收入</span><span class="heatmap__tooltip-income">+￥{{ fmt(tooltip.data?.income) }}</span>
      </div>
      <div class="heatmap__tooltip-row">
        <span>支出</span><span class="heatmap__tooltip-expense">-￥{{ fmt(tooltip.data?.expense) }}</span>
      </div>
      <div class="heatmap__tooltip-row">
        <span>净结余</span>
        <span :class="netColorClass(tooltip.data?.net)">￥{{ fmt(tooltip.data?.net) }}</span>
      </div>
      <div v-if="isCovered(tooltip.index ?? -1)" class="heatmap__tooltip-coverage">
        ✅ 现金流覆盖
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import { formatAmount } from '@/shared/utils/format'
import { useWealthStore } from '../stores/wealthStore'
import type { WeekCalendarEntry } from '../types/wealthTypes'

const props = withDefaults(defineProps<{
  cellSize?: number
}>(), {
  cellSize: 14,
})

const emit = defineEmits<{
  select: [weekIndex: number]
}>()

const store = useWealthStore()

const START_AGE = 18

function globalIndex(ageOffset: number, week: number): number {
  return ageOffset * 52 + (week - 1)
}

/** 获取周历条目 */
function getEntry(index: number): WeekCalendarEntry | undefined {
  return store.weekData[index]
}

/** 是否已度过 */
function isLived(index: number): boolean {
  return store.weekData[index]?.is_lived ?? false
}

/** 是否在现金流覆盖范围内 */
function isCovered(index: number): boolean {
  return store.coverageSet.has(index)
}

/** 单元格颜色 */
function cellColor(index: number): string {
  const entry = getEntry(index)
  if (!entry) return '#f5f5f5'
  if (!entry.is_lived) return '#f5f5f5'

  const colors: Record<string, string> = {
    surplus_high: '#1b5e20',
    surplus_mid: '#388e3c',
    surplus_low: '#81c784',
    zero: '#9e9e9e',
    deficit_low: '#e57373',
    deficit_mid: '#d32f2f',
    deficit_high: '#b71c1c',
  }
  return colors[entry.net_level] ?? '#f5f5f5'
}

/** 单元格 CSS 类 */
function cellClasses(index: number): Record<string, boolean> {
  const covered = isCovered(index)
  return {
    'heatmap__cell--selected': store.selectedWeekIndex === index,
    'heatmap__cell--covered': covered,
    'heatmap__cell--unlived': !isLived(index) || !getEntry(index),
  }
}

/** 净结余颜色类 */
function netColorClass(net: number | undefined): string {
  if (net === undefined) return ''
  return net >= 0 ? 'heatmap__tooltip-positive' : 'heatmap__tooltip-negative'
}

/** 格式化金额 */
function fmt(val: number | undefined): string {
  if (val === undefined) return '0.00'
  return formatAmount(val)
}

/** 点击选中 */
function handleClick(index: number) {
  emit('select', index)
}

/** 悬浮提示 */
const tooltip = reactive<{
  visible: boolean
  x: number
  y: number
  index: number | null
  data: WeekCalendarEntry | null
}>({
  visible: false, x: 0, y: 0, index: null, data: null,
})

function handleHover(index: number) {
  const entry = getEntry(index)
  tooltip.visible = true
  tooltip.index = index
  tooltip.data = entry ?? null
}

function handleLeave() {
  tooltip.visible = false
}
</script>

<style scoped lang="scss">
.heatmap {
  position: relative;
  display: inline-block;
  font-size: 10px;
  user-select: none;

  &__header {
    display: flex;
    margin-left: 44px;
    margin-bottom: 2px;
  }

  &__corner {
    width: 44px;
    flex-shrink: 0;
  }

  &__col-header {
    flex-shrink: 0;
    text-align: center;
    color: #999;
    font-size: 9px;
    line-height: 16px;
  }

  &__body {
    display: grid;
    grid-template-columns: 44px repeat(52, auto);
    gap: 1px;
  }

  &__row-label {
    font-size: 10px;
    color: #999;
    line-height: 14px;
    text-align: right;
    padding-right: 4px;
    white-space: nowrap;
  }

  &__cell {
    border-radius: 2px;
    cursor: pointer;
    transition: opacity 0.15s;
    position: relative;

    &:hover {
      opacity: 0.8;
      transform: scale(1.3);
      z-index: 1;
    }

    &--selected {
      outline: 2px solid #ff9800;
      outline-offset: -1px;
      z-index: 2;
    }

    &--covered {
      box-shadow: inset 0 0 0 1.5px rgba(33, 150, 243, 0.7);
    }

    &--unlived {
      background-color: #f5f5f5 !important;
    }
  }

  /* 悬浮提示 */
  &__tooltip {
    position: fixed;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.85);
    color: #fff;
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.6;
    pointer-events: none;
    white-space: nowrap;
    transform: translate(8px, -50%);
    min-width: 140px;
  }

  &__tooltip-title {
    font-weight: 600;
    margin-bottom: 4px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    padding-bottom: 2px;
  }

  &__tooltip-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }

  &__tooltip-income { color: #81c784; }
  &__tooltip-expense { color: #e57373; }
  &__tooltip-positive { color: #81c784; font-weight: 600; }
  &__tooltip-negative { color: #e57373; font-weight: 600; }

  &__tooltip-coverage {
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
    font-size: 11px;
    color: #64b5f6;
  }
}
</style>
