<template>
  <div class="schedule-page">
    <div class="page-header">
      <div class="header-left">
        <h2>📅 日程视图</h2>
        <el-tag size="small" type="info" effect="plain">收件箱 · 里程碑 日历总览</el-tag>
      </div>
      <div class="header-actions">
        <el-button size="small" :type="viewMode === 'month' ? 'primary' : ''" @click="viewMode = 'month'">月</el-button>
        <el-button size="small" :type="viewMode === 'list' ? 'primary' : ''" @click="viewMode = 'list'">列表</el-button>
        <el-button size="small" @click="fetchAll">刷新</el-button>
      </div>
    </div>

    <!-- 月份导航（钉钉式：上/下月 + 今天 + 年月标题） -->
    <div class="cal-toolbar">
      <div class="toolbar-left">
        <el-button-group>
          <el-button size="small" @click="changeMonth(-1)">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <el-button size="small" @click="changeMonth(1)">
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </el-button-group>
        <span class="toolbar-title">{{ calendarDate.getFullYear() }}年{{ calendarDate.getMonth() + 1 }}月</span>
      </div>
      <el-button size="small" @click="goToday">今天</el-button>
    </div>

    <el-card shadow="never" class="calendar-card">
      <!-- 月视图：自建，每行独立高度 -->
      <CalendarMonthView
        v-if="viewMode === 'month'"
        :events="allEvents"
        :year="calendarDate.getFullYear()"
        :month="calendarDate.getMonth() + 1"
        :selected-date="selectedDate"
        :expanded-days="expandedDays"
        @select-date="selectDate"
        @toggle-expand="toggleDay"
        @click-event="handleEventClick"
      />

      <!-- 列表视图 -->
      <CalendarListView
        v-else
        :events="allEvents"
        :year="calendarDate.getFullYear()"
        :month="calendarDate.getMonth() + 1"
        @select-date="selectDate"
        @click-event="handleEventClick"
      />
    </el-card>

    <!-- 事项详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="detailTitle" size="420px">
      <div v-if="detailEvent" class="event-detail">
        <div class="detail-meta">
          <el-tag :type="detailEvent.source === 'inbox' ? 'warning' : 'primary'" size="small">
            {{ detailEvent.source === 'inbox' ? '📥 收件箱待办' : '🎯 里程碑' }}
          </el-tag>
          <el-tag :type="detailEvent.status === 'done' ? 'success' : 'danger'" size="small" effect="plain">
            {{ detailEvent.status === 'done' ? '已完成' : '待完成' }}
          </el-tag>
        </div>

        <el-descriptions :column="1" border size="small" class="detail-desc">
          <el-descriptions-item label="日期">{{ detailEvent.date }}</el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.goalTitle" label="所属目标">{{ detailEvent.goalTitle }}</el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.category" label="类别">{{ detailEvent.category }}</el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.tags" label="标签">{{ detailEvent.tags }}</el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.description" label="描述">
            <div class="desc-text">{{ detailEvent.description }}</div>
          </el-descriptions-item>
          <!-- 🔴 批阅单独一栏：它此前被并进「完成备注」显示过 —— 写的是 `self_review`、
               显示的却是 `completed_note` 的标题，刷新后那行还会凭空消失。
               两列各归各位，标题不一致就等于同一句话有两个名字。 -->
          <el-descriptions-item v-if="detailEvent.selfReview" label="自我批阅">
            <div class="desc-text">{{ detailEvent.selfReview }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.completedNote" label="完成备注">
            <div class="desc-text">{{ detailEvent.completedNote }}</div>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 详情模式：完成按钮 -->
        <template v-if="detailEvent.status !== 'done' && !completing">
          <el-button
            type="success"
            class="complete-btn"
            @click="enterCompleteMode"
          >
            ✓ 完成{{ detailEvent.source === 'inbox' ? '待办' : '里程碑' }}
          </el-button>
        </template>

        <!-- 录入模式：完成备注 + 确认 -->
        <template v-else-if="detailEvent.status !== 'done' && completing">
          <div class="completion-form">
            <!-- 标题跟着写入的列走：这里对里程碑写的是批阅，不是「心得」 -->
            <div class="completion-title">
              {{ detailEvent.source === 'inbox' ? '记录完成心得' : '写一句批阅' }}
            </div>
            <el-input
              v-model="completionNote"
              type="textarea"
              :rows="5"
              :placeholder="detailEvent.source === 'inbox'
                ? '做完有什么感想？耗时多久？留个记录日后可回顾'
                : '难在哪，下次怎么改 —— 一句话就够'"
              maxlength="500"
              show-word-limit
            />
            <div class="completion-actions">
              <el-button @click="cancelComplete">取消</el-button>
              <el-button
                type="success"
                :loading="submitting"
                @click="submitComplete"
              >
                ✓ 确认完成
              </el-button>
            </div>
          </div>
        </template>

        <el-alert v-else type="success" :closable="false" show-icon title="该事项已完成" />
      </div>
    </el-drawer>

    <!-- 选中日期的事件列表 -->
    <el-card v-if="selectedDate && dayEvents.length" shadow="hover" class="event-detail-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">{{ selectedDateLabel }}</span>
          <el-tag size="small" type="info">{{ dayEvents.length }} 项</el-tag>
        </div>
      </template>
      <div class="event-list">
        <template v-for="(e, idx) in displayList(selectedDate, dayEvents)" :key="e.id">
          <div class="event-item" :class="{ 'hidden-item': idx >= 3 && !expandedDays[selectedDate] }">
            <span class="status-dot" :class="{ done: e.status === 'done' }" />
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
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/shared/utils/request'
import { apiErrorText } from '@/shared/utils/apiError'
import CalendarMonthView from './components/CalendarMonthView.vue'
import CalendarListView from './components/CalendarListView.vue'
import type { CalendarEvent } from '../types/calendar'

const calendarDate = ref(new Date())
const selectedDate = ref('')
const inboxItems = ref<any[]>([])
const milestones = ref<any[]>([])
const expandedDays = ref<Record<string, boolean>>({})
const viewMode = ref<'month' | 'list'>('month')
const drawerVisible = ref(false)
const detailEvent = ref<CalendarEvent | null>(null)
const completing = ref(false)        // 是否在录入完成模式
const submitting = ref(false)         // 提交中
const completionNote = ref('')

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
        description: i.description || '',
        category: i.category_display || i.category || '',
        tags: i.tags || '',
        remindAt: i.remind_at || '',
        rawId: i.id,
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
        description: m.description || '',
        completedNote: m.completed_note || '',
        selfReview: m.self_review || '',
        goalTitle: m.goal_title || '',
        goalDeadline: m.goal_deadline || '',
        rawId: m.id,
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

function displayList(day: string, items: CalendarEvent[]) {
  if (items.length > 3 && !expandedDays.value[day]) return items.slice(0, 3)
  return items
}

function toggleDay(day: string) {
  expandedDays.value[day] = !expandedDays.value[day]
}

function selectDate(day: string) {
  selectedDate.value = day
}

const detailTitle = computed(() => detailEvent.value?.title || '事项详情')

function handleEventClick(ev: CalendarEvent) {
  detailEvent.value = ev
  drawerVisible.value = true
}

function enterCompleteMode() {
  const ev = detailEvent.value
  // ⚠️ 回填必须跟着**写入口**走：里程碑那个框写的是 `self_review`，
  //    回填却取 `completed_note` 的话，一条「完成过又改回进行中」的里程碑
  //    打开时框是空的，一保存就把原来那句覆盖掉（旧内容无声消失）。
  completionNote.value = (ev?.source === 'milestone' ? ev.selfReview : ev?.completedNote) || ''
  completing.value = true
}

function cancelComplete() {
  completing.value = false
  completionNote.value = ''
}

async function submitComplete() {
  const ev = detailEvent.value
  if (!ev || ev.status === 'done') return
  submitting.value = true
  try {
    const note = completionNote.value.trim()
    if (ev.source === 'milestone') {
      // 🔴 后端要求完成里程碑必须附一句批阅（goals/services/completion_review.py），
      //    缺了返回 400。先在本地挡：空着点「确认完成」不该发一次必然失败的请求。
      if (!note) {
        ElMessage.warning('留一句再完成')
        return                       // `finally` 会复位 submitting
      }
      // ⚠️ 这个框的语义一直是「完成心得」（占位文案就是「心得、答题情况」），
      //    此前却发给了 `completed_note`（完成备注），于是这里完成的里程碑
      //    从来不算「有批阅」。改为写进 `self_review` —— 同一个框只写一列，
      //    不两列都发（那会让同一句话有两个来源，以后必然分叉）。
      await request({
        url: `/goals/milestones/${ev.rawId}/`,
        method: 'patch',
        data: { status: 'completed', self_review: note },
      })
    } else {
      await request({
        url: `/inbox/items/${ev.rawId}/`,
        method: 'patch',
        data: { status: 'done', completion_note: note },
      })
    }
    ElMessage.success('已完成 ✓')
    ev.status = 'done'
    // 回显跟着写入的列走：里程碑那句是批阅，不是完成备注
    if (note) {
      if (ev.source === 'milestone') ev.selfReview = note
      else ev.completedNote = note
    }
    completing.value = false
    completionNote.value = ''
    fetchEvents(calendarDate.value)
  } catch (e: any) {
    // 用唯一实现：400 的体是 `{'self_review': ['…']}`，没有 `detail` 键 ——
    // 原来只读 `detail`，于是「留一句再完成」这句后端话术永远显示不出来，
    // 用户只会看到「操作失败」。
    ElMessage.error(apiErrorText(e, '操作失败'))
  } finally {
    submitting.value = false
  }
}

function changeMonth(delta: number) {
  calendarDate.value = new Date(calendarDate.value.getFullYear(), calendarDate.value.getMonth() + delta, 1)
  selectedDate.value = ''
  fetchEvents(calendarDate.value)
}

function goToday() {
  calendarDate.value = new Date()
  selectedDate.value = ''
  fetchEvents(calendarDate.value)
}

async function fetchEvents(date: Date) {
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  try {
    const [inboxRes, milestoneRes] = await Promise.all([
      request({ url: `/inbox/items/calendar/?year=${year}&month=${month}`, method: 'get' }),
      // 🔴 `exclude_abandoned_goals=1`：**已放弃目标 + 还没完成**的里程碑不进日历（2026-10-26）
      //    放弃目标时里程碑**不级联删**（项目铁律），所以它们的 pending 项会一直
      //    留在日历上，看起来像一堆还没做的事。已完成的**要留** —— 翻历史日程
      //    看「那天做了什么」不能少条目。过滤开关由后端解释，前端不自算。
      request({
        url: `/goals/milestones/?target_date_year=${year}&target_date_month=${month}&page_size=100&exclude_abandoned_goals=1`,
        method: 'get',
      }),
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

.cal-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.toolbar-title {
  font-size: 16px;
  font-weight: 600;
  color: #1F2937;
}

.calendar-card {
  border-radius: 6px;
  margin-bottom: 8px;
}
.calendar-card :deep(.el-card__body) {
  padding: 10px !important;
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
.event-item:last-child { border-bottom: none; }
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #f56c6c;
}
.status-dot.done { background: #67c23a; }
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
.collapse-toggle .el-link { font-size: 12px; }
.empty-state {
  text-align: center;
  padding: 24px;
  color: #9CA3AF;
  font-size: 13px;
}
.event-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.detail-meta {
  display: flex;
  gap: 8px;
}
.detail-desc :deep(.el-descriptions__label) {
  width: 90px;
  color: #909399;
}
.desc-text {
  white-space: pre-wrap;
  word-break: break-word;
  color: #374151;
  line-height: 1.6;
}
.complete-btn {
  width: 100%;
  margin-top: 6px;
}
.completion-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}
.completion-title {
  font-size: 13px;
  font-weight: 600;
  color: #1F2937;
}
.completion-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
