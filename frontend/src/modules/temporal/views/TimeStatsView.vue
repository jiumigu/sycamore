<template>
  <div class="time-stats-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">⏱️ 时间统计</h1>
        <el-tag type="warning" class="module-tag">时间追踪</el-tag>
      </div>
      <div class="header-actions">
        <!-- v3.63.7：报表已从侧边栏降为「按钮页」（偶尔打开、看完就关），
             因此这里要有一条明确的回主入口的路 —— 任务清单才是这一块的主页面。 -->
        <el-button type="primary" size="default" @click="$router.push('/temporal/tasks')">
          <el-icon><ArrowLeft /></el-icon> 任务清单
        </el-button>
        <el-select v-model="selectedYear" size="default" style="width: 130px" @change="refreshData">
          <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
        </el-select>
        <el-button size="default" @click="importVisible = true">
          <el-icon><Upload /></el-icon>
          导入数据
        </el-button>
        <el-button size="default" @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button size="default" @click="$router.push('/temporal/mapping')">
          🧩 映射编辑器
        </el-button>
        <el-button size="default" @click="$router.push('/temporal/contrib')">
          📊 贡献图
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6f7ff"><el-icon color="#1890ff" :size="22"><Clock /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value stat-value--dual">
                <span class="sv-main">{{ recordedHoursText }}</span>
                <span class="sv-rest">
                  <span class="sv-sep">/</span>
                  <span class="sv-sub">{{ totalHoursText }}</span>
                </span>
              </div>
              <el-tooltip placement="top" :content="`总时间 = 16h × 有记录天数（${store.completeness?.days_recorded ?? 0} 天）`">
                <div class="stat-label">已记录 / 总时间（h）</div>
              </el-tooltip>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f6ffed"><el-icon color="#52c41a" :size="22"><Document /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ store.overview?.total_records ?? 0 }}</div>
              <div class="stat-label">记录数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff7e6"><el-icon color="#fa8c16" :size="22"><Calendar /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ store.overview?.active_days ?? 0 }}</div>
              <div class="stat-label">活跃天数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f0f5ff"><el-icon color="#2f54eb" :size="22"><TrendCharts /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ completenessText }}</div>
              <el-tooltip placement="top" content="已归类时长 ÷ 总时间（16h × 有记录天数）；未归类不参与">
                <div class="stat-label">记录完整度</div>
              </el-tooltip>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 🌞 旭日图（L1/L2） + 📈 月度趋势（L1） -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>🌞 时间结构（L1 归因 › L2 类型 › L3 任务）</span></template>
          <SunburstChart :data="store.sunburst" :height="400" :empty-text="`${selectedYear} 年暂无记录`" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>📈 月度趋势（按 L1 归因）</span></template>
          <div class="chart-host">
            <div ref="trendRef" class="chart-box"></div>
            <div v-if="trendEmpty" class="chart-empty">{{ selectedYear }} 年暂无记录</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 📅 168h 周结构 + 💎 赎回 mini 仪表 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="16">
        <el-card class="chart-card">
          <template #header><span>📅 近 12 周 168h 结构（按 L1 归因）</span></template>
          <Weekly168Chart :data="store.weeklyStructure" :height="320" :empty-text="`${selectedYear} 年暂无记录`" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header><span>🧭 当前阶段时间面</span></template>
          <div v-loading="stageLoading" class="stage-mini">
            <template v-if="ledger">
              <div class="rm-item">
                <span class="rm-label">阶段剩余</span>
                <span class="rm-value">{{ ledger.range.remaining_days }} 天</span>
              </div>
              <div class="rm-item">
                <span class="rm-label">时间覆盖率</span>
                <span class="rm-value">{{ (ledger.time.coverage_rate * 100).toFixed(1) }}%</span>
              </div>
              <div class="rm-item">
                <span class="rm-label">已记录</span>
                <span class="rm-value">{{ ledger.time.covered_hours }}h</span>
              </div>
              <el-divider />
              <div class="rm-4color">
                <div v-for="(h, k) in ledger.time.hours" :key="k" class="rm-bar-row">
                  <span class="rm-bar-label" :style="{ color: attrColor(String(k)) }">{{ k }}</span>
                  <span class="rm-bar-val">{{ Number(h).toFixed(1) }}h</span>
                </div>
              </div>
            </template>
            <!-- 🔴 两种「空」必须分开说：「还没有阶段」与「有阶段但账本取不到」
                 是完全不同的结论 —— 一律印「暂无数据」，用户会去查阶段是不是丢了。 -->
            <el-empty
              v-else
              :description="stageState === 'no_stage' ? '还没有进行中的阶段' : '阶段账本暂时取不到'"
              :image-size="60"
            />
            <div v-if="stageState === 'unavailable' && stageHint" class="stage-hint">
              {{ stageHint }}
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- CSV 导入弹窗：两步 —— 先检查会撞上什么，再决定落哪些（v3.64.32） -->
    <el-dialog v-model="importVisible" title="📂 导入数据" width="780px" @close="resetImport">
      <div class="import-body">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :show-file-list="true"
          :limit="1"
          accept=".csv"
          @change="handleFileChange"
        >
          <el-button type="primary">
            <el-icon><Upload /></el-icon>
            选择 CSV 文件
          </el-button>
          <template #tip>
            <div class="upload-tip">支持格式：.csv（ATracker 导出）</div>
          </template>
        </el-upload>

        <!-- 第一步：还没检查 -->
        <div v-if="!preview" class="import-rules">
          <h4>📋 落库前先看一眼</h4>
          <ul>
            <li>先检查：这份文件里哪些行库里已经有了、哪些行与已有记录的时段相交</li>
            <li>「相交」不一定是错 —— 大段「牛马工作」里再细分「代码编程」是合法记录</li>
            <li>检查阶段一个字都不写库，可以反复看、换文件重看</li>
          </ul>
        </div>

        <!-- 第二步：检查结果 -->
        <div v-else class="preview-block">
          <el-alert
            :title="previewSummaryText"
            :type="preview.summary.needs_review ? 'warning' : 'success'"
            :description="previewHintText"
            show-icon
            :closable="false"
          />
          <el-table
            v-if="preview.rows.length"
            :data="preview.rows"
            size="small"
            max-height="300"
            class="preview-table"
          >
            <el-table-column label="行" width="52">
              <template #default="{ row }">{{ row.row_no }}</template>
            </el-table-column>
            <el-table-column label="这次要导入的" min-width="196">
              <template #default="{ row }">
                <div class="pv-task">{{ row.task_name }}</div>
                <div class="pv-time">
                  {{ row.start_time }}<template v-if="row.end_time">–{{ row.end_time }}</template>
                  · {{ row.hours }}h
                </div>
              </template>
            </el-table-column>
            <el-table-column label="与已有记录的关系" min-width="232">
              <template #default="{ row }">
                <el-tag size="small" :type="verdictTagType(row.verdict)">
                  {{ verdictLabel(row.verdict) }}
                </el-tag>
                <div v-if="row.conflicts.length" class="pv-conflict">
                  {{ row.conflicts[0].task_name }}
                  {{ row.conflicts[0].start_time.slice(11) }}–{{ row.conflicts[0].end_time.slice(11) }}
                  · 重叠 {{ row.conflicts[0].overlap_minutes }} 分钟<template
                    v-if="row.conflict_total > 1"> · 共 {{ row.conflict_total }} 条</template>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="这次不导入" width="92" align="center">
              <template #default="{ row }">
                <el-checkbox
                  :model-value="isSkipped(row.row_no)"
                  @change="toggleSkip(row.row_no)"
                />
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="pv-empty">
            没有需要你判断的行 —— 直接确认导入即可。
          </div>
        </div>

        <div v-if="importResult" class="import-result">
          <el-alert :title="importSummary" type="success" show-icon closable />
        </div>
        <div v-if="importError" class="import-result">
          <el-alert :title="importError" type="error" show-icon closable />
        </div>
      </div>

      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button
          v-if="!preview"
          type="primary"
          :loading="checking"
          :disabled="!selectedFile"
          @click="handlePreview"
        >
          先检查
        </el-button>
        <el-button v-else type="primary" :loading="importing" @click="handleImport">
          {{ importButtonText }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadInstance } from 'element-plus'
