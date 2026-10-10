<template>
  <div class="summary-dashboard" v-loading="store.loading">
    <!-- 季度决策工作台已从页面撤下（2026-09-23）：
         三张洞察卡片（未达标 / 环比 / 最需关注）只复述数据、不产生决策信息，
         位置让给每日金句。组件、store 方法、后端接口全部原样保留，
         要接回只需取消下面这行注释。 -->
    <!-- <QuarterlyDecisionCards /> -->

    <!-- 两个回顾出口并排（v3.60.11）：
         金句 = 摘录里「被推得最少」的一句（长度不超上限、冷落优先而非纯随机；
         上限是「系统管理 → 系统设置 → 摘录金句池」里的配置项，v3.60.12 起可调）；
         旧结论 = 问答库里标过采纳 / 写过备注的一条判断。
         在此之前只有金句有出口、问答库没有，于是内容被手动拷贝到摘录一侧 —— 这里把两条出口对齐。 -->
    <div class="recall-row">
      <el-card shadow="hover" class="chart-card recall-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">📖 每日金句</span>
            <el-button size="small" text @click="refreshQuote">🔄 换一句</el-button>
          </div>
        </template>
        <div class="quote-card-body" v-if="dailyQuote">
          <div class="quote-content">{{ dailyQuote.content }}</div>
          <div class="quote-author" v-if="dailyQuote.author">— {{ dailyQuote.author }}</div>
          <el-tag size="small">{{ dailyQuote.language }}</el-tag>
        </div>
        <div v-else class="recall-empty">
          还没有能上卡的摘录 —— 去
          <el-button link type="primary" @click="$router.push('/toolkit/quotes')">摘录管理</el-button>
          加一条，或到「系统设置 → 摘录金句池」把长度上限调大。
        </div>
      </el-card>

      <el-card
        shadow="hover"
        class="chart-card recall-card"
        :class="{ 'is-clickable': !!conclusion }"
        @click="openConclusion"
      >
        <template #header>
          <div class="card-header">
            <span class="card-title">🧠 一条旧结论</span>
            <div class="recall-actions">
              <!-- 出口（v3.60.13）：这张卡原先只能看、不能点 ——
                   卡上只有结论摘要，判断依据与完整回答都在问答库里，却没有任何路径过去。 -->
              <el-button v-if="conclusion" size="small" text type="primary" @click.stop="openConclusion">
                看全文 →
              </el-button>
              <el-button size="small" text @click.stop="refreshConclusion">🔄 换一条</el-button>
            </div>
          </div>
        </template>

        <div class="quote-card-body" v-if="conclusion">
          <!-- 出处：后端一直在下发 `scene_name` / `topic_title`，卡片从未渲染过 ——
               实测这两项 100% 有值（11/11 主题有标题、有场景），等于白扔。 -->
          <div class="conclusion-src">
            <span class="src-scene">🗂 {{ conclusion.scene_name || '未分类' }}</span>
            <template v-if="conclusion.topic_title">
              <span class="src-sep">·</span>
              <span class="src-topic">{{ conclusion.topic_title }}</span>
            </template>
          </div>
          <div class="conclusion-q">{{ conclusion.question }}</div>

          <!-- 判断依据：`note` 型下你的结论可能只有几个字（实测那条 4 个字：「不够清晰」），
               没有这段 AI 回答就完全读不出「当时在判断什么」。
               `answer` 型下 `conclusion` 本身就是这段（后端 docstring 已说明）⇒ 不重复渲染。 -->
          <div v-if="conclusion.conclusion_source === 'note'" class="conclusion-block">
            <div class="block-label">🤖 {{ conclusion.ai }} 当时的回答</div>
            <div class="block-text">{{ conclusion.ai_excerpt }}</div>
            <div v-if="conclusion.ai_excerpt_truncated" class="block-more">
              原文共 {{ conclusion.answer_len }} 字，这里只放了开头 —— 点开看全文
            </div>
          </div>

          <div
            class="conclusion-block"
            :class="{ 'is-your-note': conclusion.conclusion_source === 'note' }"
          >
            <div class="block-label">
              {{ conclusion.conclusion_source === 'note' ? '✍️ 你的结论' : `🤖 ${conclusion.ai} 回答的开头` }}
            </div>
            <div class="block-text">{{ conclusion.conclusion }}</div>
            <div
              v-if="conclusion.conclusion_source === 'answer' && conclusion.ai_excerpt_truncated"
              class="block-more"
            >
              原文共 {{ conclusion.answer_len }} 字，这里只放了开头 —— 点开看全文
            </div>
          </div>

          <div class="conclusion-meta">
            <el-tag size="small" :type="conclusion.conclusion_source === 'note' ? 'success' : 'info'">
              {{ conclusion.conclusion_source === 'note' ? '你写的结论' : 'AI 回答片段' }}
            </el-tag>
            <!-- 「不采用」这类标记打的是**当时那条 AI 回答**，不是卡上这句结论；
                 不解释会被读成「都标不采用了怎么还推给我」 -->
            <el-tooltip v-if="conclusion.verdict" :content="VERDICT_TIP" placement="top">
              <el-tag size="small">{{ conclusion.verdict }}</el-tag>
            </el-tooltip>
            <span class="conclusion-days">{{ askedDate }} · {{ conclusion.days_ago }} 天前</span>
          </div>

          <!-- 池子太瘦：「换一条」转两下就回原处，界面上得说出为什么（实测库里只有 2 条能进池） -->
          <div v-if="conclusion.pool_size <= 3" class="pool-thin">
            池中只有 <b>{{ conclusion.pool_size }}</b> 条能上这张卡 —— 「换一条」很快会转回来。去
            <el-button link type="primary" @click.stop="$router.push('/toolkit/ask-library/review')">
              回顾
            </el-button>
            给更多回答补一句结论。
          </div>
        </div>
        <div v-else class="recall-empty">
          问答库里还没有标过结论 —— 标「采纳」或写一句备注，它就会出现在这里。去
          <el-button link type="primary" @click.stop="$router.push('/toolkit/ask-library/review')">回顾一条</el-button>
        </div>
      </el-card>
    </div>

    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>📊 综合进度看板</h2>
        <el-tag size="small" type="success" effect="plain">年度目标 {{ YEARLY_TARGET }} 点</el-tag>
      </div>
      <div class="header-actions">
        <el-select
          v-model="store.currentYear"
          size="small"
          style="width: 100px"
          @change="store.switchYear"
        >
          <el-option
            v-for="y in store.availableYears"
            :key="y"
            :label="`${y}年`"
            :value="y"
          />
        </el-select>
        <el-button :icon="Refresh" size="small" @click="store.fetchAll" />
      </div>
    </div>

    <!-- 进度环 + 模块贡献 + 雷达图 -->
    <el-row :gutter="16" class="summary-top-row">
      <!-- 年度进度环 -->
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <template #header><span class="card-title">🎯 年度进度</span></template>
          <div class="ring-wrapper">
            <ProgressRing
              :value="overview?.total_points ?? 0"
              :max="YEARLY_TARGET"
              :label="`${overview?.year || currentYear}年`"
            />
          </div>
        </el-card>
      </el-col>

      <!-- 各模块贡献 -->
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <template #header>
            <div class="card-header-flex">
              <span class="card-title">📊 各模块贡献</span>
              <span v-if="overview?.total_points != null" class="year-progress-badge">
                {{ overview.total_points }} / {{ overview.yearly_target }} 分
                ({{ overview.progress_percent }}%)
              </span>
            </div>
          </template>
          <ModuleBar
            v-if="overview?.modules"
            :modules="overview.modules"
            :show-percent="true"
            @view-module="handleViewModule"
          />
          <div v-else class="chart-empty">暂无数据</div>
        </el-card>
      </el-col>

      <!-- 雷达图 -->
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <template #header>
          <div class="card-header-flex">
            <span class="card-title">📡 七维平衡</span>
            <el-button size="small" text type="primary" @click="openRadarConfig">
              <el-icon style="margin-right:2px"><Setting /></el-icon>配置
            </el-button>
          </div>
        </template>
          <!-- v-show 保持组件常驻，避免 v-if 卸载/重挂载导致 ECharts DOM 竞态 -->
          <RadarChart v-show="!!store.radarData" />
          <div v-if="!store.radarData" class="chart-empty">暂无数据</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 月度趋势图 -->
    <el-card shadow="hover" class="chart-card full-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📈 月度进度趋势</span>
          <div class="card-hint">堆叠柱状图展示各模块月度贡献，红线为月目标</div>
        </div>
      </template>
      <TrendChart v-if="store.trendData.length" />
      <div v-else class="chart-empty" style="height:200px;display:flex;align-items:center;justify-content:center">
        暂无趋势数据
      </div>
    </el-card>

    <!-- 身体-状态关联（暂隐藏，等待数据接口就绪后启用） -->
    <!-- <BodyMindChart /> -->

    <!-- 月度详情表格 -->
    <el-card shadow="hover" class="chart-card full-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📅 月度明细</span>
          <div class="header-actions">
            <el-button size="small" @click="openYearDetail">📆 年度明细</el-button>
            <el-button size="small" @click="showMonthModal = true">查看本月详情</el-button>
          </div>
        </div>
      </template>
      <el-table :data="monthTableData" stripe size="small" style="width: 100%" @row-click="handleRowClick">
        <el-table-column label="月份" min-width="60">
          <template #default="{ row }">{{ row.month }}月</template>
        </el-table-column>
        <el-table-column label="总进度" min-width="80" sortable prop="total_points">
          <template #default="{ row }">
            <span :class="row.total_points >= row.month_target ? 'text-success' : 'text-warning'">
              {{ row.total_points.toFixed(1) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="目标" min-width="60" prop="month_target" />
        <el-table-column label="财富" min-width="60" prop="wealth" />
        <el-table-column label="健康" min-width="60" prop="health" />
        <el-table-column label="时间投入" min-width="70" prop="times" />
        <el-table-column label="阅读" min-width="60" prop="book" />
        <el-table-column label="小确幸" min-width="60" prop="sugar" />
        <el-table-column label="旅行" min-width="60" prop="travel" />
        <el-table-column label="文字" min-width="60" prop="words" />
        <el-table-column label="达成率" width="80" sortable>
          <template #default="{ row }">
            <span :style="{ color: row.rate >= 80 ? '#52c41a' : row.rate >= 50 ? '#faad14' : '#f5222d', fontWeight: 600 }">
              {{ row.rate }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 月度详情弹窗 -->
    <!-- 年度明细弹窗 -->
    <el-dialog v-model="showYearModal" title="📆 年度明细" width="960" append-to-body>
      <el-table :data="yearRows" v-loading="yearLoading" stripe size="small" max-height="420" style="width: 100%">
        <el-table-column v-for="col in YEAR_COLUMNS" :key="col.key" :label="col.label" :prop="col.key"
          align="right" :min-width="col.width" />
        <el-table-column label="达成率" min-width="90" align="right" fixed="right">
          <template #default="{ row }">
            <span :class="row.progress_percent >= 100 ? 'text-success' : row.progress_percent >= 50 ? 'text-primary' : 'text-warning'">
              {{ row.progress_percent }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <MonthlyModal
      v-model:visible="showMonthModal"
      :year="store.currentYear"
      :month="store.currentMonth"
      @view-module="handleViewModule"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getRadarConfig, saveRadarConfig as apiSaveRadarConfig, getRadarConfigHistory, getYearlyDetail } from '../api/summaryApi'
import { useSummaryStore } from '../stores/summaryStore'
import { YEARLY_TARGET } from '../types/summaryTypes'
import QuarterlyDecisionCards from '../components/QuarterlyDecisionCards.vue'
import ProgressRing from '../components/ProgressRing.vue'
import ModuleBar from '../components/ModuleBar.vue'
import RadarChart from '../components/RadarChart.vue'
import TrendChart from '../components/TrendChart.vue'
import MonthlyModal from '../components/MonthlyModal.vue'
import BodyMindChart from '../components/BodyMindChart.vue'
import { getNextQuote } from '@/modules/toolkit/api/quoteApi'
import { getNextConclusion } from '@/modules/toolkit/api/askLibraryApi'
import type { AskConclusionItem } from '@/modules/toolkit/api/askLibraryApi'
import type { Quote } from '@/modules/toolkit/types/quoteTypes'

const store = useSummaryStore()
const router = useRouter()
const currentYear = computed(() => store.currentYear)
const overview = computed(() => store.overview)
const showMonthModal = ref(false)

// ─── 年度明细 ───
const YEAR_COLUMNS = [
  { key: 'year', label: '年份', width: 70 },
  { key: 'total_points', label: '总进度', width: 80 },
  { key: 'yearly_target', label: '目标', width: 70 },
  { key: 'wealth', label: '财富', width: 70 },
  { key: 'health', label: '健康', width: 70 },
  { key: 'times', label: '时间投入', width: 85 },
  { key: 'book', label: '阅读', width: 70 },
  { key: 'sugar', label: '小确幸', width: 70 },
  { key: 'travel', label: '旅行', width: 70 },
  { key: 'words', label: '文字', width: 70 },
]
const showYearModal = ref(false)
const yearRows = ref<Array<Record<string, any>>>([])
const yearLoading = ref(false)

async function openYearDetail() {
  showYearModal.value = true
  if (yearRows.value.length) return
  yearLoading.value = true
  try {
    const res = await getYearlyDetail()
    yearRows.value = res.data.years || []
  } catch {
    ElMessage.error('获取年度明细失败')
  } finally {
    yearLoading.value = false
  }
}
const dailyQuote = ref<Quote | null>(null)
const conclusion = ref<AskConclusionItem | null>(null)

// ─── 七维平衡封顶配置 ───
const CONFIG_ITEMS = [
  { key: 'wealth_max', label: '财富', unit: '万元' },
  { key: 'health_max', label: '健康', unit: '万步' },
  { key: 'times_max', label: '时间投入', unit: '小时/30' },
  { key: 'words_max', label: '文字记录', unit: '万字' },
  { key: 'sugar_max', label: '小确幸', unit: '级' },
  { key: 'travel_max', label: '旅行', unit: '次' },
  { key: 'book_max', label: '阅读', unit: '本' },
]
const configItems = CONFIG_ITEMS
const configVisible = ref(false)
const savingConfig = ref(false)
const configForm = reactive<Record<string, number | string>>({
  wealth_max: 10, health_max: 80, times_max: 80,
  words_max: 20, sugar_max: 50, travel_max: 20, book_max: 20, note: '',
})
const configHistory = ref<Array<Record<string, any>>>([])

async function openRadarConfig() {
  try {
    const res = await getRadarConfig()
    for (const item of CONFIG_ITEMS) {
      if (res.data[item.key] != null) configForm[item.key] = res.data[item.key]
    }
    configForm.note = ''
    configVisible.value = true
    const his = await getRadarConfigHistory()
    configHistory.value = his.data || []
  } catch {
    ElMessage.error('获取配置失败')
  }
}

async function saveRadarConfig() {
  savingConfig.value = true
  try {
    await apiSaveRadarConfig({ ...configForm })
    ElMessage.success('封顶配置已保存')
    configVisible.value = false
    await store.fetchRadar()  // 立即刷新雷达图
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingConfig.value = false
  }
}

/**
 * 金句：改走 `next/`（短句池 + 冷落优先），不再走 `random/`。
 *
 * ⚠️ 池为空时后端返回 **204**，此时 `res.data` 是空串 `''`（不是 null）——
 * 直接赋值会让 `v-if="dailyQuote"` 判真、把空串当成一条金句渲染出来。所以这里显式判类型。
 */
async function refreshQuote() {
  try {
    const res = await getNextQuote()
    const data = res.data
    dailyQuote.value = data && typeof data === 'object' ? (data as Quote) : null
  } catch {
    dailyQuote.value = null
  }
}

/**
 * 一条旧结论：问答库里「标过采纳 / 写过备注」的一条回答。
 * 库里还没有任何结论时后端返回 **200 + null**（这不是错误），照实显示引导文案。
 */
async function refreshConclusion() {
  try {
    const res = await getNextConclusion()
    conclusion.value = (res.data as AskConclusionItem) ?? null
  } catch {
    conclusion.value = null
  }
}

/**
 * 「不采用」这类标记打的是**当时那条 AI 回答**，不是卡上这句结论 ——
 * 卡上不解释，会被读成「都标不采用了怎么还推给我」。
 */
const VERDICT_TIP = '这条标记打在当时那条 AI 回答上，不是打在你写的结论上'

/** `asked_at` 是带时区的 ISO 串：直接切片取日期，不 `new Date()`（避免两把尺子） */
const askedDate = computed(() => {
  const iso = conclusion.value?.asked_at || ''
  return iso.length >= 10 ? iso.slice(0, 10) : ''
})

/**
 * 打开这条结论的全文：落到问答库「回顾」页，并把抽屉定位到**这一条回答**。
 *
 * 卡上只放得下摘要（实测库里的 AI 回答 1045~2696 字），判断依据与全文都在那边。
 * 带上 `answer` 而不只是 `topic`：一个主题下常挂多条回答，
 * 只给主题的话用户还得自己在一串回答里找——那等于没解决「点不开」。
 */
function openConclusion() {
  const c = conclusion.value
  if (!c) return
  router.push({
    path: '/toolkit/ask-library/review',
    query: { topic: String(c.topic_id), answer: String(c.id) },
  })
}

const monthTableData = computed(() => {
  return store.trendData.map(d => ({
    ...d,
    total_points: d.total_points,
    rate: d.month_target > 0 ? Math.round(d.total_points / d.month_target * 100) : 0,
  }))
})

function handleViewModule(module: string, year?: number, month?: number) {
  store.fetchModuleDetail(module, year, month)
}

function handleRowClick(row: { month: number }) {
  store.currentMonth = row.month
  showMonthModal.value = true
}

onMounted(() => {
  store.fetchAll()
  refreshQuote()
  refreshConclusion()
})
</script>

<style scoped>
.summary-dashboard {
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-left h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}


/* 图表卡片 */
.charts-row {
  margin-bottom: 16px;
}

.chart-card {
  border: none;
  border-radius: 10px;
  margin-bottom: 16px;
}
.chart-card :deep(.el-card__body) {
  padding: 12px 16px 16px;
}

/* 顶部三列等高卡片 */
.summary-top-row {
  margin-bottom: 16px;
}
.summary-top-row .el-col {
  display: flex;
}
.summary-card {
  border: none;
  border-radius: 10px;
  flex: 1;
}
.summary-card :deep(.el-card__body) {
  padding: 12px 16px 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-hint {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.full-card {
  margin-bottom: 16px;
}

.ring-wrapper {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

.chart-empty {
  text-align: center;
  color: #9CA3AF;
  font-size: 13px;
  padding: 40px 0;
}

.text-success {
  color: #10B981;
  font-weight: 600;
}
.text-warning {
  color: #F59E0B;
  font-weight: 600;
}

/* 两个回顾出口并排（金句 / 一条旧结论）—— 窄屏自动堆叠 */
.recall-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}
.recall-row .recall-card {
  flex: 1 1 0;
  min-width: 0;
  margin-bottom: 0;
}
@media (max-width: 900px) {
  .recall-row { flex-direction: column; }
  .recall-row .recall-card { margin-bottom: 16px; }
}
.recall-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 13px;
  color: #9CA3AF;
}
/* ─── 一条旧结论（v3.60.13）：卡上要能读出「当时在判断什么」 ───
   本样式块是纯 CSS（无 lang="scss"），只能用扁平选择器，别写嵌套。 */
.recall-card.is-clickable { cursor: pointer; }
.recall-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
/* 出处行：场景 · 主题。主题可能很长 ⇒ 省略号收尾，不换行把卡撑高 */
.conclusion-src {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 5px;
  font-size: 12px;
  color: #9CA3AF;
  white-space: nowrap;
  overflow: hidden;
}
.conclusion-src .src-scene,
.conclusion-src .src-sep { flex: none; }
.conclusion-src .src-topic { overflow: hidden; text-overflow: ellipsis; }
.conclusion-q {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.conclusion-block {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}
/* 你自己写的那句是这张卡的主角，给一层可辨识的底色 */
.conclusion-block.is-your-note { background: var(--el-color-success-light-9); }
.conclusion-block .block-label {
  margin-bottom: 4px;
  font-size: 12px;
  color: #6B7280;
}
.conclusion-block .block-text {
  font-size: 13px;
  line-height: 1.7;
  color: #1F2937;
  white-space: pre-wrap;
  /* 卡内滚动，不把卡撑高 —— 这里是两列并排，一张卡变高会带着整行一起变高 */
  max-height: 96px;
  overflow-y: auto;
}
.conclusion-block .block-more {
  margin-top: 4px;
  font-size: 12px;
  color: #9CA3AF;
}
/* 池子太瘦：「换一条」转两下就回原处，界面上得说出为什么 */
.pool-thin {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px;
  line-height: 1.8;
  color: #9CA3AF;
}
.pool-thin b { color: #D97706; }
.conclusion-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.conclusion-days {
  font-size: 12px;
  color: #9CA3AF;
}

.quote-card-body {
  padding: 8px 0;
}
.quote-content {
  font-size: 14px;
  color: #1F2937;
  line-height: 1.6;
  white-space: pre-wrap;
  /* 长度上限放开成可配置后（v3.60.12），长摘录会**全文**上卡 ——
     卡内滚动而不是把卡片撑高：这里是两列并排布局，一张卡变高会带着整行一起变高，
     旁边那张就被拉出一片空白。约 8 行的可视高度，超出自己滚。 */
  max-height: 180px;
  overflow-y: auto;
}
.quote-author {
  margin-top: 6px;
  font-size: 13px;
  color: #6B7280;
  font-style: italic;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.card-header-flex {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.year-progress-badge {
  font-size: 12px;
  font-weight: 600;
  color: #1F2937;
  background: #F3F4F6;
  padding: 2px 10px;
  border-radius: 12px;
}
.config-hint {
  font-size: 12px;
  color: #6B7280;
  margin-bottom: 12px;
}
.config-unit {
  margin-left: 8px;
  font-size: 12px;
  color: #9CA3AF;
}
.history-divider {
  margin: 4px 0 8px;
}
.history-collapse {
  max-height: 220px;
  overflow-y: auto;
}
.history-time {
  font-size: 12px;
  color: #4B5563;
  margin-right: 6px;
}
.history-tag {
  margin-right: 6px;
}
.history-note {
  font-size: 12px;
  color: #6B7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}
.history-detail {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px 16px;
  padding: 4px 8px;
}
.history-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}
.history-label {
  color: #6B7280;
}
.history-empty {
  font-size: 12px;
  color: #9CA3AF;
  text-align: center;
  padding: 8px 0;
}
</style>
