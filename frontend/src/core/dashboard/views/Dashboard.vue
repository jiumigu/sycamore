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
        <el-button @click="refreshAll">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

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

    <!-- 快速记录读者互动 -->
    <el-card shadow="never" class="section-card quick-interaction-card">
      <template #header>
        <div class="card-header">
          <span>📬 快速记录读者互动</span>
          <el-tag v-if="!loadingRecent && recentInteractions.length" size="small" type="success">{{ recentInteractions.length }}条</el-tag>
        </div>
      </template>
      <div class="quick-input-area">
        <el-input
          v-model="quickContent"
          type="textarea"
          :rows="2"
          placeholder="粘贴读者留言..."
          @keydown.enter.ctrl="quickSave"
        />
        <div v-if="showAdvanced" class="advanced-options">
          <el-row :gutter="8">
            <el-col :span="8">
              <el-select v-model="quickType" size="small" class="full-width">
                <el-option v-for="o in INTERACTION_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-col>
            <el-col :span="8">
              <el-input v-model="quickReader" size="small" placeholder="读者名（可选）" />
            </el-col>
            <el-col :span="8">
              <el-select v-model="quickEnergy" size="small" class="full-width">
                <el-option v-for="o in ENERGY_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
            </el-col>
          </el-row>
        </div>
        <div class="quick-footer">
          <el-button type="primary" @click="quickSave" :loading="savingQuick" size="small">
            记录（Ctrl+Enter）
          </el-button>
          <el-button size="small" text @click="showAdvanced = !showAdvanced">
            {{ showAdvanced ? '收起' : '更多选项' }}
          </el-button>
          <span class="quick-tip">默认：留言 +1分 | 只需填内容</span>
        </div>
      </div>
      <div v-if="!loadingRecent && recentInteractions.length" class="recent-interactions">
        <div class="recent-title">最近互动</div>
        <div v-for="item in recentInteractions.slice(0, 3)" :key="item.id" class="recent-item">
          <span class="recent-date">{{ item.created_at.slice(5, 10) }}</span>
          <span class="recent-name">{{ item.reader_name }}</span>
          <span class="recent-content">{{ item.content.slice(0, 30) }}{{ item.content.length > 30 ? '...' : '' }}</span>
          <span class="energy-badge">+{{ item.energy_score }}</span>
        </div>
      </div>
    </el-card>

    <!-- 年度进度 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>📈 年度进度</span>
          <span v-if="!loadingProgress && progress" class="progress-sub">
            {{ progress.total_points }} / {{ progress.yearly_target }} 分
            ({{ progress.progress_percent }}%)
          </span>
        </div>
      </template>
      <el-skeleton :loading="loadingProgress" animated>
        <template #template>
          <el-skeleton-item variant="text" style="width:100%;height:16px" />
          <div style="margin-top:20px">
            <el-skeleton-item variant="text" style="width:80%;height:10px;display:block;margin-bottom:12px" />
            <el-skeleton-item variant="text" style="width:80%;height:10px;display:block;margin-bottom:12px" />
            <el-skeleton-item variant="text" style="width:80%;height:10px;display:block;margin-bottom:12px" />
          </div>
        </template>
        <template #default>
          <div v-if="progress" class="progress-section">
            <el-progress
              :percentage="Math.min(progress.progress_percent, 100)"
              :stroke-width="16"
              :text-inside="true"
              :color="progressColors"
            />
            <div class="module-bars">
              <div v-for="mod in progress.modules" :key="mod.module" class="module-bar">
                <div class="module-bar-label">
                  <span>{{ mod.label }}</span>
                  <span>{{ mod.points }}分</span>
                </div>
                <el-progress
                  :percentage="Math.min(Math.round(mod.points / progress.yearly_target * 100), 100)"
                  :stroke-width="10"
                  :color="mod.color"
                  :show-text="false"
                />
              </div>
            </div>
          </div>
          <el-empty v-else description="年度进度看板已就绪，数据加载中…" :image-size="60" />
        </template>
      </el-skeleton>
    </el-card>

    <!-- 每日金句 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>📖 每日金句</span>
          <el-button size="small" text @click="refreshQuote">🔄 换一句</el-button>
        </div>
      </template>
      <div class="quote-body" v-if="dailyQuote">
        <div v-if="dailyQuote.is_paragraph" class="quote-title">
          {{ dailyQuote.short_title || dailyQuote.content.slice(0, 50) + '...' }}
        </div>
        <div v-else class="quote-content">{{ dailyQuote.content }}</div>
        <div class="quote-author" v-if="dailyQuote.author">— {{ dailyQuote.author }}</div>
        <el-tag size="small">{{ dailyQuote.language }}</el-tag>
      </div>
      <el-empty v-else description="暂无金句" :image-size="60" />
    </el-card>
    <el-dialog v-model="showQuoteFull" title="金句详情" width="500px">
      <div class="full-quote-content">{{ dailyQuote?.content }}</div>
      <div v-if="dailyQuote?.author" class="full-quote-author">— {{ dailyQuote.author }}</div>
      <div v-if="dailyQuote?.source" class="full-quote-source">📎 {{ dailyQuote.source }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, WarningFilled } from '@element-plus/icons-vue'