import { Refresh, Upload, Clock, Document, Calendar, TrendCharts, ArrowLeft } from '@element-plus/icons-vue'
import { useTemporalStore } from '../stores/temporalStore'
import * as temporalApi from '@/modules/temporal/api/temporalApi'
// ⚠️ v3.64.20：「赎回时间面」这块改成读**当前阶段账本** —— 赎回期已并入自我运转，
//    旧的 `/api/redemption/stats/` 端点整体下线（留着就会调一个 404）。
import * as selfrunApi from '@/modules/selfrun/api/selfrunApi'
import type { StageLedger } from '@/modules/selfrun/types/selfrunTypes'
import * as echarts from 'echarts'
import SunburstChart from '../components/SunburstChart.vue'
import Weekly168Chart from '../components/Weekly168Chart.vue'
import { ATTRIBUTION_COLOR_MAP } from '../types/temporalTypes'
import type { ConflictRelation, ImportPreview } from '../types/temporalTypes'

const store = useTemporalStore()

// ─── 年份 ───
const selectedYear = ref(new Date().getFullYear())
const yearOptions = computed(() => {
  const years: number[] = []
  const y = new Date().getFullYear()
  for (let i = y; i >= y - 5; i--) years.push(i)
  return years
})

// ─── 指标卡片：数值格式化（统一两位小数，避免浮点尾巴如 26.3400000000000004）───
const recordedHoursText = computed(() => `${(store.overview?.total_hours ?? 0).toFixed(2)}h`)

