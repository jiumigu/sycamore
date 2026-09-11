<template>
  <div class="decision-tracker">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
    </div>

    <div class="page-header">
      <div class="header-left">
        <h2>🧭 决策追踪器</h2>
        <el-tag size="small" type="warning">长期观察型决策 · 日常记录倾向 · 到期汇总分析</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="fetchTrackers">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>新建决策
        </el-button>
      </div>
    </div>

    <div v-if="bannerItems.length" class="reminder-banner">
      <el-alert
        v-for="(item, i) in bannerItems"
        :key="i"
        :title="item.text"
        :type="item.type"
        :closable="false"
        show-icon
        class="reminder-line"
      />
    </div>

    <el-tabs v-model="activeTab" class="main-tabs">
      <el-tab-pane v-for="tab in TABS" :key="tab.status" :name="tab.status" :label="`${tab.label} (${countOf(tab.status)})`">
        <div v-loading="loading" class="tracker-list">
          <el-card v-for="t in trackersOf(tab.status)" :key="t.id" shadow="hover" class="tracker-card">
            <div class="card-main">
              <div class="topic-row">
                <span class="topic">{{ t.topic }}</span>
                <el-tag :type="statusTagType(t.status)" size="small">{{ t.status }}</el-tag>
                <el-tag v-if="t.status === '观察中' && t.days_left !== undefined" size="small" :type="t.days_left <= 7 ? 'warning' : 'info'" effect="plain">
                  {{ t.days_left >= 0 ? `距结束 ${t.days_left} 天` : '已过观察期' }}
                </el-tag>
              </div>
              <div class="meta-line">
                {{ t.start_date }} ~ {{ t.end_date }} · 已记录 <b>{{ t.record_count ?? 0 }}</b> 次
                <span v-if="t.background" class="bg-text" :title="t.background">{{ t.background }}</span>
              </div>
              <div v-if="t.status === '已决策' || t.status === '已归档'" class="decision-line">
                ✅ 最终决定：<b>{{ t.final_decision }}</b><span v-if="t.decision_date">（{{ t.decision_date }}）</span>
              </div>
              <div v-if="t.status === '已归档'" class="review-line">
                📌 事后回看：{{ t.review_note || '（待补，30 天后回看可填）' }}
              </div>
              <!-- 观察期内刻意封存倾向结论：中途结论会反向影响后续记录与判断，等尘埃落定（已到期/已决策/已归档）再展示 -->
              <div v-if="t.status === '观察中' && previewOf(t.id)?.needs_reminder" class="stale-line">
                <el-tag size="small" type="danger" effect="plain">
                  已 {{ previewOf(t.id)?.stale_days }} 天未记录
                </el-tag>
                <span class="stale-hint">观察期内结论暂不展示，先坚持记录</span>
              </div>
              <div v-else-if="t.status === '观察中' && previewOf(t.id)?.total_records" class="locked-line">
                🔒 倾向结论已封存，观察期结束后展示
              </div>
              <div v-else-if="previewOf(t.id)?.total_records" class="lean-line">
                📈 当前倾向：{{ previewOf(t.id)?.conclusion }}
                <el-tag size="small" effect="plain" :type="leanTagTypeOf(previewOf(t.id)!)">
                  {{ isCustomLean(previewOf(t.id)!) ? '主导加权差' : '强度加权' }} {{ signedScore(previewOf(t.id)?.weighted_score ?? 0) }}
                </el-tag>
              </div>
            </div>
            <div class="card-actions">
              <template v-if="t.status === '观察中'">
                <el-button type="primary" plain size="small" @click="openRecord(t)">
                  <el-icon><EditPen /></el-icon>记录感受
                </el-button>
                <el-button size="small" @click="openExtend(t)">延长观察</el-button>
                <el-button type="danger" link size="small" @click="handleDelete(t)">删除</el-button>
              </template>
              <template v-else-if="t.status === '已到期'">
                <el-button type="primary" size="small" @click="openRecord(t)">📝 补充记录</el-button>
                <el-button size="small" @click="openDetail(t)">查看记录</el-button>
                <el-button type="success" size="small" @click="openReport(t)">📊 生成报告</el-button>
                <el-button type="warning" size="small" @click="openDecide(t)">🎯 做出决定</el-button>
                <el-button size="small" @click="openExtend(t)">延长观察</el-button>
                <el-button type="danger" link size="small" @click="handleDelete(t)">删除</el-button>
              </template>
              <template v-else-if="t.status === '已决策'">
                <el-button size="small" @click="openDetail(t)">查看记录</el-button>
                <el-button size="small" @click="openReport(t)">📊 查看报告</el-button>
                <el-button type="primary" plain size="small" @click="openArchive(t)">归档</el-button>
                <el-button type="danger" link size="small" @click="handleDelete(t)">删除</el-button>
              </template>
              <template v-else>
                <el-button size="small" @click="openDetail(t)">查看记录</el-button>
                <el-button size="small" @click="openReport(t)">📊 查看报告</el-button>
                <el-button size="small" @click="openArchive(t)">补事后回看</el-button>
                <el-button type="danger" link size="small" @click="handleDelete(t)">删除</el-button>
              </template>
            </div>
          </el-card>

          <el-empty v-if="!loading && trackersOf(tab.status).length === 0" :description="emptyText(tab.status)" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建决策 -->
    <el-dialog v-model="createVisible" title="🧭 新建决策追踪" width="520px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="决策主题" prop="topic">
          <el-input v-model="createForm.topic" placeholder="如：这份工作还值得继续吗？" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="观察期限" prop="end_date">
          <el-date-picker
            v-model="createForm.start_date" type="date" placeholder="开始" value-format="YYYY-MM-DD" style="width: 45%" />
          <span class="range-sep">~</span>
          <el-date-picker
            v-model="createForm.end_date" type="date" placeholder="结束（默认 3 个月后）" value-format="YYYY-MM-DD" style="width: 45%" />
        </el-form-item>
        <el-form-item label="决策背景" prop="background">
          <el-input v-model="createForm.background" type="textarea" :rows="3" placeholder="为什么想观察这个决策？（选填）" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="倾向选项">
          <div class="lean-options-editor">
            <div v-for="(_, i) in createForm.lean_options" :key="i" class="lean-option-row">
              <el-input
                v-model="createForm.lean_options[i]" maxlength="20"
                :placeholder="`选项 ${i + 1}，如：想现在买`"
              />
              <el-button type="danger" link @click="createForm.lean_options.splice(i, 1)">删</el-button>
            </div>
            <el-button
              v-if="createForm.lean_options.length < 6" size="small"
              @click="createForm.lean_options.push('')"
            >
              + 添加选项
            </el-button>
            <div class="lean-hint">留空则使用默认三项：想继续 / 不想继续 / 不确定（2–6 项，每项 ≤ 20 字）</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">开始观察</el-button>
      </template>
    </el-dialog>

    <!-- 日常记录 -->
    <el-dialog v-model="recordVisible" title="📝 记录今日感受" width="480px" destroy-on-close>
      <template v-if="current">
        <p class="dialog-topic">{{ current.topic }}</p>
        <div class="record-block">
          <div class="field-label">现在的倾向</div>
          <el-radio-group v-model="recordForm.tendency">
            <el-radio-button v-for="o in currentLeanOptions" :key="o.key" :value="o.key">
              {{ leanMeta(o.key, currentLeanOptions).icon ? leanMeta(o.key, currentLeanOptions).icon + ' ' : '' }}{{ o.label }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="record-block">
          <div class="field-label">具体理由（关键词即可，可留空）</div>
          <el-input v-model="recordForm.reason" type="textarea" :rows="3"
            placeholder="如：需求被卡了一周，感觉自己什么也没推进" maxlength="500" show-word-limit />
        </div>
        <div class="record-block">
          <div class="field-label">情绪强度（1 很弱 → 5 很强，用于加权汇总）</div>
          <el-radio-group v-model="recordForm.intensity">
            <el-radio-button v-for="o in INTENSITY_OPTIONS" :key="o.value" :value="o.value">
              {{ o.value }} {{ o.label }}
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="record-block">
          <div class="field-label">记录日期</div>
          <el-date-picker v-model="recordForm.record_date" type="date" placeholder="记录日期"
            value-format="YYYY-MM-DD" style="width: 100%" />
        </div>
      </template>
      <template #footer>
        <el-button @click="recordVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleAddRecord">保存记录</el-button>
      </template>
    </el-dialog>

    <!-- 记录明细 -->
    <el-dialog v-model="detailVisible" :title="detailTitle" width="720px" destroy-on-close @closed="detailRecords = []">
      <el-table v-loading="detailLoading" :data="detailRecords" size="small" max-height="420">
        <el-table-column prop="record_date" label="日期" width="110" />
        <el-table-column label="倾向" width="110">
          <template #default="{ row }">
            <el-tag :type="tendencyTagType(row.tendency, currentLeanOptions)" size="small">{{ tendencyLabel(row.tendency, currentLeanOptions) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="强度" width="100" align="center">
          <template #default="{ row }">
            <span :style="{ color: intensityColor(row.intensity), fontWeight: 600 }">
              {{ row.intensity }} · {{ intensityLabel(row.intensity) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="理由" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.reason || '（未写理由）' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="70" align="center">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="handleDeleteRecord(row)">删</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!detailLoading && detailRecords.length === 0" description="暂无记录" :image-size="80" />
    </el-dialog>

    <!-- 汇总报告 -->
    <el-dialog v-model="reportVisible" :title="reportTitle" width="860px" destroy-on-close @closed="disposeReportChart">
      <div v-loading="reportLoading" class="report-body">
        <template v-if="report">
          <p class="report-topic">{{ report.tracker.topic }}
            <span class="report-period">{{ report.tracker.start_date }} ~ {{ report.tracker.end_date }}</span>
          </p>

          <div class="stat-row">
            <div class="stat-num">{{ report.total_records }}</div>
            <div class="stat-label">总记录</div>
            <el-divider direction="vertical" />
            <div class="stat-num">{{ report.record_days }}</div>
            <div class="stat-label">覆盖天数</div>
          </div>

          <div class="section-title">📊 倾向统计</div>
          <div v-for="s in report.tendency_stats" :key="s.tendency" class="tendency-bar">
            <span class="tendency-name">{{ s.label }}</span>
            <span class="tendency-track">
              <span class="tendency-fill" :style="{ width: s.percent + '%', background: tendencyColor(s.tendency, reportCols) }" />
            </span>
            <span class="tendency-count">{{ s.count }} 次 · {{ s.percent }}%</span>
          </div>

          <div v-if="report.monthly_trend.length" class="section-title">📈 月度倾向趋势</div>
          <div v-if="report.monthly_trend.length" ref="trendChartRef" class="trend-chart" />

          <div class="section-title">🗂️ 理由明细（按倾向分列）</div>
          <el-row :gutter="12">
            <el-col v-for="col in reportCols" :key="col.key" :span="reasonSpan">
              <div class="reason-col" :style="{ borderTopColor: tendencyColor(col.key, reportCols) }">
                <div class="reason-col-title">{{ col.label }}</div>
                <template v-if="report.reasons[col.key]?.length">
                  <div v-for="(r, i) in report.reasons[col.key]" :key="i" class="reason-item">
                    <div class="reason-meta">{{ r.record_date }}
                      <el-tag size="small" effect="plain" :type="intensityTagType(r.intensity)">
                        {{ r.intensity }} · {{ r.intensity_label }}
                      </el-tag>
                    </div>
                    <div class="reason-text">{{ r.reason }}</div>
                  </div>
                </template>
                <div v-else class="reason-empty">（无）</div>
              </div>
            </el-col>
          </el-row>
        </template>
      </div>
      <template #footer>
        <el-button @click="reportVisible = false">关闭</el-button>
        <el-button v-if="canDecideFromReport" type="warning" @click="decideFromReport">🎯 基于报告做出决定</el-button>
      </template>
    </el-dialog>

    <!-- 做出决定 -->
    <el-dialog v-model="decideVisible" :title="`🎯 做出决定 — ${current?.topic ?? ''}`" width="480px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="最终决定">
          <el-input v-model="decideForm.final_decision" placeholder="如：离职 / 留下 / 暂不动作" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="决定日期">
          <el-date-picker v-model="decideForm.decision_date" type="date" placeholder="选择日期"
            value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="decideVisible = false">取消</el-button>
        <el-button type="warning" :loading="submitting" @click="handleDecide">确认决定</el-button>
      </template>
    </el-dialog>

    <!-- 归档 / 补回看 -->
    <el-dialog v-model="archiveVisible" :title="`📌 归档 — ${current?.topic ?? ''}`" width="520px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="事后回看">
          <el-input v-model="archiveForm.review_note" type="textarea" :rows="4"
            placeholder="现在填或 30 天后补填都行：这个决定做对了吗？有什么新觉察？" maxlength="1000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="archiveVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleArchive">确认归档</el-button>
      </template>
    </el-dialog>

    <!-- 延长观察 -->
    <el-dialog v-model="extendVisible" :title="`⏳ 延长观察 — ${current?.topic ?? ''}`" width="480px" destroy-on-close>
      <p class="extend-tip">当前观察期至 <b>{{ current?.end_date }}</b>。延长后该决策回到「观察中」，可继续日常记录。</p>
      <el-form label-width="90px">
        <el-form-item label="新结束日期">
          <el-date-picker v-model="extendForm.end_date" type="date" placeholder="选择新结束日期"
            value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="extendVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleExtend">延长并继续观察</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { ArrowLeft, Refresh, Plus, EditPen } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getDecisionTrackers, createDecisionTracker, updateDecisionTracker, deleteDecisionTracker,
  getTrackerRecords, createDecisionRecord, deleteDecisionRecord,
  getDecisionReport, getDecisionPreview, decideTracker, archiveTracker,
  INTENSITY_OPTIONS, intensityLabel, intensityColor,
} from '../../api/decisionTrackerApi'
import type {
  DecisionTracker, DecisionRecord, DecisionReport, DecisionPreview, TrackerPreviewItem, Tendency, Intensity,
  LeanOption,
} from '../../api/decisionTrackerApi'
import { DEFAULT_LEAN_OPTIONS, leanMeta } from '../../api/decisionTrackerApi'

const TABS = [
  { status: '观察中', label: '追踪中' },
  { status: '已到期', label: '已到期' },
  { status: '已决策', label: '已决策' },
  { status: '已归档', label: '归档' },
] as const

function toLocalISO(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function todayISO(offsetDays = 0): string {
  // 用本地时间拼装，避免 toISOString() 的 UTC 偏移（UTC+8 下凌晨会算成前一天）
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return toLocalISO(d)
}

const loading = ref(false)
const submitting = ref(false)
const activeTab = ref('观察中')
const trackers = ref<DecisionTracker[]>([])

const createVisible = ref(false)
const recordVisible = ref(false)
const detailVisible = ref(false)
const reportVisible = ref(false)
const decideVisible = ref(false)
const archiveVisible = ref(false)
const extendVisible = ref(false)

const createFormRef = ref<FormInstance>()
const current = ref<DecisionTracker | null>(null)

const createForm = reactive({
  topic: '', start_date: todayISO(), end_date: todayISO(90), background: '',
  lean_options: [] as string[],
})
const createRules: FormRules = {
  topic: [{ required: true, message: '请填写决策主题', trigger: 'blur' }],
  end_date: [{ required: true, message: '请选择观察结束日期', trigger: 'change' }],
}
const recordForm = reactive<{ tendency: Tendency; reason: string; intensity: Intensity; record_date: string }>({
  tendency: 'uncertain', reason: '', intensity: 3, record_date: todayISO(),
})
const decideForm = reactive({ final_decision: '', decision_date: todayISO() })
const archiveForm = reactive({ review_note: '' })
const extendForm = reactive({ end_date: '' })

const detailRecords = ref<DecisionRecord[]>([])
const detailLoading = ref(false)
const report = ref<DecisionReport | null>(null)
const reportLoading = ref(false)
/** 随时倾向预览（不用等到期） */
const preview = ref<DecisionPreview | null>(null)
const trendChartRef = ref<HTMLDivElement>()
let trendChart: echarts.ECharts | null = null

const activeTrackers = computed(() => trackers.value.filter(t => t.status === activeTab.value))
const countOf = (status: string) => trackers.value.filter(t => t.status === status).length
const trackersOf = (status: string) => trackers.value.filter(t => t.status === status)

const previewMap = computed(() => {
  const map = new Map<number, TrackerPreviewItem>()
  for (const item of preview.value?.items ?? []) map.set(item.tracker_id, item)
  return map
})
const previewOf = (id: number): TrackerPreviewItem | undefined => previewMap.value.get(id)

const soonList = computed(() =>
  trackers.value.filter(t => t.status === '观察中' && t.days_left !== undefined && t.days_left >= 0 && t.days_left <= 7),
)
const expiredPending = computed(() => countOf('已到期'))
/** 顶部横幅：到期/临近提醒 + 断记提醒（观察期内一律不出倾向结论，避免中途结论影响判断） */
const bannerItems = computed<Array<{ text: string; type: 'warning' | 'error' | 'info' }>>(() => {
  const items: Array<{ text: string; type: 'warning' | 'error' | 'info' }> = []
  if (expiredPending.value > 0) {
    items.push({ text: `有 ${expiredPending.value} 个决策观察期已结束，建议查看报告做出决定。`, type: 'warning' })
  }
  for (const t of soonList.value.slice(0, 2)) {
    items.push({ text: `「${t.topic}」观察期还剩 ${t.days_left} 天（已记录 ${t.record_count ?? 0} 次）。`, type: 'warning' })
  }
  for (const s of preview.value?.stale_trackers ?? []) {
    items.push({ text: `「${s.topic}」已连续 ${s.stale_days} 天没有记录，观察容易中断，记得补一条。`, type: 'error' })
  }
  return items.slice(0, 4)
})

const canDecideFromReport = computed(() => current.value?.status === '已到期')
const detailTitle = computed(() => `📋 记录明细 — ${current.value?.topic ?? ''}`)
const reportTitle = computed(() => `📊 决策分析报告 — ${current.value?.topic ?? ''}`)

/** 当前追踪的倾向选项：自定义 → 选项文字；否则默认三项 */
const currentLeanOptions = computed<LeanOption[]>(() => {
  const t = current.value
  if (t?.lean_options?.length) return t.lean_options.map(l => ({ key: l, label: l }))
  return DEFAULT_LEAN_OPTIONS
})
/** 是否自定义倾向选项的追踪 */
function isCustomLean(t: DecisionTracker | TrackerPreviewItem): boolean {
  const opts = 'lean_options' in t ? t.lean_options : undefined
  return !!opts?.length
}
/** 报告理由列 / 图表系列：按追踪选项渲染 */
const reportCols = computed<LeanOption[]>(() => report.value?.options ?? [])
const reasonSpan = computed(() => {
  const n = reportCols.value.length || 3
  return n <= 2 ? 12 : Math.floor(24 / n)
})

function emptyText(status: string): string {
  const map: Record<string, string> = {
    观察中: '暂无追踪中的决策，点右上角「新建决策」开始观察',
    已到期: '暂无到期未决策的追踪',
    已决策: '暂无已做出决定的决策',
    已归档: '归档区空空如也',
  }
  return map[status] || ''
}

function statusTagType(s: string): 'primary' | 'success' | 'warning' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info'> = {
    观察中: 'primary', 已到期: 'warning', 已决策: 'success', 已归档: 'info',
  }
  return map[s] || 'info'
}
function tendencyLabel(t: Tendency, options?: LeanOption[]) { return leanMeta(t, options).label }
function tendencyTagType(t: Tendency, options?: LeanOption[]) { return leanMeta(t, options).tag }
function tendencyColor(t: Tendency, options?: LeanOption[]) { return leanMeta(t, options).color }
function intensityTagType(i: number): 'info' | 'warning' | 'danger' {
  if (i >= 4) return 'danger'
  return i === 3 ? 'warning' : 'info'
}
/** 加权倾向分：正数偏离开、负数偏留下（结论已封存于观察期后，仅「已到期/已决策/已归档」展示） */
function signedScore(score: number): string {
  return `${score > 0 ? '+' : ''}${score}`
}
function leanTagType(score: number): 'info' | 'warning' | 'danger' | 'success' {
  if (score > 0) return 'danger'
  return score < 0 ? 'success' : 'info'
}
/** 卡片加权标签颜色：默认三选项 = 红/绿双向语义；自定义选项 = 主导优势分，用中性/警示色 */
function leanTagTypeOf(item: TrackerPreviewItem): 'info' | 'warning' | 'danger' | 'success' {
  if (isCustomLean(item)) return item.weighted_score > 0 ? 'warning' : 'info'
  return leanTagType(item.weighted_score)
}

async function fetchTrackers() {
  loading.value = true
  try {
    const resp = await getDecisionTrackers()
    trackers.value = resp.data.results
  } catch {
    ElMessage.error('获取决策列表失败')
  } finally {
    loading.value = false
  }
  await fetchPreview()
}

/** 倾向预览（占比 + 强度加权 + 断记天数）——失败不打断主流程 */
async function fetchPreview() {
  try {
    const resp = await getDecisionPreview()
    preview.value = resp.data
  } catch {
    preview.value = null
  }
}

function openCreate() {
  Object.assign(createForm, {
    topic: '', start_date: todayISO(), end_date: todayISO(90), background: '',
    lean_options: [],
  })
  createVisible.value = true
}

async function handleCreate() {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    if (createForm.end_date < createForm.start_date) {
      ElMessage.warning('结束日期不能早于开始日期')
      return
    }
    // 自定义倾向选项：过滤空白项；只填了 1 项视为未定义
    const cleaned = createForm.lean_options.map(s => s.trim()).filter(Boolean)
    if (cleaned.length === 1) {
      ElMessage.warning('自定义倾向选项至少 2 项，或删掉留空用默认三项')
      return
    }
    submitting.value = true
    try {
      await createDecisionTracker({
        topic: createForm.topic,
        start_date: createForm.start_date,
        end_date: createForm.end_date,
        background: createForm.background,
        lean_options: cleaned.length >= 2 ? cleaned : null,
      })
      ElMessage.success('已开始观察，记得定期记录感受')
      createVisible.value = false
      await fetchTrackers()
    } catch {
      ElMessage.error('创建失败')
    } finally {
      submitting.value = false
    }
  })
}

function openRecord(t: DecisionTracker) {
  current.value = t
  // 默认选中第一个选项（自定义追踪取第一个自定义项，默认追踪保持 uncertain）
  const firstOption = t.lean_options?.length ? t.lean_options[0] : 'uncertain'
  Object.assign(recordForm, { tendency: firstOption, reason: '', intensity: 3, record_date: todayISO() })
  recordVisible.value = true
}

async function handleAddRecord() {
  if (!current.value) return
  submitting.value = true
  try {
    await createDecisionRecord({ tracker: current.value.id, ...recordForm })
    ElMessage.success('记录成功')
    recordVisible.value = false
    await fetchTrackers()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

async function openDetail(t: DecisionTracker) {
  current.value = t
  detailVisible.value = true
  detailLoading.value = true
  detailRecords.value = []
  try {
    const resp = await getTrackerRecords(t.id)
    detailRecords.value = resp.data
  } catch {
    ElMessage.error('获取记录失败')
  } finally {
    detailLoading.value = false
  }
}

async function handleDeleteRecord(row: DecisionRecord) {
  try {
    await ElMessageBox.confirm(`删除 ${row.record_date} 这条记录？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await deleteDecisionRecord(row.id)
    ElMessage.success('已删除')
    if (current.value) await openDetail(current.value)
    await fetchTrackers()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function openReport(t: DecisionTracker) {
  current.value = t
  report.value = null
  reportVisible.value = true
  reportLoading.value = true
  try {
    const resp = await getDecisionReport(t.id)
    report.value = resp.data
    await nextTick()
    renderTrendChart()
  } catch {
    ElMessage.error('生成报告失败')
  } finally {
    reportLoading.value = false
  }
}

function renderTrendChart() {
  const el = trendChartRef.value
  if (!el || !report.value) return
  if (trendChart) { trendChart.dispose(); trendChart = null }
  trendChart = echarts.init(el)
  const reportData = report.value
  const cols = reportCols.value
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: cols.map(o => o.label), bottom: 0 },
    grid: { left: '3%', right: '3%', bottom: 24, top: 10, containLabel: true },
    xAxis: { type: 'category', data: reportData.monthly_trend.map(m => m.month) },
    yAxis: { type: 'value', minInterval: 1 },
    series: cols.map(o => ({
      name: o.label,
      type: 'bar' as const,
      stack: 't',
      data: reportData.monthly_trend.map(m => m[o.key] ?? 0),
      itemStyle: { color: leanMeta(o.key, cols).color },
    })),
  })
}

function disposeReportChart() {
  if (trendChart) { trendChart.dispose(); trendChart = null }
  report.value = null
}

function openDecide(t: DecisionTracker) {
  current.value = t
  Object.assign(decideForm, { final_decision: '', decision_date: todayISO() })
  decideVisible.value = true
}

function decideFromReport() {
  reportVisible.value = false
  if (!current.value) return
  openDecide(current.value)
}

async function handleDecide() {
  if (!current.value) return
  if (!decideForm.final_decision.trim()) {
    ElMessage.warning('请填写最终决定')
    return
  }
  submitting.value = true
  try {
    await decideTracker(current.value.id, { final_decision: decideForm.final_decision.trim(), decision_date: decideForm.decision_date || todayISO() })
    ElMessage.success('已记录决定')
    decideVisible.value = false
    await fetchTrackers()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

function openArchive(t: DecisionTracker) {
  current.value = t
  archiveForm.review_note = t.review_note || ''
  archiveVisible.value = true
}

async function handleArchive() {
  if (!current.value) return
  submitting.value = true
  try {
    await archiveTracker(current.value.id, { review_note: archiveForm.review_note.trim() })
    ElMessage.success('已归档')
    archiveVisible.value = false
    await fetchTrackers()
  } catch {
    ElMessage.error('归档失败')
  } finally {
    submitting.value = false
  }
}

function openExtend(t: DecisionTracker) {
  current.value = t
  const base = t.days_left !== undefined && t.days_left >= 0 ? new Date(t.end_date) : new Date()
  extendForm.end_date = todayISO(0)
  if (base.getTime() > Date.now()) {
    const d = new Date(base); d.setDate(d.getDate() + 30)
    extendForm.end_date = toLocalISO(d)
  } else {
    extendForm.end_date = todayISO(30)
  }
  extendVisible.value = true
}

async function handleExtend() {
  if (!current.value) return
  if (!extendForm.end_date) { ElMessage.warning('请选择新结束日期'); return }
  submitting.value = true
  try {
    await updateDecisionTracker(current.value.id, { end_date: extendForm.end_date, status: '观察中' })
    ElMessage.success(`已延长至 ${extendForm.end_date}，继续观察中`)
    extendVisible.value = false
    await fetchTrackers()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(t: DecisionTracker) {
  try {
    await ElMessageBox.confirm(
      `删除「${t.topic}」将同时删除其下 ${t.record_count ?? 0} 条记录，不可恢复。确认删除？`,
      '警告', { type: 'warning' },
    )
  } catch { return }
  try {
    await deleteDecisionTracker(t.id)
    ElMessage.success('已删除')
    await fetchTrackers()
  } catch {
    ElMessage.error('删除失败')
  }
}

fetchTrackers()
</script>

<style scoped lang="scss">
.decision-tracker {
  padding: 20px;
  background-color: var(--el-bg-color-page);
  min-height: 100vh;
}

.back-bar { margin-bottom: 8px; }

.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px; flex-wrap: wrap; gap: 12px;

  .header-left { display: flex; align-items: center; gap: 12px;
    h2 { margin: 0; font-size: 22px; font-weight: 600; color: var(--el-text-color-primary); }
  }
  .header-actions { display: flex; gap: 8px; align-items: center; }
}

.reminder-banner { margin-bottom: 12px;
  .reminder-line + .reminder-line { margin-top: 8px; }
}

.main-tabs {
  :deep(.el-tabs__header) { margin-bottom: 12px; }
}

.tracker-list {
  min-height: 120px;
}

.tracker-card {
  margin-bottom: 12px;
  :deep(.el-card__body) { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 16px 20px; }

  .card-main { flex: 1; min-width: 0;
    .topic-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
      .topic { font-size: 16px; font-weight: 600; color: var(--el-text-color-primary); }
    }
    .meta-line { font-size: 13px; color: var(--el-text-color-regular);
      b { color: var(--el-text-color-primary); }
      .bg-text { color: var(--el-text-color-secondary); margin-left: 12px; max-width: 340px;
        display: inline-block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom; }
    }
    .decision-line { margin-top: 4px; font-size: 13px; color: #389e0d; }
    .review-line { margin-top: 2px; font-size: 13px; color: var(--el-text-color-secondary); }
    .lean-line { margin-top: 6px; font-size: 13px; color: var(--el-text-color-regular); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .stale-line { margin-top: 6px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
      .stale-hint { font-size: 12px; color: var(--el-text-color-secondary); } }
    .locked-line { margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); }
  }

  .card-actions { display: flex; gap: 6px; align-items: center; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
}

.dialog-topic { margin: 0 0 12px; font-size: 15px; font-weight: 600; color: var(--el-color-primary); }

.record-block { margin-bottom: 14px;
  .field-label { font-size: 13px; color: var(--el-text-color-regular); margin-bottom: 6px; }
}

.range-sep { margin: 0 6px; color: var(--el-text-color-secondary); }

.lean-options-editor {
  width: 100%;
  .lean-option-row {
    display: flex; align-items: center; gap: 6px; margin-bottom: 6px;
    .el-input { flex: 1; }
  }
  .lean-hint { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; margin-top: 2px; }
}

.report-body { min-height: 200px;
  .report-topic { margin: 0 0 4px; font-size: 16px; font-weight: 600; color: var(--el-text-color-primary);
    .report-period { font-size: 12px; font-weight: 400; color: var(--el-text-color-secondary); margin-left: 10px; }
  }
  .stat-row { display: flex; align-items: baseline; gap: 8px; margin: 6px 0 14px;
    .stat-num { font-size: 26px; font-weight: 700; color: var(--el-color-primary); }
    .stat-label { font-size: 12px; color: var(--el-text-color-secondary); }
  }
  .section-title { font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); margin: 16px 0 8px; }

  .tendency-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
    .tendency-name { width: 70px; font-size: 13px; color: var(--el-text-color-regular); }
    .tendency-track { flex: 1; height: 12px; background: var(--el-fill-color-light); border-radius: 6px; overflow: hidden;
      .tendency-fill { display: block; height: 100%; border-radius: 6px; transition: width .5s; }
    }
    .tendency-count { width: 110px; text-align: right; font-size: 12px; color: var(--el-text-color-regular); }
  }

  .trend-chart { height: 220px; width: 100%; }

  .reason-col { border-top: 3px solid; background: var(--el-fill-color-lighter); border-radius: 6px; padding: 8px 10px;
    min-height: 100px; max-height: 260px; overflow-y: auto;
    .reason-col-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; color: var(--el-text-color-primary); }
    .reason-item { margin-bottom: 8px;
      .reason-meta { font-size: 11px; color: var(--el-text-color-secondary); display: flex; align-items: center; gap: 6px; }
      .reason-text { font-size: 13px; color: var(--el-text-color-primary); line-height: 1.5; margin-top: 2px; }
    }
    .reason-empty { font-size: 12px; color: var(--el-text-color-secondary); }
  }
}

.extend-tip { margin: 0 0 12px; font-size: 13px; color: var(--el-text-color-regular); }

@media (max-width: 768px) {
  .tracker-card :deep(.el-card__body) { flex-direction: column; align-items: flex-start; }
  .card-actions { justify-content: flex-start; }
}
</style>