import { getGoalList } from '@/modules/goals/api/goalApi'
import { getTodayPending } from '@/modules/inbox/api/inboxApi'
import { getDueReminders, createQuickReaderInteraction, getRecentReaderInteractions } from '@/modules/relation/api/relationshipApi'
import { INTERACTION_TYPE_OPTIONS, ENERGY_OPTIONS } from '@/modules/relation/types/relationshipTypes'
import type { ReaderInteraction } from '@/modules/relation/types/relationshipTypes'
import { getYearlyOverview } from '@/modules/summary/api/summaryApi'
import { getWeekCount } from '@/modules/temporal/api/temporalApi'
import { getRandomRetro } from '@/modules/summary/api/summaryApi'
import { getRandomQuote } from '@/modules/toolkit/api/quoteApi'
import type { InboxItem } from '@/modules/inbox/types/inboxTypes'
import type { Quote } from '@/modules/toolkit/types/quoteTypes'

interface AlertItem {
  type: 'danger' | 'warning'
  text: string
}

interface ProgressData {
  total_points: number
  yearly_target: number
  progress_percent: number
  modules: { module: string; label: string; color: string; points: number }[]
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
  weeklyExpense: null as string | null,
})

const pendingItems = ref<InboxItem[]>([])
const alerts = reactive<AlertItem[]>([])
const progress = ref<ProgressData | null>(null)
const retroItem = ref<RetroItem | null>(null)
const dailyQuote = ref<Quote | null>(null)
const showQuoteFull = ref(false)

// ─── 快速读者互动 ───
const quickContent = ref('')
const quickReader = ref('')
const quickType = ref('comment')
const quickEnergy = ref(1)
const showAdvanced = ref(false)
const savingQuick = ref(false)
const recentInteractions = ref<ReaderInteraction[]>([])
const loadingRecent = ref(true)

// 从 localStorage 恢复默认值
const savedDefaults = JSON.parse(localStorage.getItem('interaction_defaults') || '{}')
if (savedDefaults.type) quickType.value = savedDefaults.type
if (savedDefaults.energy) quickEnergy.value = savedDefaults.energy

// ─── 独立加载状态 ───
const loadingGoals = ref(true)
const loadingDiary = ref(true)
const loadingInbox = ref(true)
const loadingAlerts = ref(true)
const loadingProgress = ref(true)
const loadingRetro = ref(true)

const progressColors = [
  { color: '#F97316', percentage: 25 },
  { color: '#F59E0B', percentage: 50 },
  { color: '#10B981', percentage: 75 },
  { color: '#3B82F6', percentage: 100 },
]

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

