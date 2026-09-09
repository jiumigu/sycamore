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

    <el-alert
      v-if="reminderText"
      :title="reminderText"
      type="warning"
      :closable="false"
      show-icon
      class="reminder-banner"
    />

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
            <el-radio-button value="continue">✓ 想继续</el-radio-button>
            <el-radio-button value="quit">✗ 不想继续</el-radio-button>
            <el-radio-button value="uncertain">？不确定</el-radio-button>
          </el-radio-group>
        </div>
        <div class="record-block">
          <div class="field-label">具体理由（关键词即可，可留空）</div>
          <el-input v-model="recordForm.reason" type="textarea" :rows="3"
            placeholder="如：需求被卡了一周，感觉自己什么也没推进" maxlength="500" show-word-limit />
        </div>
        <div class="record-block">
          <div class="field-label">情绪强度</div>
          <el-radio-group v-model="recordForm.intensity">
            <el-radio-button value="低">低</el-radio-button>
            <el-radio-button value="中">中</el-radio-button>
            <el-radio-button value="高">高</el-radio-button>
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
            <el-tag :type="tendencyTagType(row.tendency)" size="small">{{ tendencyLabel(row.tendency) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="intensity" label="强度" width="70" align="center">
          <template #default="{ row }">
            <span :class="`intensity-${row.intensity}`">{{ row.intensity }}</span>
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
              <span class="tendency-fill" :style="{ width: s.percent + '%', background: tendencyColor(s.tendency) }" />
            </span>
            <span class="tendency-count">{{ s.count }} 次 · {{ s.percent }}%</span>
          </div>

          <div v-if="report.monthly_trend.length" class="section-title">📈 月度倾向趋势</div>
          <div v-if="report.monthly_trend.length" ref="trendChartRef" class="trend-chart" />

          <div class="section-title">🗂️ 理由明细（按倾向分列）</div>
          <el-row :gutter="12">
            <el-col v-for="t in reasonCols" :key="t" :span="8">
              <div class="reason-col" :style="{ borderTopColor: tendencyColor(t) }">
                <div class="reason-col-title">{{ tendencyLabel(t) }}</div>
                <template v-if="report.reasons[t].length">
                  <div v-for="(r, i) in report.reasons[t]" :key="i" class="reason-item">
                    <div class="reason-meta">{{ r.record_date }}
                      <el-tag size="small" effect="plain" :type="intensityTagType(r.intensity)">{{ r.intensity }}</el-tag>
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
  getDecisionReport, decideTracker, archiveTracker,
} from '../../api/decisionTrackerApi'
import type { DecisionTracker, DecisionRecord, DecisionReport, Tendency } from '../../api/decisionTrackerApi'

const TABS = [
  { status: '观察中', label: '追踪中' },
  { status: '已到期', label: '已到期' },
  { status: '已决策', label: '已决策' },
  { status: '已归档', label: '归档' },
] as const

/** 报告理由三列展示顺序 */
const reasonCols: Tendency[] = ['continue', 'quit', 'uncertain']

const TENDENCY_META: Record<Tendency, { label: string; tag: 'success' | 'danger' | 'warning'; color: string }> = {
  continue: { label: '想继续', tag: 'success', color: '#52c41a' },
  quit: { label: '不想继续', tag: 'danger', color: '#f5222d' },
  uncertain: { label: '不确定', tag: 'warning', color: '#fa8c16' },
}

function todayISO(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
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

const createForm = reactive({ topic: '', start_date: todayISO(), end_date: todayISO(90), background: '' })
const createRules: FormRules = {
  topic: [{ required: true, message: '请填写决策主题', trigger: 'blur' }],
  end_date: [{ required: true, message: '请选择观察结束日期', trigger: 'change' }],
}
const recordForm = reactive<{ tendency: Tendency; reason: string; intensity: '低' | '中' | '高'; record_date: string }>({
  tendency: 'uncertain', reason: '', intensity: '中', record_date: todayISO(),
})
const decideForm = reactive({ final_decision: '', decision_date: todayISO() })
const archiveForm = reactive({ review_note: '' })
const extendForm = reactive({ end_date: '' })

const detailRecords = ref<DecisionRecord[]>([])
const detailLoading = ref(false)
const report = ref<DecisionReport | null>(null)
const reportLoading = ref(false)
const trendChartRef = ref<HTMLDivElement>()
let trendChart: echarts.ECharts | null = null

const activeTrackers = computed(() => trackers.value.filter(t => t.status === activeTab.value))
const countOf = (status: string) => trackers.value.filter(t => t.status === status).length
const trackersOf = (status: string) => trackers.value.filter(t => t.status === status)

const soonList = computed(() =>
  trackers.value.filter(t => t.status === '观察中' && t.days_left !== undefined && t.days_left >= 0 && t.days_left <= 7),
)
const expiredPending = computed(() => countOf('已到期'))
const reminderText = computed(() => {
  const parts: string[] = []
  if (expiredPending.value > 0) parts.push(`有 ${expiredPending.value} 个决策观察期已结束，建议查看报告做出决定。`)
  for (const t of soonList.value.slice(0, 2)) {
    parts.push(`「${t.topic}」观察期还剩 ${t.days_left} 天（已记录 ${t.record_count ?? 0} 次）。`)
  }
  return parts.join(' ')
})

const canDecideFromReport = computed(() => current.value?.status === '已到期')
const detailTitle = computed(() => `📋 记录明细 — ${current.value?.topic ?? ''}`)
const reportTitle = computed(() => `📊 决策分析报告 — ${current.value?.topic ?? ''}`)

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
function tendencyLabel(t: Tendency) { return TENDENCY_META[t].label }
function tendencyTagType(t: Tendency) { return TENDENCY_META[t].tag }
function tendencyColor(t: Tendency) { return TENDENCY_META[t].color }
function intensityTagType(i: string): 'info' | 'warning' | 'danger' {
  const map: Record<string, 'info' | 'warning' | 'danger'> = { 低: 'info', 中: 'warning', 高: 'danger' }
  return map[i] || 'info'
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
}

function openCreate() {
  Object.assign(createForm, { topic: '', start_date: todayISO(), end_date: todayISO(90), background: '' })
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
    submitting.value = true
    try {
      await createDecisionTracker({ ...createForm })
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
  Object.assign(recordForm, { tendency: 'uncertain', reason: '', intensity: '中', record_date: todayISO() })
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
  const months = report.value.monthly_trend.map(m => m.month)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['想继续', '不想继续', '不确定'], bottom: 0 },
    grid: { left: '3%', right: '3%', bottom: 24, top: 10, containLabel: true },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '想继续', type: 'bar', stack: 't', data: report.value.monthly_trend.map(m => m.continue), itemStyle: { color: '#52c41a' } },
      { name: '不想继续', type: 'bar', stack: 't', data: report.value.monthly_trend.map(m => m.quit), itemStyle: { color: '#f5222d' } },
      { name: '不确定', type: 'bar', stack: 't', data: report.value.monthly_trend.map(m => m.uncertain), itemStyle: { color: '#fa8c16' } },
    ],
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
    extendForm.end_date = d.toISOString().slice(0, 10)
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

.reminder-banner { margin-bottom: 12px; }

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
  }

  .card-actions { display: flex; gap: 6px; align-items: center; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
}

.dialog-topic { margin: 0 0 12px; font-size: 15px; font-weight: 600; color: var(--el-color-primary); }

.record-block { margin-bottom: 14px;
  .field-label { font-size: 13px; color: var(--el-text-color-regular); margin-bottom: 6px; }
}

.range-sep { margin: 0 6px; color: var(--el-text-color-secondary); }

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

.intensity-低 { color: var(--el-text-color-secondary); }
.intensity-中 { color: #d46b08; font-weight: 600; }
.intensity-高 { color: #cf1322; font-weight: 600; }

.extend-tip { margin: 0 0 12px; font-size: 13px; color: var(--el-text-color-regular); }

@media (max-width: 768px) {
  .tracker-card :deep(.el-card__body) { flex-direction: column; align-items: flex-start; }
  .card-actions { justify-content: flex-start; }
}
</style>
