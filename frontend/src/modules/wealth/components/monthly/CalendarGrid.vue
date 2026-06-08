<template>
  <div class="calendar-grid">
    <!-- 星期栏 -->
    <div class="calendar-grid__weekdays">
      <div class="calendar-grid__weekday">一</div>
      <div class="calendar-grid__weekday">二</div>
      <div class="calendar-grid__weekday">三</div>
      <div class="calendar-grid__weekday">四</div>
      <div class="calendar-grid__weekday">五</div>
      <div class="calendar-grid__weekday">六</div>
      <div class="calendar-grid__weekday">日</div>
    </div>

    <!-- 日期网格 -->
    <div class="calendar-grid__days">
      <!-- 前月占位 -->
      <div
        v-for="n in leadingBlank"
        :key="'lead-' + n"
        class="calendar-grid__cell calendar-grid__cell--other-month"
      />

      <!-- 当月日期 -->
      <div
        v-for="day in days"
        :key="'day-' + day.day"
        class="calendar-grid__cell"
        :class="getDayClasses(day)"
        :style="{ backgroundColor: getDayBg(day) }"
        @click="handleDayClick(day)"
      >
        <!-- 第一层：公历日期 -->
        <div class="calendar-grid__date-row">
          <span
            class="calendar-grid__day-num"
            :class="{ 'calendar-grid__day-num--today': isToday(day.date) }"
          >
            {{ day.day }}
          </span>
          <span v-if="isToday(day.date)" class="calendar-grid__today-badge">今</span>
          <span v-if="isWeekStart(day)" class="calendar-grid__week-start">●</span>
        </div>

        <!-- 第二层：收支汇总 -->
        <div v-if="day.income > 0 || day.expense > 0" class="calendar-grid__summary">
          <span
            class="calendar-grid__summary-text"
            :class="day.net >= 0 ? 'text-income' : 'text-expense'"
          >
            {{ formatDaySummary(day.income, day.expense, privacyStore.privacyMode) }}
          </span>
        </div>

        <!-- 第三层：农历/节日 -->
        <div class="calendar-grid__lunar">
          {{ getLunarDisplay(day.date) }}
        </div>
      </div>

      <!-- 后月占位 -->
      <div
        v-for="n in trailingBlank"
        :key="'trail-' + n"
        class="calendar-grid__cell calendar-grid__cell--other-month"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import type { MonthlyDay } from '../../types/wealthTypes'
import {
  getLunarInfo, isSameDay, isWeekStart as checkWeekStart,
  COLOR_BG_MAP, formatDate,
} from '../common/LunarUtil'

const privacyStore = usePrivacyStore()

function formatDaySummary(income: number, expense: number, privacy: boolean): string {
  let text = ''
  if (income > 0) {
    text += privacy ? '+*,***' : `+${Math.round(income)}`
  }
  if (expense > 0) {
    text += `/-${Math.round(expense)}`
  }
  return text
}

const props = defineProps<{
  days: MonthlyDay[]
  year: number
  month: number
  selectedDate: string | null
}>()

const emit = defineEmits<{
  select: [date: string]
}>()

const today = new Date()

/** 当月1号是周几（0=周日） */
const firstDayOfWeek = computed(() => {
  const d = new Date(props.year, props.month - 1, 1)
  return d.getDay()
})

/** 前月占位格数（周一为一周第一天） */
const leadingBlank = computed(() => {
  const fd = firstDayOfWeek.value
  return fd === 0 ? 6 : fd - 1
})

/** 后月占位 */
const trailingBlank = computed(() => {
  const total = leadingBlank.value + props.days.length
  const remainder = total % 7
  return remainder === 0 ? 0 : 7 - remainder
})

function isToday(dateStr: string): boolean {
  const [y, m, d] = dateStr.split('-').map(Number)
  return today.getFullYear() === y && today.getMonth() + 1 === m && today.getDate() === d
}

function isWeekStart(day: MonthlyDay): boolean {
  return checkWeekStart(props.year, props.month, day.day)
}

function getDayBg(day: MonthlyDay): string {
  if (day.income === 0 && day.expense === 0) return '#fafafa'
  return COLOR_BG_MAP[day.color_level] || '#fafafa'
}

function getDayClasses(day: MonthlyDay): Record<string, boolean> {
  return {
    'calendar-grid__cell--selected': props.selectedDate === day.date,
    'calendar-grid__cell--has-data': day.income > 0 || day.expense > 0,
    'calendar-grid__cell--today': isToday(day.date),
    'calendar-grid__cell--income': day.net > 0,
    'calendar-grid__cell--expense': day.net < 0,
  }
}

function getLunarDisplay(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  const info = getLunarInfo(date)
  return info.display
}

function handleDayClick(day: MonthlyDay) {
  emit('select', day.date)
}
</script>

<style scoped lang="scss">
.calendar-grid {
  background: #fff;
  border-radius: 8px;
  padding: 8px;

  &__weekdays {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
    margin-bottom: 4px;
  }

  &__weekday {
    text-align: center;
    font-size: 12px;
    font-weight: 600;
    color: #999;
    padding: 4px 0;
  }

  &__days {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
  }

  &__cell {
    min-height: 72px;
    border-radius: 4px;
    padding: 3px 4px;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.15s;
    display: flex;
    flex-direction: column;
    gap: 1px;
    overflow: hidden;

    &:hover {
      border-color: #409eff;
      box-shadow: 0 0 0 1px #409eff;
    }

    &--other-month {
      opacity: 0.35;
      cursor: default;
      &:hover {
        border-color: transparent;
        box-shadow: none;
      }
    }

    &--selected {
      border-color: #ff9800 !important;
      box-shadow: 0 0 0 2px rgba(255, 152, 0, 0.3) !important;
    }

    &--today {
      border-color: #52c41a;
    }
  }

  &__date-row {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  &__day-num {
    font-size: 14px;
    font-weight: 500;
    color: #333;

    &--today {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      background: #52c41a;
      color: #fff;
      border-radius: 50%;
      font-weight: 700;
    }
  }

  &__today-badge {
    font-size: 10px;
    background: #52c41a;
    color: #fff;
    border-radius: 3px;
    padding: 0 4px;
    line-height: 16px;
  }

  &__week-start {
    font-size: 6px;
    color: #aaa;
    margin-left: auto;
  }

  &__summary {
    line-height: 1.3;
  }

  &__summary-text {
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__lunar {
    font-size: 10px;
    color: #999;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.text-income { color: #389e0d; }
.text-expense { color: #cf1322; }
</style>