async function fetchDiaryCount() {
  loadingDiary.value = true
  try {
    const res = await getWeekCount()
    stats.diaryCount = res.data.count
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

async function fetchProgress() {
  loadingProgress.value = true
  try {
    const year = new Date().getFullYear()
    const res = await getYearlyOverview({ year })
    const data = res.data
    if (data) {
      progress.value = {
        total_points: data.total_points,
        yearly_target: data.yearly_target,
        progress_percent: data.progress_percent,
        modules: data.modules ?? [],
      }
    }
  } catch {
    // noop
  } finally {
    loadingProgress.value = false
  }
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

async function refreshQuote() {
  try {
    const res = await getRandomQuote()
    dailyQuote.value = res.data as Quote
  } catch {
    dailyQuote.value = null
  }
}

// ─── 快速读者互动 ───
async function quickSave() {
  if (!quickContent.value.trim()) return
  savingQuick.value = true
  try {
    await createQuickReaderInteraction({
      content: quickContent.value,
      interaction_type: quickType.value,
      energy_score: quickEnergy.value,
      reader_name: quickReader.value || '匿名读者',
    })
    ElMessage.success(`已记录 +${quickEnergy.value} 能量`)
    quickContent.value = ''
    quickReader.value = ''
    // 持久化用户偏好
    localStorage.setItem('interaction_defaults', JSON.stringify({
      type: quickType.value,
      energy: quickEnergy.value,
    }))
    await fetchRecentInteractions()
  } catch {
    ElMessage.error('记录失败')
  } finally {
    savingQuick.value = false
  }
}

async function fetchRecentInteractions() {
  loadingRecent.value = true
  try {
    const res = await getRecentReaderInteractions()
    recentInteractions.value = res.data
  } catch {
    recentInteractions.value = []
  } finally {
    loadingRecent.value = false
  }
}

async function refreshAll() {
  await Promise.all([
    fetchGoalStats(),
    fetchPendingItems(),
    fetchAlerts(),
    fetchProgress(),
    fetchDiaryCount(),
    fetchRandomRetro(),
    refreshQuote(),
    fetchRecentInteractions(),
  ])
}

onMounted(() => {
  // 各自独立加载，不互相阻塞
  fetchGoalStats()
  fetchDiaryCount()
  fetchPendingItems()
  fetchAlerts()
  fetchProgress()
  fetchRandomRetro()
  refreshQuote()
  fetchRecentInteractions()
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

.quick-interaction-card {
  :deep(.el-card__body) {
    padding: 16px 20px;
  }
}

.quick-input-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.advanced-options {
  padding: 8px 0;
  .full-width { width: 100%; }
}

.quick-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quick-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: auto;
}

.recent-interactions {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-light);
}

.recent-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;

  .recent-date {
    color: var(--el-text-color-secondary);
    min-width: 32px;
  }
  .recent-name {
    font-weight: 500;
    min-width: 48px;
  }
  .recent-content {
    flex: 1;
    color: var(--el-text-color-regular);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.energy-badge {
  font-size: 12px;
  font-weight: 600;
  color: #10B981;
  min-width: 24px;
  text-align: right;
}

.quote-body {
  padding: 4px 0;
}
.quote-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-color-primary);
  cursor: pointer;
  line-height: 1.5;
}
.quote-content {
  font-size: 14px;
  color: #1F2937;
  line-height: 1.6;
  white-space: pre-wrap;
}
.quote-author {
  margin-top: 6px;
  font-size: 13px;
  color: #6B7280;
  font-style: italic;
}
.full-quote-content {
  font-size: 16px;
  line-height: 1.8;
  white-space: pre-wrap;
  margin-bottom: 12px;
}
.full-quote-author {
  font-size: 14px;
  color: #6B7280;
  font-style: italic;
  margin-bottom: 4px;
}
.full-quote-source {
  font-size: 13px;
  color: #9CA3AF;
}
</style>
