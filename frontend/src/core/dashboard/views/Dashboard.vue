<template>
  <div class="dashboard">
    <!-- 系统箴言 -->
    <div class="dashboard-motto">
      <p>{{ motto }}</p>
      <el-button text size="small" @click="editMotto">✏️</el-button>
    </div>

    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">仪表盘</h1>
        <el-tag type="primary" class="module-tag">总览</el-tag>
      </div>
      <div class="header-actions">
        <!-- 汇总总览的菜单项已撤（v3.63.14）⇒ 入口挂在这里。
             它回答的是「这一年我到底在不在动」（年度尺度），与本页的「本周」是两件事，
             所以只并入入口、不合并页面（合并会把首屏待办挤到图表下面）。 -->
        <el-button @click="$router.push('/summary')">📊 汇总总览</el-button>
        <el-button @click="refreshAll">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 跑道（v3.64.41）：整个系统里**唯一在倒计时的量**。
         放在四张「本周」卡之上 —— 那四张回答「这周有没有在动」，
         这一张回答「这条路还能走多久」，后者才是决定要不要调整的那个。
         🔴 口径与 KPI `redemption.runway`、阶段账本共用同一个后端函数。 -->
    <RunwayCard ref="runwayCardRef" />

    <!-- 顶部统计行 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <el-skeleton :loading="loadingGoals" animated>
            <template #template>
              <el-skeleton-item variant="text" style="width:60%;height:32px;margin:0 auto" />
            </template>
            <template #default>
              <div class="stat-value" style="color: var(--el-color-primary)">{{ stats.goalCount }}</div>
            </template>
          </el-skeleton>
          <div class="stat-label">进行中目标</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <el-skeleton :loading="loadingDiary" animated>
            <template #template>
              <el-skeleton-item variant="text" style="width:60%;height:32px;margin:0 auto" />
            </template>
            <template #default>
              <div class="stat-value" style="color: #10B981">{{ stats.diaryCount ?? '-' }}</div>
            </template>
          </el-skeleton>
          <div class="stat-label">本周日记</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" style="color: #F59E0B">{{ stats.stepCount ?? '-' }}</div>
          <div class="stat-label">本周步数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" style="color: #EF4444">{{ stats.weeklyExpense ?? '-' }}</div>
          <div class="stat-label">本周支出</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 今天的三条线（v3.64.13）：睡眠 / 午睡 / 流失
         🔴 放在「自我运转」之上：那一张是**周**尺子（这周有没有在动），
            这一张是**今天**（今天有没有过度）。裸辞后最先滑坡的是当天，
            所以今日的护栏要在周的上面。 -->
    <DailyGuardCard />

    <!-- 自我运转小卡（第一屏）：
         只在**真的在进行中**时出现 —— 没有阶段时整张卡不渲染，
         免得仪表盘上长期挂一张空卡天天提醒你「没在做」。 -->
    <SelfRunCard />

    <!-- 待处理 + 需要关注 + 随机回顾 -->
    <el-row :gutter="16" class="mid-row">
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>📥 待处理</span>
              <el-tag v-if="!loadingInbox && pendingItems.length" size="small" type="warning">{{ pendingItems.length }}项</el-tag>
            </div>
          </template>
          <el-skeleton :loading="loadingInbox" animated :count="3" />
          <template v-if="!loadingInbox">
            <div v-if="pendingItems.length" class="action-list">
              <div
                v-for="item in pendingItems.slice(0, 5)"
                :key="item.id"
                class="action-item"
              >
                <span class="priority-dot">{{ item.priority === 'high' ? '🔴' : item.priority === 'medium' ? '🟡' : '🟢' }}</span>
                <span class="action-name">{{ item.content }}</span>
                <el-tag v-if="item.category" size="small">{{ item.category_display || item.category }}</el-tag>
              </div>
            </div>
            <el-empty v-else description="暂无待处理事项" :image-size="60" />
            <div class="card-footer">
              <el-button type="primary" @click="$router.push('/inbox')">
                去收集箱处理
              </el-button>
            </div>
          </template>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>⚠️ 需要关注</span>
              <el-tag v-if="!loadingAlerts && alerts.length" size="small" type="danger">{{ alerts.length }}项</el-tag>
            </div>
          </template>
          <el-skeleton :loading="loadingAlerts" animated :count="3" />
          <template v-if="!loadingAlerts">
            <div v-if="alerts.length" class="alert-list">
              <div v-for="(alert, i) in alerts" :key="i" class="alert-item">
                <el-icon :color="alert.type === 'danger' ? '#EF4444' : '#F59E0B'" class="alert-icon">
                  <WarningFilled />
                </el-icon>
                <span class="alert-text">{{ alert.text }}</span>
              </div>
            </div>
            <el-empty v-else description="一切正常，无需关注" :image-size="60" />
          </template>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>🔮 随机回顾</span>
              <el-button text size="small" @click="fetchRandomRetro" :loading="loadingRetro">换一条</el-button>
            </div>
          </template>
          <el-skeleton :loading="loadingRetro" animated :count="3" />
          <template v-if="!loadingRetro">
            <div v-if="retroItem" class="retro-card">
              <el-tag size="small">{{ retroItem.type }}</el-tag>
              <p class="retro-content">{{ retroItem.content }}</p>
              <span class="retro-date">{{ retroItem.date }}</span>
            </div>
            <el-empty v-else description="暂无历史记录" :image-size="60" />
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 每日金句：v3.63.14 起改为共享组件 `<QuoteCard />`（唯一实现）。
         原先仪表盘与汇总总览各写一套模板 + 各调一次 quotes/next/，
         空态文案与作者排布也是两套 ⇒ 改口径要改两处，漏一处就长得不一样。
         取数、空态、卡内滚动全部收在组件里，这里只管摆在哪。 -->
    <QuoteCard ref="quoteCardRef" class="section-card" />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Refresh, WarningFilled } from '@element-plus/icons-vue'
