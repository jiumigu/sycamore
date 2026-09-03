<template>
  <div class="cal-month">
    <!-- 列头：周日～周六 -->
    <div class="cal-weekdays">
      <div v-for="(wd, i) in WEEKDAYS" :key="i" class="cal-weekday" :class="{ 'is-weekend': i === 0 || i === 6 }">
        {{ wd }}
      </div>
    </div>

    <!-- 周行 × 7 列：grid-auto-rows 每行独立高度（钉钉式灵活） -->
    <div class="cal-grid">
      <div
        v-for="cell in cells"
        :key="cell.dateStr"
        class="cal-cell"
        :class="{
          'is-other-month': cell.isOtherMonth,
          'is-today': cell.isToday,
          'is-selected': cell.dateStr === selectedDate,
          'is-weekend': cell.weekday === 0 || cell.weekday === 6,
        }"
        @click="$emit('select-date', cell.dateStr)"
      >
        <div class="cell-head">
          <span class="cell-day" :class="{ 'today-badge': cell.isToday }">{{ cell.day }}</span>
          <span class="cell-lunar">{{ cell.lunar }}</span>
        </div>

        <div class="cell-items">
          <div
            v-for="e in displayEvents(cell.dateStr)"
            :key="e.id"
            class="cell-item"
            :class="[e.source, { done: e.status === 'done' }]"
            :title="e.title"
            @click.stop="$emit('click-event', e)"
          >
            <span class="cell-dot" :class="{ done: e.status === 'done' }" />
            <span class="cell-title">{{ e.title }}</span>
          </div>
          <div v-if="getCount(cell.dateStr) > MAX_VISIBLE && !isExpanded(cell.dateStr)" class="cell-more" @click.stop="toggleExpand(cell.dateStr)">
            +{{ getCount(cell.dateStr) - MAX_VISIBLE }} 项
          </div>
          <div v-else-if="isExpanded(cell.dateStr)" class="cell-more" @click.stop="toggleExpand(cell.dateStr)">
            收起
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Solar } from 'lunar-typescript'
import type { CalendarEvent } from '../../types/calendar'

const props = defineProps<{
  events: CalendarEvent[]
  year: number
  month: number
  selectedDate: string
  expandedDays: Record<string, boolean>
}>()

const emit = defineEmits<{
  (e: 'select-date', day: string): void
  (e: 'toggle-expand', day: string): void
  (e: 'click-event', ev: CalendarEvent): void
}>()

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']
const MAX_VISIBLE = 3

interface DayCell {
  dateStr: string
  day: number
  weekday: number
  isOtherMonth: boolean
  isToday: boolean
  lunar: string
}

function pad(n: number) { return String(n).padStart(2, '0') }

/** 农历/节日/节气 显示文本（优先级：节气 > 农历节日 > 公历节日 > 农历日） */
function lunarText(y: number, m: number, d: number): string {
  const solar = Solar.fromYmd(y, m, d)
  const lunar = solar.getLunar()
  const jq = lunar.getJieQi()
  if (jq) return jq
  const lFest = lunar.getFestivals()
  if (lFest && lFest.length) return lFest[0]
  const sFest = solar.getFestivals()
  if (sFest && sFest.length) return sFest[0]
  return lunar.getDayInChinese()
}

/** 当月 6 周 × 7 天网格（含上月/下月补位） */
const cells = computed<DayCell[]>(() => {
  const { year, month } = props
  const firstWeekday = new Date(year, month - 1, 1).getDay() // 周日=0
  const daysInMonth = new Date(year, month, 0).getDate()
  const total = 42 // 6 行固定（保证月视图高度稳定）
  const result: DayCell[] = []
  const today = new Date()

  for (let i = 0; i < total; i++) {
    const offset = i - firstWeekday + 1
    const date = new Date(year, month - 1, offset)
    const isOther = date.getMonth() !== month - 1
    const y = date.getFullYear()
    const m = date.getMonth() + 1
    const d = date.getDate()
    result.push({
      dateStr: `${y}-${pad(m)}-${pad(d)}`,
      day: d,
      weekday: date.getDay(),
      isOtherMonth: isOther,
      isToday: y === today.getFullYear() && m === today.getMonth() + 1 && d === today.getDate(),
      lunar: lunarText(y, m, d),
    })
  }
  return result
})

