<template>
  <div class="schedule-page">
    <div class="page-header">
      <div class="header-left">
        <h2>📅 日程视图</h2>
        <el-tag size="small" type="info" effect="plain">收件箱 · 里程碑 日历总览</el-tag>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="fetchAll">刷新</el-button>
      </div>
    </div>

    <el-card shadow="never" class="calendar-card">
      <el-calendar v-model="calendarDate" @current-date-change="handleMonthChange">
        <template #date-cell="{ data }">
          <div class="date-cell" :class="{ 'is-selected': selectedDate === data.day }" @click="selectDate(data.day)">
            <div class="date-number">{{ data.day.split('-')[2] }}</div>
            <div class="cell-items">
              <div
                v-for="e in displayEvents(data.day)"
                :key="e.id"
                class="cell-item"
                :class="{ done: e.status === 'done' }"
                :title="e.title"
              >
                <span class="cell-dot" :class="e.status" />
                <span class="cell-title">{{ smartTruncate(e.title, 10) }}</span>
              </div>
              <div
                v-if="getEventsForDay(data.day).length > 3 && !expandedDays[data.day]"
                class="cell-more"
                @click.stop="toggleDay(data.day)"
              >
                +{{ getEventsForDay(data.day).length - 3 }} 项
              </div>
              <div
                v-else-if="expandedDays[data.day]"
                class="cell-more"
                @click.stop="toggleDay(data.day)"
              >
                收起
              </div>
            </div>
          </div>
        </template>
      </el-calendar>
    </el-card>

    <!-- 选中日期的事件列表 -->
    <el-card v-if="dayEvents.length" shadow="hover" class="event-detail-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">{{ selectedDateLabel }}</span>
          <el-tag size="small" type="info">{{ dayEvents.length }} 项</el-tag>
        </div>
      </template>
      <div class="event-list">
        <template v-for="(e, idx) in displayList(selectedDate, dayEvents)" :key="e.id">
          <div class="event-item" :class="{ 'hidden-item': idx >= 3 && !expandedDays[selectedDate] }">
            <span class="status-dot" :class="e.status" />
            <el-tag :type="e.source === 'inbox' ? 'warning' : 'primary'" size="small">
              {{ e.source === 'inbox' ? '📥' : '🎯' }}
            </el-tag>
            <span class="event-title" :class="{ 'text-done': e.status === 'done' }">{{ e.title }}</span>
            <span class="event-date">{{ e.date }}</span>
          </div>
        </template>
        <div v-if="dayEvents.length > 3" class="collapse-toggle" @click="toggleDay(selectedDate)">
          <el-link :underline="false" type="info">
            {{ expandedDays[selectedDate] ? '收起 ▲' : `展开全部 ${dayEvents.length} 项 ▼` }}
          </el-link>
        </div>
      </div>
    </el-card>
    <el-card v-else-if="selectedDate" shadow="hover" class="event-detail-card">
      <template #header>
        <span class="card-title">{{ selectedDateLabel }}</span>
      </template>
      <div class="empty-state">当日无待办事项</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import request from '@/shared/utils/request'
import { smartTruncate } from '@/shared/utils/text'

interface CalendarEvent {
  id: string
  title: string
  date: string
  status: 'todo' | 'done'
  source: 'inbox' | 'milestone'
  sourceLabel: string
}

const calendarDate = ref(new Date())
const selectedDate = ref('')
const inboxItems = ref<any[]>([])
const milestones = ref<any[]>([])
const expandedDays = ref<Record<string, boolean>>({})

const allEvents = computed<CalendarEvent[]>(() => {
  const result: CalendarEvent[] = []

  for (const i of inboxItems.value) {
    if (i.due_date) {
      result.push({
        id: `inbox-${i.id}`,
        title: i.content,
        date: i.due_date,
        status: i.status === 'done' ? 'done' : 'todo',
        source: 'inbox',
        sourceLabel: i.category_display || '收件箱',
      })
    }
  }

  for (const m of milestones.value) {
    const due = m.target_date || m.goal_deadline
    if (due) {
      result.push({
        id: `milestone-${m.id}`,
        title: m.title,
        date: due,
        status: m.status === 'completed' ? 'done' : 'todo',
        source: 'milestone',
        sourceLabel: m.goal_title || '目标',
      })
    }
  }

  return result
})

const dayEvents = computed(() => {
  if (!selectedDate.value) return []
  return allEvents.value.filter(e => e.date === selectedDate.value)
})

const selectedDateLabel = computed(() => {
  if (!selectedDate.value) return ''
  const d = selectedDate.value.split('-')
  return `${parseInt(d[1])}月${parseInt(d[2])}日`
})

function getEventsForDay(day: string) {
  return allEvents.value.filter(e => e.date === day)
}

function displayEvents(day: string) {
  const items = getEventsForDay(day)
  if (items.length > 3 && !expandedDays.value[day]) {
    return items.slice(0, 3)
  }
  return items
}