/** 总时间（小时）= 完整度分母 = 基数 × 有记录天数；优先用后端给的 denominator_hours（整数不留小数） */
const totalHoursText = computed(() => {
  const c = store.completeness
  const denom = Number(c?.denominator_hours ?? (c?.days_recorded ?? 0) * (c?.denominator_hours_per_day ?? 16))
  return `${Number.isInteger(denom) ? denom : denom.toFixed(2)}h`
})

/** 记录完整度：00.00% 两位小数 */
const completenessText = computed(() => `${((store.completeness?.completeness ?? 0) * 100).toFixed(2)}%`)

// ─── 图表 refs ───
const trendRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
const trendEmpty = ref(false)

// 🔴 归因色唯一真源在 `types/temporalTypes.ts` 的 ATTRIBUTION_COLOR_MAP。
//    本处曾是**内联的第二份副本**（加词时漏改 ⇒ 新词静默落到灰色兜底，不报错），
//    v3.60.36 收口回来。`|| '#94A3B8'` 只兜「归因名不在表里」这种异常情况。
function attrColor(name: string | number) {
  return ATTRIBUTION_COLOR_MAP[String(name)] || '#94A3B8'
}

// ─── 导入（两步：预演 → 落库）───
const importVisible = ref(false)
/**
 * el-upload 的实例 —— `resetImport` 必须靠它清掉**界面上那个文件名**。
 * 🔴 只清 `selectedFile` 不够：弹窗重开时文件列表还挂着上一次的名字，
 *    而按钮因为 `selectedFile === null` 是灰的 ⇒「文件明明选着，却点不动」。
 */
const uploadRef = ref<UploadInstance | null>(null)
const selectedFile = ref<File | null>(null)
const checking = ref(false)
const importing = ref(false)
/** 预演结果；`null` = 还没检查过（弹窗此时显示规则说明，按钮是「先检查」） */
const preview = ref<ImportPreview | null>(null)
/** 用户勾掉的行号 —— **CSV 物理行号**，原样回传后端；前端不得自己重算 */
const skippedRows = ref<number[]>([])
const importResult = ref<{ inserted: number; updated: number; skipped: number; deduplicated?: number; skipped_by_user?: number; unclassified?: number; batch?: string } | null>(null)
const importError = ref('')

/** 四类的显示词 —— 唯一一份。后端只给 key，中文不写在两个地方 */
const VERDICT_LABEL: Record<ConflictRelation, string> = {
  likely_dup: '看起来是重复',
  review: '要你判断',
  edge: '跨整点摩擦',
  contained: '大段里的细分',
}

function verdictLabel(v: ConflictRelation): string {
  return VERDICT_LABEL[v]
}

function verdictTagType(v: ConflictRelation): 'danger' | 'warning' | 'info' {
  if (v === 'likely_dup') return 'danger'
  if (v === 'review') return 'warning'
  return 'info'
}

function isSkipped(rowNo: number): boolean {
  return skippedRows.value.includes(rowNo)
}

function toggleSkip(rowNo: number) {
  const i = skippedRows.value.indexOf(rowNo)
  if (i >= 0) skippedRows.value.splice(i, 1)
  else skippedRows.value.push(rowNo)
}

/**
 * 预演汇总。注意**不说「将新增 N 条」**：预演不判「更新还是新增」
 * （那是落库时按字段差异定的），编一个数出来就是假精确。
 */