function eventsForDay(dateStr: string): CalendarEvent[] {
  return props.events.filter(e =>
    // 单日事件精确匹配；预留跨天（endDate）：startDate <= date <= endDate
    (e.endDate ? e.date <= dateStr && e.endDate >= dateStr : e.date === dateStr),
  )
}

function getCount(dateStr: string) { return eventsForDay(dateStr).length }

function isExpanded(dateStr: string) { return !!props.expandedDays[dateStr] }

function displayEvents(dateStr: string): CalendarEvent[] {
  const items = eventsForDay(dateStr)
  if (items.length > MAX_VISIBLE && !isExpanded(dateStr)) return items.slice(0, MAX_VISIBLE)
  return items
}

function toggleExpand(dateStr: string) { emit('toggle-expand', dateStr) }
</script>

<style scoped>
.cal-month {
  user-select: none;
}

/* 列头 */
.cal-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  margin-bottom: 2px;
}
.cal-weekday {
  text-align: center;
  font-size: 12px;
  color: #606266;
  padding: 6px 0;
  font-weight: 500;
}
.cal-weekday.is-weekend {
  color: #f56c6c;
}

/* 网格：关键——grid-auto-rows 每行独立高度，行高由内容撑开 */
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  grid-auto-rows: minmax(96px, auto);
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}

.cal-cell {
  border-right: 1px solid #eef0f2;
  border-bottom: 1px solid #eef0f2;
  padding: 4px 6px;
  cursor: pointer;
  min-width: 0;
  display: flex;
  flex-direction: column;
  transition: background 0.15s;
  box-sizing: border-box;
}
.cal-cell:nth-child(7n) { border-right: none; }
.cal-cell:nth-last-child(-n + 7) { border-bottom: none; }
.cal-cell:hover { background: #f8fafc; }
.cal-cell.is-other-month { background: #fafafa; }
.cal-cell.is-other-month .cell-day,
.cal-cell.is-other-month .cell-lunar { color: #c0c4cc; }
.cal-cell.is-selected { background: #eff6ff; outline: 1px solid #93c5fd; outline-offset: -1px; }
.cal-cell.is-weekend.is-other-month { background: #fafafa; }

.cell-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 2px;
}
.cell-day {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  width: 22px;
  height: 22px;
  line-height: 22px;
  text-align: center;
  border-radius: 50%;
}
.cell-day.today-badge {
  background: #409eff;
  color: #fff;
  font-weight: 600;
}
.cell-lunar {
  font-size: 10px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 日程条目 */
.cell-items {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow: hidden;
  margin-top: 1px;
}
.cell-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 1px 3px;
  border-radius: 3px;
  font-size: 11px;
  line-height: 1.35;
  overflow: hidden;
  background: #f3f4f6;
  cursor: pointer;
  transition: filter 0.12s;
}
.cell-item:hover { filter: brightness(0.95); }
.cell-item.inbox { background: #fef3e2; }
.cell-item.milestone { background: #e8f0fe; }
.cell-item.done { opacity: 0.55; }
.cell-item.done .cell-title { text-decoration: line-through; }

.cell-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #f56c6c;
}
.cell-dot.done { background: #67c23a; }

.cell-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #374151;
}

.cell-more {
  font-size: 10px;
  color: #909399;
  cursor: pointer;
  padding: 1px 4px;
  border-radius: 3px;
  text-align: center;
  margin-top: 1px;
}
.cell-more:hover { background: #eef2f7; color: #409eff; }
</style>
