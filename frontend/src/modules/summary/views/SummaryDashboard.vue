<template>
  <div class="summary-dashboard" v-loading="store.loading">
    <!-- 季度决策工作台已从页面撤下（2026-09-23）：
         三张洞察卡片（未达标 / 环比 / 最需关注）只复述数据、不产生决策信息，
         位置让给每日金句。组件、store 方法、后端接口全部原样保留，
         要接回只需取消下面这行注释。 -->
    <!-- <QuarterlyDecisionCards /> -->

    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <!-- 菜单项已撤（v3.63.14）⇒ 入口挪到仪表盘页头，这里补回程。
             写死 `/dashboard` 而不用 router.back()：刷新 / 直达 / 分享链接下没有上一条。 -->
        <el-button size="small" @click="$router.push('/dashboard')">
          <el-icon><ArrowLeft /></el-icon> 仪表盘
        </el-button>
        <h2>📊 综合进度看板</h2>
        <!--
          原来这里挂「年度目标 400 点」。
          v3.62.43 拆掉总分后改成口径说明 —— 这一年到底在量什么，先说清。
        -->
        <el-tag size="small" type="success" effect="plain">口径：覆盖率 + 强度</el-tag>
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
        <!--
          年度明细入口（原来在「月度明细」表头里，那张表删掉后搬到这里）。
          ⚠️ 它是**另一件事**：逐年的覆盖率对照，回答「哪一年开始松了」。
        -->
        <el-button size="small" @click="openYearDetail">📆 年度明细</el-button>
      </div>
    </div>

    <!-- 雷达（覆盖率 / 达成率）+ 七维覆盖率与强度 -->
    <el-row :gutter="16" class="summary-top-row">
      <el-col :xs="24" :md="10">
        <el-card shadow="hover" class="summary-card">
          <template #header>
            <div class="card-header-flex">
              <span class="card-title">📡 七维平衡</span>
              <div class="radar-head-actions">
                <!--
                  两种镜片、同一份数据（后端一次给全，切换不发请求）：
                  覆盖率 = 我记了多少（客观）；达成率 = 相对每轴封顶（保留配置的意义）
                -->
                <el-radio-group v-model="radarBasis" size="small">
                  <el-radio-button value="coverage">覆盖率</el-radio-button>
                  <el-radio-button value="achievement">达成率</el-radio-button>
                </el-radio-group>
                <el-button size="small" text type="primary" @click="openRadarConfig">
                  <el-icon style="margin-right:2px"><Setting /></el-icon>配置
                </el-button>
              </div>
            </div>
          </template>
          <!-- v-show 保持组件常驻，避免 v-if 卸载/重挂载导致 ECharts DOM 竞态 -->
          <RadarChart v-show="!!store.radarData" :basis="radarBasis" />
          <div v-if="!store.radarData" class="chart-empty">暂无数据</div>

          <!-- 最短板一句话：雷达看形状，这句给结论 -->
          <div v-if="weakestText" class="weakest-line">
            <span class="weakest-tag">最短板</span>
            <span class="weakest-body">{{ weakestText }}</span>
          </div>

          <!--
            达成率为负时必须说出来：雷达几何只能画 0–100%，负值会被压到圆心，
            形状上看是「没做」，实际是「净流出」。不写这一行就是静默误读。
          -->
          <div v-if="radarBasis === 'achievement' && negativeAxes.length" class="neg-line">
            <span class="neg-tag">净流出</span>
            <span class="neg-body">
              {{ negativeAxes.join('；') }} —— 雷达只能画 0–100%，这些轴被压到圆心
            </span>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="14">
        <el-card shadow="hover" class="summary-card">
          <template #header>
            <div class="card-header-flex">
              <span class="card-title">📋 七维覆盖率与强度</span>
              <span class="year-progress-badge">
                {{ overview?.window?.elapsed_days ?? 0 }} 天 /
                {{ overview?.window?.elapsed_months ?? 0 }} 个完整月
              </span>
            </div>
          </template>
          <CoverageTable
            v-if="overview?.modules"
            :modules="overview.modules"
            :weakest-module="overview.weakest?.module"
            @view-module="handleViewModule"
          />
          <div v-else class="chart-empty">暂无数据</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 月度：覆盖率 + 强度 -->
    <el-card shadow="hover" class="chart-card full-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">📈 月度覆盖率与强度</span>
          <div class="card-hint">
            格子里写的是覆盖率（有记录 / 该有的），底色越深 = 强度越高（按行比，跨行不比）。
            点格子看当月明细
          </div>
        </div>
      </template>
      <TrendChart v-if="store.trendData.length" @pick-month="openMonthDetail" />
      <div v-else class="chart-empty" style="height:200px;display:flex;align-items:center;justify-content:center">
        暂无趋势数据
      </div>
    </el-card>

    <!--
      两个回顾出口并排（v3.60.11 起）：金句 + 一条旧结论。
      🔴 v3.63.14 起从**页面顶部挪到底部**：这两张是「回顾读物」，实测各 450px 高，
      把「七维雷达」挤到第 900px 处（可视高度只有 753px）——
      进这一页第一眼看到两段文字，一张数据图都看不到。
      本页要回答的是「这一年我到底在不在动」⇒ 先给图，再给读物。
      金句卡自 v3.63.14 起是共享组件（`QuoteCard`），取数与空态只此一份。
    -->
    <div class="recall-row">
      <QuoteCard shadow="hover" class="chart-card recall-card" />

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

        <div class="conclusion-body" v-if="conclusion">
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


    <!-- 身体-状态关联（暂隐藏，等待数据接口就绪后启用） -->
    <!-- <BodyMindChart /> -->

    <!--
      月度明细表已删除（v3.62.43）。
      它的三列「总进度 / 目标 / 达成率」都是总分口径；改成覆盖率之后，
      数字与上面的热力图**完全重复**，而表格还会让人误以为这些数能加。
      当月明细的入口改到热力图上点格子（同一个 MonthlyModal）。
      原「📆 年度明细」保留在页头下方？不 —— 它现在挂在趋势卡页头，见下。
    -->

    <!-- 月度详情弹窗 -->
    <!-- 年度明细弹窗 -->
    <el-dialog v-model="showYearModal" title="📆 年度明细 · 覆盖率" width="960" append-to-body>
      <div class="config-hint">
        每一格是当年该维度的覆盖率：有记录期数 ÷ 该有的期数。
        <b>0% 不是「没做」，是「没记」</b>——这两件事在业务上完全不同，数值上都是 0。
      </div>
      <el-table :data="yearRows" v-loading="yearLoading" stripe size="small" max-height="420" style="width: 100%">
        <el-table-column v-for="col in YEAR_COLUMNS" :key="col.key" :label="col.label" :prop="col.key"
          align="right" :min-width="col.width" />
        <el-table-column label="当年最短板" min-width="120" align="right" fixed="right">
          <template #default="{ row }">
            <span v-if="row.weakest">{{ row.weakest }} {{ row.weakest_pct }}%</span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!--
      七维平衡 · 封顶配置弹窗。
      ⚠️ v3.60.31 前这里**没有这段模板**：script 里的 openRadarConfig / configForm /
      configHistory / saveRadarConfig 全都写好了，却没有任何 el-dialog 消费它们 ⇒
      点「配置」时请求正常发出、configVisible 被置 true，页面上什么都不出现
      （用户读到的是「按钮坏了」）。**逻辑齐了、渲染层丢了**这类缺陷不报错。
    -->
    <el-dialog v-model="configVisible" title="📡 七维平衡 · 封顶配置" width="660" append-to-body>
      <div class="config-hint">
        下面填的数字是雷达图上这一轴的<b>满格刻度（点）</b>—— 数值越接近它，该维度越接近满格。
        保存后立即生效，并留下一条历史版本（旧版本自动转为「历史」）。
      </div>

      <el-form label-width="88px" size="small">
        <el-form-item v-for="item in configItems" :key="item.key" :label="item.label">
          <el-input-number
            :model-value="Number(configForm[item.key])"
            :min="1"
            :step="1"
            controls-position="right"
            style="width:150px"
            @update:model-value="(v: number | undefined) => (configForm[item.key] = v ?? 1)"
          />
          <span class="config-unit">{{ item.unit }}</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            :model-value="String(configForm.note ?? '')"
            maxlength="200"
            placeholder="为什么改（可不填，历史版本里能看到）"
            @update:model-value="(v: string) => (configForm.note = v)"
          />
        </el-form-item>
      </el-form>

      <el-divider class="history-divider" content-position="left">历史版本</el-divider>
      <div v-if="configHistory.length" class="history-collapse">
        <el-collapse accordion>
          <el-collapse-item v-for="row in configHistory" :key="row.id" :name="String(row.id)">
            <template #title>
              <span class="history-time">{{ (row.created_at || '').slice(0, 16).replace('T', ' ') }}</span>
              <el-tag v-if="row.is_active" type="success" size="small" class="history-tag">生效</el-tag>
              <el-tag v-else type="info" size="small" class="history-tag">历史</el-tag>
              <span class="history-note">{{ row.note || '（无备注）' }}</span>
            </template>
            <div class="history-detail">
              <div v-for="item in configItems" :key="item.key" class="history-row">
                <span class="history-label">{{ item.label }}</span>
                <span>{{ row[item.key] }}</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
      <div v-else class="history-empty">还没有历史版本 —— 保存一次就会出现</div>

      <template #footer>
        <el-button @click="configVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingConfig" @click="saveRadarConfig">保存并生效</el-button>
      </template>
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
import { Refresh, Setting, ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { apiErrorText } from '@/shared/utils/apiError'
import { getRadarConfig, saveRadarConfig as apiSaveRadarConfig, getRadarConfigHistory, getYearlyDetail } from '../api/summaryApi'
import { useSummaryStore } from '../stores/summaryStore'
import QuarterlyDecisionCards from '../components/QuarterlyDecisionCards.vue'
import CoverageTable from '../components/CoverageTable.vue'
import RadarChart from '../components/RadarChart.vue'
import TrendChart from '../components/TrendChart.vue'
import MonthlyModal from '../components/MonthlyModal.vue'
import BodyMindChart from '../components/BodyMindChart.vue'
import type { RadarBasis } from '../types/summaryTypes'
import { getNextConclusion } from '@/modules/toolkit/api/askLibraryApi'
import type { AskConclusionItem } from '@/modules/toolkit/api/askLibraryApi'
import QuoteCard from '@/modules/toolkit/components/QuoteCard.vue'

const store = useSummaryStore()
const router = useRouter()
const currentYear = computed(() => store.currentYear)
const overview = computed(() => store.overview)
const showMonthModal = ref(false)

// ─── 雷达镜片（覆盖率 / 达成率）───
const radarBasis = ref<RadarBasis>('coverage')

/**
 * 最短板一句话
 *
 * 🔴 只说事实，不评价、不给建议：
 *    「292 天里只有 35 天有记录」是事实，「说明你不重视生活」是判断 ——
 *    后者不该由系统代说（管理工具不该替人下结论）。
 */
const weakestText = computed(() => {
  const w = overview.value?.weakest
  if (!w) return ''
  const base = `${w.label}：${w.periods} ${w.period_word}里只有 ${w.covered} ${w.period_word}有记录（${w.coverage_pct}%）`
  if (w.recent_covered === null || w.recent_covered === undefined) return base + '。'
  return `${base}；最近 ${w.recent_periods} 天只记了 ${w.recent_covered} 天。`
})

/**
 * 达成率为负的维度（目前只有财富：净流出）。
 *
 * 文案里的数字全部来自后端 `achievement_pct` / `achievement_target`，
 * 前端不自己算「负多少」——否则又是第二把尺子。
 */
const negativeAxes = computed(() => {
  const mods = overview.value?.modules ?? []
  return mods
    .filter((m) => m.achievement_pct !== null && m.achievement_pct < 0)
    .map((m) => {
      const amount = m.raw_value === null ? '—' : `¥${m.raw_value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      const target = m.achievement_target === null ? '—' : `¥${m.achievement_target.toLocaleString('zh-CN', { minimumFractionDigits: 0 })}`
      return `${m.label} ${amount} ÷ 目标 ${target} = ${m.achievement_pct}%`
    })
})

// ─── 年度明细（覆盖率版）───
const YEAR_COLUMNS = [
  { key: 'year', label: '年份', width: 70 },
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
const conclusion = ref<AskConclusionItem | null>(null)

// ─── 七维平衡封顶配置 ───
/**
 * ⚠️ 这里的数字是**雷达图上该轴的满格刻度（点）**，不是物理量本身。
 * 换算系数来自后端 `summary/constants.py` 的 `CONVERSION_RULES[*].divisor`
 * （`_raw_to_points = 原始值 ÷ divisor`、`indicator.max = *_max`）——
 * 两边同一把尺子，所以单位一律写成「1 点 = N <物理量>」。
 * 千万别写成裸的物理量名（如「小时」）：max=80 会被读成「封顶 80 小时」，
 * 而它实际是 **2400 小时**（80 × 30），差 30 倍且界面上看不出。
 */
const CONFIG_ITEMS = [
  { key: 'wealth_max', label: '财富', unit: '点（1 点 = 1 万元）' },
  { key: 'health_max', label: '健康', unit: '点（1 点 = 1 万步）' },
  { key: 'times_max', label: '时间投入', unit: '点（1 点 = 30 小时）' },
  { key: 'words_max', label: '文字记录', unit: '点（1 点 = 1 万字）' },
  { key: 'sugar_max', label: '小确幸', unit: '点（1 点 = 10 级）' },
  { key: 'travel_max', label: '旅行', unit: '点（1 点 = 1 次）' },
  { key: 'book_max', label: '阅读', unit: '点（1 点 = 1 本）' },
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
  } catch (e) {
    ElMessage.error(apiErrorText(e, '获取配置失败'))
    return
  }
  // 历史单独取：它拉不到**不等于**「配置没取到」，更不该沿用上一次的列表
  // （沿用 ⇒ 弹窗里挂着上一轮的版本记录，看不出是旧的）
  try {
    const his = await getRadarConfigHistory()
    configHistory.value = his.data || []
  } catch (e) {
    configHistory.value = []
    ElMessage.warning(`历史版本没取到：${apiErrorText(e, '请稍后重试')}`)
  }
}

/**
 * 保存封顶配置。
 *
 * ⚠️ 「写配置」与「刷新雷达图」是**两件事**，不能共用一个 try ——
 * 混在一起时刷新失败会被报成「保存失败」，而配置**其实已经写进去了**，
 * 用户会再点一次保存（多留一条历史版本）。
 */
async function saveRadarConfig() {
  savingConfig.value = true
  let saved = false
  try {
    await apiSaveRadarConfig({ ...configForm })
    saved = true
  } catch (e) {
    ElMessage.error(apiErrorText(e, '保存失败'))
  } finally {
    savingConfig.value = false
  }
  if (!saved) return

  ElMessage.success('封顶配置已保存')
  configVisible.value = false
  try {
    await store.fetchRadar()  // 立即刷新雷达图
  } catch {
    ElMessage.warning('配置已保存，但雷达图没刷新成功 —— 刷新页面即可')
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

function handleViewModule(module: string, year?: number, month?: number) {
  store.fetchModuleDetail(module, year, month)
}

/** 热力图点格子 → 打开当月明细（替代已删除的「月度明细」表逐行点击） */
function openMonthDetail(month: number) {
  store.currentMonth = month
  showMonthModal.value = true
}

onMounted(() => {
  store.fetchAll()
  refreshConclusion()   // 金句由共享组件 `<QuoteCard />` 自己取
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

/* 雷达卡底部那句「最短板」—— 形状看雷达，结论看这行 */
.weakest-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 4px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--el-color-warning-light-9);
}
.weakest-tag {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #92400E;
  background: #FDE68A;
}
.weakest-body {
  font-size: 12px;
  line-height: 1.65;
  color: #92400E;
}

.radar-head-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 达成率为负的说明行：雷达画不出来，只能靠文字补齐 */
.neg-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 6px;
  padding: 7px 10px;
  border-radius: 8px;
  background: var(--el-color-danger-light-9);
}
.neg-tag {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-8);
}
.neg-body {
  font-size: 12px;
  line-height: 1.65;
  color: var(--el-color-danger-dark-2);
}

.text-muted {
  color: var(--el-text-color-placeholder);
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

/* 「一条旧结论」卡的内容容器。原名叫 `.quote-card-body`，
   与金句卡共用 —— 金句抽成组件（自带同名类）后改名，免得同名不同义。 */
.conclusion-body {
  padding: 8px 0;
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