const previewSummaryText = computed(() => {
  const p = preview.value
  if (!p) return ''
  const s = p.summary
  const parts = [`共 ${s.total} 行`]
  if (s.already_exists) parts.push(`库里已有 ${s.already_exists} 行（会跳过或更新）`)
  if (s.clean) parts.push(`干净 ${s.clean} 行`)
  const hits = s.contained + s.edge + s.review + s.likely_dup
  if (hits) parts.push(`与已有记录相交 ${hits} 行`)
  return parts.join(' · ')
})

const previewHintText = computed(() => {
  const p = preview.value
  if (!p) return ''
  const s = p.summary
  const bits: string[] = []
  if (s.contained || s.edge) {
    bits.push(`${s.contained} 行是大段里的细分、${s.edge} 行是跨整点的几分钟摩擦 —— 都算正常，没列出来`)
  }
  if (s.needs_review) {
    bits.push(`下面 ${s.needs_review} 行需要你看：「看起来是重复」指长度接近且几乎完全重合，最常见是同一件事在手机和电脑上各记了一次，默认已勾掉`)
  } else {
    bits.push('没有需要判断的行')
  }
  if (p.inner_duplicate) bits.push(`另有 ${p.inner_duplicate} 行在文件内部重复，落库时自动丢弃`)
  return bits.join('；')
})

const importButtonText = computed(() => (skippedRows.value.length
  ? `确认导入（跳过 ${skippedRows.value.length} 行）`
  : '确认导入'))

// 导入结果文案：把「全部跳过」这种情况讲清楚——它不是失败，而是这批记录库里已有一份
const importSummary = computed(() => {
  const r = importResult.value
  if (!r) return ''
  const dedup = r.deduplicated ? `，CSV 内重复去重 ${r.deduplicated} 条` : ''
  const mine = r.skipped_by_user ? `，你勾掉 ${r.skipped_by_user} 条` : ''
  const tail = r.unclassified ? `；${r.unclassified} 个任务待归类` : ''
  if (!r.inserted && !r.updated && r.skipped) {
    return `本次没有新增：CSV 里 ${r.skipped} 条记录库里都已有${mine}${dedup}（重复导入不会产生重复数据）${tail}`
  }
  // v3.64.33：把本批批次号摆出来 —— 否则「来源批次」弹窗里那 15 个批次，
  // 用户没法把「我刚导的这批」跟其中某一行对上（只能凭日期猜）。
  // ⚠️ 一条都没写进去时不显示：那批号在库里没有任何记录可归，显示出来反而是空指针。
  const batch = r.batch ? `；本批记为 ${r.batch}` : ''
  return `导入完成：新增 ${r.inserted} 条，更新 ${r.updated} 条，跳过 ${r.skipped} 条${mine}${dedup}${tail}${batch}`
})

function resetImport() {
  selectedFile.value = null
  uploadRef.value?.clearFiles()   // 界面上的文件名也要清，否则重开时「选着却点不动」
  preview.value = null
  skippedRows.value = []
  importResult.value = null
  importError.value = ''
  checking.value = false
  importing.value = false
}

function handleFileChange(file: any) {
  selectedFile.value = file.raw || null
  // 🔴 换了文件 ⇒ 旧的检查结果与勾选全部作废。留着会拿**旧行号**去跳新文件的行，
  //    轻则 400（后端会拒），重则跳过根本不该跳的那一行。
  preview.value = null
  skippedRows.value = []
  importResult.value = null
  importError.value = ''
}

async function handlePreview() {
  if (!selectedFile.value || checking.value) return
  checking.value = true
  importError.value = ''
  preview.value = null
  importResult.value = null
  try {
    const res = await store.previewCsv(selectedFile.value)
    if (res.error) {
      importError.value = res.error
      return
    }
    preview.value = res
    // 「看起来是重复」默认勾掉：同一件事两端各记一次是最常见的形态。
    // 「要你判断」**不预勾** —— 预勾等于替用户决定不要这份数据。
    skippedRows.value = res.rows
      .filter(r => r.verdict === 'likely_dup')
      .map(r => r.row_no)
  } catch (e: any) {
    importError.value = e?.response?.data?.error || '检查失败'
  } finally {
    checking.value = false
  }
}