import { getGoalList } from '@/modules/goals/api/goalApi'
import { getTodayPending } from '@/modules/inbox/api/inboxApi'
import { getDueReminders } from '@/modules/relation/api/relationshipApi'
import { getYearlyOverview } from '@/modules/summary/api/summaryApi'
import { getWeekCount, getWeekStats } from '@/modules/temporal/api/temporalApi'
import { getRandomRetro } from '@/modules/summary/api/summaryApi'
import SelfRunCard from '@/modules/selfrun/components/SelfRunCard.vue'
import RunwayCard from '@/modules/selfrun/components/RunwayCard.vue'
import DailyGuardCard from '@/modules/temporal/components/DailyGuardCard.vue'
import QuoteCard from '@/modules/toolkit/components/QuoteCard.vue'
import type { InboxItem } from '@/modules/inbox/types/inboxTypes'

interface AlertItem {
  type: 'danger' | 'warning'
  text: string
}

interface RetroItem {
  type: string
  content: string
  date: string
}

// ─── 系统箴言 ───
const motto = ref(localStorage.getItem('dashboard_motto') || '这个系统服务于 _____')

async function editMotto() {
  try {
    const { value } = await ElMessageBox.prompt('修改你的系统宣言', '编辑', {
      inputValue: motto.value,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    motto.value = value
    localStorage.setItem('dashboard_motto', value)
  } catch {
    // cancelled
  }
}

// ─── 统计卡片 ───
const stats = reactive({
  goalCount: 0,
  diaryCount: null as number | null,
  stepCount: null as number | null,
  weeklyExpense: null as number | null,
})

const pendingItems = ref<InboxItem[]>([])
const alerts = reactive<AlertItem[]>([])
const retroItem = ref<RetroItem | null>(null)
/** 金句卡（共享组件）—— 「刷新」时要能重取一条 */
const quoteCardRef = ref<InstanceType<typeof QuoteCard> | null>(null)
/** 跑道卡（v3.64.41）—— 同一条刷新链路，别让它停在旧数上 */
const runwayCardRef = ref<InstanceType<typeof RunwayCard> | null>(null)

// ─── 独立加载状态 ───
const loadingGoals = ref(true)
const loadingDiary = ref(true)
const loadingInbox = ref(true)
const loadingAlerts = ref(true)
const loadingRetro = ref(true)

async function fetchGoalStats() {
  loadingGoals.value = true
  try {
    const res = await getGoalList({ status: 'in-progress' })
    const data = res.data
    const list = Array.isArray(data) ? data : data?.results ?? []
    stats.goalCount = list.length
  } catch {
    stats.goalCount = 0
  } finally {
    loadingGoals.value = false
  }
}

async function fetchWeekStats() {
  loadingDiary.value = true
  try {
    const res = await getWeekStats()
    stats.diaryCount = res.data.count
    stats.stepCount = res.data.step_count
    stats.weeklyExpense = res.data.weekly_expense
  } catch {
    stats.diaryCount = 0
  } finally {
    loadingDiary.value = false
  }
}

async function fetchPendingItems() {
  loadingInbox.value = true
  try {
    const res = await getTodayPending()
    const data = res.data
    pendingItems.value = (data?.results ?? []).filter(Boolean)
  } catch {
    pendingItems.value = []
  } finally {
    loadingInbox.value = false
  }
}

async function fetchAlerts() {
  loadingAlerts.value = true
  alerts.length = 0

  // 快到期目标
  try {
    const res = await getGoalList({ status: 'in-progress', ordering: 'deadline' })
    const data = res.data
    const list = Array.isArray(data) ? data : data?.results ?? []
    const now = new Date()
    for (const goal of list) {
      if (goal.deadline) {
        const days = Math.ceil((new Date(goal.deadline).getTime() - now.getTime()) / 86400000)
        if (days <= 0) {
          alerts.push({ type: 'danger', text: `目标「${goal.title}」已到期` })
        } else if (days <= 7) {
          alerts.push({ type: 'warning', text: `目标「${goal.title}」${days}天后到期` })
        }
      }
    }
  } catch {
    // noop
  }

  // 关系提醒
  try {
    const res = await getDueReminders()
    const list = Array.isArray(res.data) ? res.data : res.data?.results ?? []
    for (const r of list) {
      alerts.push({ type: 'warning', text: `联系「${r.name || r.relationship_name}」快` })
    }
  } catch {
    // noop
  }

  loadingAlerts.value = false
}

async function fetchRandomRetro() {
  loadingRetro.value = true
  try {
    const res = await getRandomRetro()
    retroItem.value = res.data
  } catch {
    retroItem.value = null
  } finally {
    loadingRetro.value = false
  }
}

/**
 * 金句取数已搬进共享组件 `QuoteCard`（唯一实现）。
 * 这里只保留「刷新时重取一条」的入口 —— 不再有第二份 `getNextQuote()` 调用。
 */
async function refreshAll() {
  await Promise.all([
    fetchGoalStats(),
    fetchPendingItems(),
    fetchAlerts(),
    fetchWeekStats(),
    fetchRandomRetro(),
    quoteCardRef.value?.refresh(),
    runwayCardRef.value?.refresh(),
  ])
}

onMounted(() => {
  // 各自独立加载，不互相阻塞（金句由组件自己在 onMounted 里取）
  fetchGoalStats()
  fetchWeekStats()
  fetchPendingItems()
  fetchAlerts()
  fetchRandomRetro()
})
</script>

<style scoped lang="scss">
.dashboard {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.dashboard-motto {
  text-align: center;
  margin-bottom: 16px;
  p {
    font-size: 18px;
    color: #666;
    font-style: italic;
    display: inline;
    margin-right: 8px;
  }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    .page-title { margin: 0; font-size: 24px; font-weight: 600; }
    .module-tag { font-size: 12px; }
  }
}

.stats-row {
  margin-bottom: 16px;

  .stat-card {
    :deep(.el-card__body) {
      padding: 20px;
      text-align: center;
    }
  }

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 6px;
  }
  .stat-label {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }
}

.mid-row {
  margin-bottom: 16px;
}

.section-card {
  margin-bottom: 16px;
  height: 100%;

  :deep(.el-card__body) {
    padding: 20px;
    min-height: 120px;
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 15px;
}

.card-footer {
  text-align: center;
  margin-top: 12px;
}

.progress-sub {
  font-size: 13px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}

.action-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;

  &:hover {
    background: var(--el-fill-color-light);
  }

  &:active {
    background: var(--el-fill-color);
  }
}

.priority-dot {
  flex-shrink: 0;
  font-size: 14px;
  line-height: 1;
}

.action-name {
  font-size: 14px;
  color: var(--el-text-color-primary);
  flex: 1;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.alert-icon { flex-shrink: 0; }
.alert-text { color: var(--el-text-color-primary); }

.retro-card {
  .retro-content {
    font-size: 14px;
    color: var(--el-text-color-primary);
    margin: 8px 0;
    line-height: 1.6;
  }
  .retro-date {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

.progress-section {
  padding: 4px 0;
}

.module-bars {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.module-bar {
  .module-bar-label {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    color: var(--el-text-color-regular);
    margin-bottom: 4px;
  }
}

@media (max-width: 768px) {
  .stats-row {
    .stat-value { font-size: 22px; }
  }
  .mid-row .el-col {
    margin-bottom: 16px;
  }
}
</style>
