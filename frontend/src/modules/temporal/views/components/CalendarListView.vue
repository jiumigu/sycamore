<template>
  <div class="cal-list">
    <el-empty v-if="!grouped.length" description="该月暂无日程" :image-size="60" />
    <div v-for="g in grouped" :key="g.date" class="list-day">
      <div class="list-day-head">
        <span class="list-date" :class="{ 'is-today': g.date === todayStr }">{{ g.label }}</span>
        <el-tag size="small" type="info">{{ g.items.length }} 项</el-tag>
      </div>
      <div class="list-items">
        <div
          v-for="e in g.items"
          :key="e.id"
          class="list-item"
          :class="{ done: e.status === 'done' }"
          @click="$emit('click-event', e)"
        >
          <span class="cell-dot" :class="{ done: e.status === 'done' }" />
          <el-tag :type="e.source === 'inbox' ? 'warning' : 'primary'" size="small" effect="plain">
            {{ e.source === 'inbox' ? '📥' : '🎯' }}
          </el-tag>
          <span class="list-title">{{ e.title }}</span>
          <span class="list-src">{{ e.sourceLabel }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CalendarEvent } from '../../types/calendar'

const props = defineProps<{
  events: CalendarEvent[]
  year: number
  month: number
}>()

const emit = defineEmits<{
  (e: 'select-date', day: string): void
  (e: 'click-event', ev: CalendarEvent): void
}>()

const todayStr = computed(() => {
  const t = new Date()
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
})

const grouped = computed(() => {
  const map = new Map<string, CalendarEvent[]>()
  for (const e of props.events) {
    if (!map.has(e.date)) map.set(e.date, [])
    map.get(e.date)!.push(e)
  }
  return [...map.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, items]) => {
      const [y, m, d] = date.split('-').map(Number)
      const week = ['日', '一', '二', '三', '四', '五', '六'][new Date(y, m - 1, d).getDay()]
      return { date, label: `${m}月${d}日 周${week}`, items }
    })
})
</script>

<style scoped>
.cal-list {
  padding: 4px 0;
}
.list-day {
  margin-bottom: 14px;
}
.list-day-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.list-date {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.list-date.is-today {
  color: #409eff;
}
.list-items {
  border: 1px solid #eef0f2;
  border-radius: 6px;
  overflow: hidden;
}
.list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #f5f5f5;
  cursor: pointer;
  transition: background 0.15s;
}
.list-item:last-child { border-bottom: none; }
.list-item:hover { background: #f8fafc; }
.list-item.done .list-title { color: #9ca3af; text-decoration: line-through; }
.list-title {
  flex: 1;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.list-src {
  font-size: 11px;
  color: #909399;
  flex-shrink: 0;
}
.cell-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #f56c6c;
}
.cell-dot.done { background: #67c23a; }
</style>