async function handleImport() {
  if (!selectedFile.value || importing.value) return
  importing.value = true
  importError.value = ''
  importResult.value = null
  try {
    const result = await store.importCsv(selectedFile.value, skippedRows.value)
    if (result.error) {
      // 失败时**保留清单**：用户可以改勾选重试，不用再传一次文件
      importError.value = result.error
    } else {
      importResult.value = result
      preview.value = null
      skippedRows.value = []
      await refreshData()
      ElMessage.success(`导入完成：新增 ${result.inserted} 条，更新 ${result.updated} 条，跳过 ${result.skipped ?? 0} 条`
        + (result.skipped_by_user ? `，你勾掉 ${result.skipped_by_user} 条` : '')
        + (result.deduplicated ? `，CSV 内重复去重 ${result.deduplicated} 条` : ''))
    }
  } catch (e: any) {
    importError.value = e?.response?.data?.error || '导入失败'
  } finally {
    importing.value = false
  }
}

// ─── 当前阶段时间面（v3.64.20：赎回期已并入自我运转）───
// 🔴 两步取数，不是偷懒：账本接口要 stage id，而「哪一个是当前阶段」由后端定
//    （`get_open_stage` 收窄为「有在跑 KPI 的叶子」）。前端自己按 start_date 排
//    会取到长阶段 —— 长阶段没有 KPI，账本页面显示 0/0，看着像没数据。
const ledger = ref<StageLedger | null>(null)
const stageLoading = ref(false)
/** `no_stage` = 确实没有在跑的阶段；`unavailable` = 有阶段但账本没取到 */
const stageState = ref<'ok' | 'no_stage' | 'unavailable'>('ok')
/** 取不到时把后端那句话原样带出来（例如「请先执行 migrate」），别自己编 */
const stageHint = ref('')

async function loadStageLedger() {
  stageLoading.value = true
  stageHint.value = ''
  try {
    // 🔴 `shape=long`：这一面讲的是「这段长路」的时间归因，
    //    取的必须是长阶段。裸 `status=active` 会同时返回长阶段与小阶段，
    //    靠「取第一条」拿对纯属排序巧合（起点相同按 -id，id 大的正好是长阶段）。
    const stages = await selfrunApi.listStages({ status: 'active', shape: 'long' })
    const stage = (stages.data || [])[0]
    if (!stage) {
      ledger.value = null
      stageState.value = 'no_stage'
      return
    }
    ledger.value = (await selfrunApi.getStageLedger(stage.id)).data.ledger
    stageState.value = 'ok'
  } catch (e: any) {
    // 取不到就空态 —— 不许把上一份数留在屏上（那会让人以为这一期没变化）
    ledger.value = null
    stageState.value = 'unavailable'
    stageHint.value = e?.response?.data?.detail || ''
  } finally {
    stageLoading.value = false
  }
}

// ─── 月度趋势（L1 堆叠）───
function initTrendChart() {
  if (!trendRef.value) return
  if (!trendChart) trendChart = echarts.init(trendRef.value)

  const data = store.trendData || []
  // 空数据必须显式清图：setOption 默认是 merge，`series: []` 这种空数组不会删掉上一次的柱子，
  // 于是切到没有记录的年份时会残留旧数据（表现为「图表有柱子、卡片全是 0」）
  if (!data.length) {
    trendEmpty.value = true
    trendChart.clear()
    return
  }
  trendEmpty.value = false

  const allKeys = new Set<string>()
  data.forEach((d: any) => Object.keys(d).forEach((k) => { if (k !== 'period') allKeys.add(k) }))
  const keys = Array.from(allKeys).sort()
  const chartData = data.slice(-12)

  trendChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: keys, bottom: 0, type: 'scroll', icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
    // top 留够：y 轴 name「小时」要显示在轴顶上方，top: '5%' 会把字号裁掉一半
    grid: { left: '3%', right: '4%', bottom: '22%', top: 26, containLabel: true },
    xAxis: {
      type: 'category',
      data: chartData.map((d: any) => d.period),
      // 已按单年筛选，轴上只显示「M月」（tooltip 仍保留完整 YYYY-MM）
      axisLabel: {
        rotate: 0, fontSize: 10, hideOverlap: true,
        formatter: (v: string) => `${parseInt(v.slice(5), 10)}月`,
      },
    },
    yAxis: { type: 'value', name: '小时', nameGap: 14, nameTextStyle: { fontSize: 10, color: '#9CA3AF' } },
    series: keys.map((name) => ({
      name,
      type: 'bar' as const,
      stack: 'total',
      barWidth: '65%',
      data: chartData.map((d: any) => +(d[name] || 0).toFixed(2)),
      itemStyle: { color: attrColor(name) },
      label: { show: false },
      emphasis: { focus: 'series' as const },
    })),
  }, true) // notMerge：换年份时整体替换，避免旧系列/旧图例残留
  trendChart.resize()
}