function displayList(day: string, items: CalendarEvent[]) {
  if (items.length > 3 && !expandedDays.value[day]) {
    return items.slice(0, 3)
  }
  return items
}

function toggleDay(day: string) {
  expandedDays.value[day] = !expandedDays.value[day]
}

function selectDate(day: string) {
  selectedDate.value = day
}

function handleMonthChange(date: Date) {
  calendarDate.value = date
  selectedDate.value = ''
  fetchEvents(date)
}

async function fetchEvents(date: Date) {
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  try {
    const [inboxRes, milestoneRes] = await Promise.all([
      request({ url: `/inbox/items/calendar/?year=${year}&month=${month}`, method: 'get' }),
      request({ url: `/goals/milestones/?target_date_year=${year}&target_date_month=${month}&page_size=100`, method: 'get' }),
    ])
    inboxItems.value = inboxRes.data || []
    const raw = Array.isArray(milestoneRes.data) ? milestoneRes.data : (milestoneRes.data.results || [])
    milestones.value = raw
  } catch (e) {
    console.error('获取日历数据失败:', e)
  }
}

function fetchAll() {
  fetchEvents(calendarDate.value)
}

onMounted(() => {
  fetchEvents(calendarDate.value)
})
</script>

<style scoped>
.schedule-page {
  max-width: 100%;
  margin: 0 auto;
  padding: 8px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-left h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1F2937;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.calendar-card {
  border-radius: 6px;
  margin-bottom: 8px;
}
.calendar-card :deep(.el-card__body) {
  padding: 8px !important;
}
.calendar-card :deep(.el-calendar) {
  --el-calendar-border: #E5E7EB;
  --el-calendar-header-height: 32px;
  --el-calendar-cell-width: auto;
}
.calendar-card :deep(.el-calendar__header) {
  padding: 4px 0;
}
.calendar-card :deep(.el-calendar__header .el-calendar__title) {
  font-size: 14px;
}
.calendar-card :deep(.el-calendar__header .el-button-group .el-button) {
  padding: 4px 8px;
  font-size: 12px;
}
.calendar-card :deep(.el-calendar__body) {
  padding: 0;
}
.calendar-card :deep(.el-calendar-table) {
  width: 100%;
  table-layout: fixed;
}
.calendar-card :deep(.el-calendar-table thead th) {
  padding: 4px 0;
  font-size: 12px;
}
.calendar-card :deep(.el-calendar-table td) {
  padding: 2px;
  vertical-align: top;
  border: 1px solid #eee;
}
.calendar-card :deep(.el-calendar-table td.is-selected) {
  background: #EFF6FF;
}
.calendar-card :deep(.el-calendar-table td.is-today) {
  background: #FEFCE8;
}
.calendar-card :deep(.el-calendar-table .el-calendar-day) {
  min-height: 80px;
  padding: 4px;
  box-sizing: border-box;
}

.date-cell {
  cursor: pointer;
  min-height: 60px;
  padding: 2px;
  border-radius: 4px;
  transition: background 0.2s;
}
.date-cell:hover {
  background: #F3F4F6;
}
.date-cell.is-selected {
  background: #DBEAFE;
}

.date-number {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  width: 28px;
  height: 28px;
  line-height: 28px;
  text-align: center;
  margin: 2px;
}

.cell-items {
  margin-top: 2px;
  gap: 2px;
}

.cell-item {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 1px 0;
  font-size: 11px;
  line-height: 1.2;
  border-radius: 3px;
  overflow: hidden;
}
.cell-item.done .cell-title {
  text-decoration: line-through;
  color: #9CA3AF;
}

.cell-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.cell-dot.todo {
  background: #f56c6c;
}
.cell-dot.done {
  background: #67c23a;
}
.cell-dot.milestone {
  background: #e6a23c;
}

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
.cell-more:hover {
  background: #F3F4F6;
  color: #409EFF;
}

.event-detail-card {
  border-radius: 6px;
  margin-top: 8px;
  margin-bottom: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #1F2937;
}

.event-list {
  display: flex;
  flex-direction: column;
}

.event-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  border-bottom: 1px solid #f5f5f5;
}
.event-item:last-child {
  border-bottom: none;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.todo {
  background: #f56c6c;
}
.status-dot.done {
  background: #67c23a;
}
.status-dot.milestone {
  background: #e6a23c;
}

.event-title {
  flex: 1;
  font-size: 14px;
  color: #1F2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-title.text-done {
  color: #999;
  text-decoration: line-through;
}

.event-date {
  margin-left: auto;
  font-size: 12px;
  color: #999;
}

.collapse-toggle {
  text-align: center;
  padding: 8px 0 4px;
  border-top: 1px solid #f0f0f0;
  margin-top: 4px;
}
.collapse-toggle .el-link {
  font-size: 12px;
}

.empty-state {
  text-align: center;
  padding: 24px;
  color: #9CA3AF;
  font-size: 13px;
}
</style>