// ─── 数据加载 ───
async function refreshData() {
  const year = selectedYear.value
  await Promise.all([
    store.fetchOverview(year),
    store.fetchTrend(year, 'month'),
    store.fetchSunburst(year),
    store.fetchWeeklyStructure(year, 12),
    store.fetchCompleteness(year),
    loadStageLedger(),
    store.fetchStats(),
  ])
  nextTick(initTrendChart)
}

window.addEventListener('resize', () => { trendChart?.resize() })

onMounted(async () => { await refreshData() })
</script>

<style scoped lang="scss">
.time-stats-view {
  padding: 20px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
      .page-title { margin: 0; font-size: 24px; font-weight: 600; color: #1F2937; }
    }
    .header-actions { display: flex; gap: 8px; align-items: center; }
  }

  .stats-row { margin-bottom: 18px;
    // 四张卡等高，避免其中一张文字折行时被拉高
    .el-col { display: flex; }
    .stat-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); width: 100%;
      :deep(.el-card__body) { height: 100%; display: flex; align-items: center; }
      .stat-content { display: flex; align-items: center; gap: 14px; padding: 6px 4px; width: 100%;
        .stat-icon { width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .stat-info {
          min-width: 0;
          .stat-value { font-size: 22px; font-weight: 700; color: #1F2937; line-height: 1.3; }
          // 「已记录 h / 总时间 h」双值排版：主值突出、总值次要
          .stat-value--dual {
            display: flex; align-items: baseline; gap: 3px; flex-wrap: wrap;
            .sv-main { font-size: 15px; font-weight: 700; color: #1F2937; letter-spacing: -0.2px; white-space: nowrap; }
            // 「/ 总时间」整组换行，不会出现 「/」孤零零留在行尾
            .sv-rest { display: inline-flex; align-items: baseline; gap: 3px; white-space: nowrap;
              .sv-sep { font-size: 13px; color: #C0C4CC; }
              .sv-sub { font-size: 14px; font-weight: 600; color: #6B7280; letter-spacing: -0.2px; }
            }
          }
          .stat-label { font-size: 13px; color: #6B7280; }
        }
      }
    }
  }

  .chart-row { margin-bottom: 18px; display: flex; flex-wrap: wrap;
    .el-col { display: flex; }
    .chart-card { border: none; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); width: 100%; display: flex; flex-direction: column;
      :deep(.el-card__header) { padding: 14px 20px; font-size: 14px; font-weight: 500; border-bottom: 1px solid #f2f2f2; }
      :deep(.el-card__body) { flex: 1; display: flex; padding: 16px; }
      .chart-host {
        position: relative; display: flex; flex: 1; width: 100%;
        .chart-box { flex: 1; width: 100%; min-height: 280px; }
        .chart-empty {
          position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
          color: #9CA3AF; font-size: 13px; pointer-events: none;
        }
      }
    }
  }

  .stage-mini { padding: 4px 8px; width: 100%;
    .rm-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed #f0f0f0;
      .rm-label { font-size: 13px; color: #6B7280; }
      .rm-value { font-size: 16px; font-weight: 700; color: #1F2937; } }
    .rm-4color { margin-top: 8px;
      .rm-bar-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }
      .rm-bar-label { font-weight: 600; }
      .rm-bar-val { color: #4B5563; } }
    .muted { color: #b8bcc4; font-size: 13px; }
    .stage-hint { padding: 0 8px 8px; font-size: 12px; color: #B45309; line-height: 1.7; }
  }

  .import-body {
    .upload-tip { font-size: 12px; color: #909399; margin-top: 4px; }
    .import-rules { background: #f9fafb; border-radius: 8px; padding: 12px 16px; margin: 8px 0 12px;
      h4 { margin: 0 0 6px; font-size: 13px; color: #1F2937; }
      ul { margin: 0; padding-left: 18px; font-size: 12px; color: #6B7280; line-height: 1.8; } }
    .import-result { margin-top: 12px; }
    // 预演清单：两行式（任务名 + 时段），比单行挤九个字段好认
    .preview-block { margin: 8px 0 4px; }
    .preview-table { margin-top: 10px; }
    .pv-task { font-size: 13px; font-weight: 600; color: #1F2937; }
    .pv-time { font-size: 12px; color: #6B7280; margin-top: 2px; }
    .pv-conflict { font-size: 12px; color: #6B7280; margin-top: 6px; line-height: 1.7; }
    .pv-empty { margin-top: 10px; font-size: 13px; color: #6B7280; }
  }
}
</style>
