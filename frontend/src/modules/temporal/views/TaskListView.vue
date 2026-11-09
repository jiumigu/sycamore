<template>
  <div class="task-list-view">
    <!-- v3.63.7：这一页是「时间感知」的主入口 —— 页内不再有「返回」，
         只有通往报表 / 映射编辑器 / 贡献图的按钮（那两个菜单项已从侧边栏撤掉）。 -->
    <div class="page-header">
      <h2 class="page-title">📋 时间任务清单</h2>
      <div class="header-actions">
        <!-- v3.63.10：贡献图原先只能从「时间统计报表」进，但它看的是任务本身的热力分布，
             与任务清单是同一批数据的两种看法 ⇒ 两个入口并列，带 `from` 让子页知道从哪来回哪去。 -->
        <el-button
          size="small"
          @click="$router.push({ path: '/temporal/contrib', query: { from: 'tasks' } })"
        >📈 贡献图</el-button>
        <el-button size="small" type="primary" @click="openCreate">＋ 手工新增</el-button>
        <el-button size="small" @click="timerPanelVisible = true">⏱ 实时计时</el-button>
        <el-button size="small" @click="$router.push('/temporal/mapping')">🧩 映射编辑器</el-button>
        <!-- v3.64.33：来源可见 —— 每条记录是从哪写进来的（CSV / 计时 / 工作日志 / 加班反推） -->
        <el-button size="small" @click="openSources">🧾 来源批次</el-button>
        <el-button size="small" @click="$router.push('/temporal')">📊 时间统计报表</el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-date-picker
        v-model="filter.dateRange"
        type="daterange"
        range-separator="~"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        size="small"
        style="width:240px"
        @change="applyFilter"
      />
      <el-select v-model="filter.attribution" placeholder="L1 归因" clearable size="small" style="width:120px" @change="applyFilter">
        <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
      </el-select>
      <el-select v-model="filter.activity_type" placeholder="L2 活动类型" clearable size="small" style="width:140px" @change="applyFilter">
        <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
      </el-select>
      <el-checkbox v-model="filter.unclassified" size="small" @change="applyFilter">仅未归类</el-checkbox>
      <!-- 来源选项来自后端（不写死中文）：标签与条数都由 /tasks/sources/ 下发 -->
      <el-select v-model="filter.source" placeholder="来源" clearable size="small" style="width:132px"
        @change="onSourceChange">
        <el-option v-for="k in sourceKinds" :key="k.kind"
          :label="`${k.label} ${k.count}`" :value="k.kind" />
      </el-select>
      <el-tag v-if="filter.batch" closable size="small" type="info" @close="clearBatch">
        只看批次 {{ filter.batch }}
      </el-tag>
      <el-input v-model="filter.keyword" placeholder="搜索任务名 / 备注" clearable size="small" style="width:180px"
        @keyup.enter="applyFilter" @clear="applyFilter">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button size="small" @click="applyFilter">查询</el-button>
      <el-button size="small" @click="resetFilter">重置</el-button>
    </div>

    <!-- 批量操作条 -->
    <div class="bulk-bar" v-if="selectedRows.length">
      <span>已选 {{ selectedRows.length }} 项</span>
      <el-button size="small" type="primary" @click="bulkVisible = true">批量改 L1 归因 / L2 类型</el-button>
      <el-button size="small" @click="clearSelection">取消选择</el-button>
    </div>

    <el-table ref="tableRef" :data="tasks" v-loading="loading" stripe size="small" max-height="560"
      @selection-change="onSelectionChange" row-key="id">
      <el-table-column type="selection" width="40" reserve-selection />
      <el-table-column label="任务（L3）" width="220">
        <template #default="{ row }">
          <div class="task-cell">
            <div class="task-name">{{ row.task_name }}</div>
            <el-tooltip
              v-if="row.task_description"
              placement="top"
              :content="row.task_description"
              :show-after="200"
            >
              <div class="task-desc">{{ flatDesc(row.task_description) }}</div>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="140">
        <template #default="{ row }">{{ (row.start_time || '').slice(0, 16) }}</template>
      </el-table-column>
      <el-table-column label="结束时间" width="90">
        <template #default="{ row }">
          <span v-if="row.end_time">{{ endTimeText(row) }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column width="86">
        <template #header>
          <el-tooltip placement="top" content="该条记录的时长；正常情况下等于「结束 − 开始」，两者不一致时以本列为准">
            <span class="th-tip">时长</span>
          </el-tooltip>
        </template>
        <template #default="{ row }">
          <span v-if="!row.duration_display" class="muted">-</span>
          <el-tooltip v-else :disabled="!spanMismatch(row)" placement="top" :content="durationTip(row)">
            <span :class="{ 'dur-multi': spanMismatch(row) }">{{ row.duration_display }}<i v-if="spanMismatch(row)" class="dur-mark">*</i></span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="L1 归因" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.attribution" size="small" :style="attrStyle(row.attribution)">{{ row.attribution }}</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="L2 类型" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.activity_type" size="small" :style="typeStyle(row.activity_type)">{{ row.activity_type }}</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="106">
        <template #default="{ row }">
          <el-tooltip placement="top" :content="sourceTip(row)" :show-after="200">
            <el-tag size="small" effect="plain" :type="sourceTagType(row.source_kind)">
              {{ row.source_label || '—' }}
            </el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.notes || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next" small
      style="margin-top:12px;justify-content:center" @current-change="loadTasks" />

    <!-- 来源批次（v3.64.33）：回答「这些时间记录是从哪写进来的」 -->
    <el-dialog v-model="sourcesVisible" title="记录来源 · 从哪写进来的" width="880px">
      <div v-loading="sourcesLoading" class="src-body">
        <div v-if="sourcesError" class="src-err">{{ sourcesError }}</div>
        <template v-else-if="sources">
          <div class="src-head">
            <span class="src-total">全库 {{ sources.total_records }} 条</span>
            <span class="src-sub">· {{ sources.total_batches }} 个批次</span>
            <el-tag v-if="sources.unlabeled_count" type="warning" effect="plain" size="small">
              {{ sources.unlabeled_count }} 条没有来源标记
            </el-tag>
          </div>
          <!-- 来源汇总：点一下 = 只看这个来源（并关掉弹窗落在清单上） -->
          <div class="src-kinds">
            <el-tooltip v-for="k in sources.kinds" :key="k.kind" :content="k.hint" placement="top">
              <button class="src-kind" @click="applySource(k.kind)">
                <b>{{ k.label }}</b><span>{{ k.count }}</span>
              </button>
            </el-tooltip>
          </div>
          <el-table :data="sources.items" size="small" max-height="400" stripe>
            <el-table-column label="批次号" min-width="210">
              <template #default="{ row }">
                <span v-if="row.batch" class="mono">{{ row.batch }}</span>
                <span v-else class="muted">（没有批次号）</span>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="96">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" :type="sourceTagType(row.kind)">{{ row.label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="条数" width="68" align="right">
              <template #default="{ row }">{{ row.count }}</template>
            </el-table-column>
            <el-table-column label="任务名" width="68" align="right">
              <template #default="{ row }">{{ row.name_kinds }}</template>
            </el-table-column>
            <el-table-column label="记录覆盖的时间" width="156">
              <template #default="{ row }">
                <!-- 两行固定（首条 / 末条），不靠列宽硬挤 —— 否则每行折行位置不同，行高参差 -->
                <div v-if="row.first_start" class="span-two">
                  <div>{{ row.first_start }}</div>
                  <div class="span-to">→ {{ row.last_start }}</div>
                </div>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="最后改动" width="132">
              <template #default="{ row }">{{ row.last_touch || '—' }}</template>
            </el-table-column>
            <el-table-column width="96">
              <template #default="{ row }">
                <el-button link size="small" @click="drillBatch(row)">看这 {{ row.count }} 条</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="src-note">
            「最后改动」是这批记录最后一次被改写的时间，<b>不是导入时间</b> —— 改备注也会刷新它。
            「未标注」是早期记录，当时还没有来源标记；从现在起，这一页手工新增的记录会标成「手工录入」。
          </div>
        </template>
      </div>
    </el-dialog>

    <!-- 批量改弹窗 -->
    <el-dialog v-model="bulkVisible" title="批量设置 L1 归因 / L2 类型" width="460px">
      <el-form label-width="110px" size="small">
        <el-form-item label="L2 活动类型" required>
          <el-select v-model="bulkForm.activity_type" style="width:100%">
            <el-option v-for="a in ACTIVITY_TYPE_OPTIONS" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="L1 价值归因">
          <el-select v-model="bulkForm.attribution" clearable style="width:100%">
            <el-option v-for="a in ATTRIBUTION_OPTIONS" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="bulkVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="applyBulk">应用</el-button>
      </template>
    </el-dialog>

    <!-- 单条新增 / 编辑（时长由起止时间自动计算，不再手填） -->
    <el-dialog v-model="editVisible" :title="editingId ? '编辑任务' : '手工新增记录'" width="540px">
      <el-form :model="editForm" label-width="80px" size="small">
        <el-form-item label="任务名称" required :error="nameError">
          <div class="name-field">
            <!-- 最近常用：只在新增时出现；点一下选中、再点一次取消 -->
            <div v-if="!editingId" class="freq-block">
              <div v-if="frequentLoading" class="freq-hint">正在读取最近常用任务…</div>
              <div v-else-if="frequentNames.length" class="freq-row">
                <span class="freq-label">近{{ frequentMonths }}个月常用</span>
                <el-tooltip
                  v-for="n in frequentNames"
                  :key="n.task_name"
                  :content="`${n.record_count} 次 · ${n.total_hours} 小时`"
                  placement="top"
                >
                  <el-check-tag
                    class="freq-tag"
                    :checked="pickedName === n.task_name"
                    @change="togglePick(n.task_name)"
                  >{{ n.task_name }}</el-check-tag>
                </el-tooltip>
              </div>
              <div v-else-if="frequentError" class="freq-hint freq-warn">
                常用任务没读出来，可直接手动输入
              </div>
            </div>
            <el-input
              v-model="editForm.task_name"
              :disabled="!!pickedName"
              :placeholder="pickedName ? '' : '如：深度工作 / 刷短视频'"
              @input="nameError = ''"
            />
            <div v-if="pickedName" class="freq-hint">
              已选「{{ pickedName }}」；再点一次标签可取消、恢复手输
            </div>
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.task_description" type="textarea" :rows="2" />
        </el-form-item>
        <el-row :gutter="10">
          <el-col :span="12">
            <el-form-item label="开始时间" required>
              <el-date-picker v-model="editForm.start_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss"
                :clearable="false" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间" required>
              <el-date-picker v-model="editForm.end_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss"
                :clearable="false" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="时长">
          <div class="dur-auto">
            <span v-if="formSpanOk" class="dur-value">{{ formDurationText }}<small>小时</small></span>
            <span v-if="formSpanOk" class="dur-hhmm">{{ formHhmmText }}</span>
            <span v-else-if="formSpanMin !== null" class="dur-err">结束时间需晚于开始时间（跨零点请把结束时间选到次日）</span>
            <span v-else class="muted">选定起止时间后自动计算</span>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="2" placeholder="如：和启迪聊天" />
        </el-form-item>
        <!-- 录入当时就说清「这条会被记成什么来源」；编辑态不出现（改备注不换来源） -->
        <div v-if="!editingId" class="src-hint">
          保存后来源记为「手工录入」—— 之后在清单的「来源」列、「来源批次」弹窗里都能看到它。
        </div>
      </el-form>
      <template #footer>
        <el-button size="small" @click="editVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 实时计时：与手工补录并排在同一页，才会真的在两者之间做选择 -->
    <TimerPanel v-model="timerPanelVisible" @changed="onTimerChanged" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import * as temporalApi from '@/modules/temporal/api/temporalApi'
import TimerPanel from '@/modules/temporal/components/TimerPanel.vue'
import { useTemporalStore } from '../stores/temporalStore'
import { ACTIVITY_TYPE_COLOR_MAP, ACTIVITY_TYPE_OPTIONS, ATTRIBUTION_COLOR_MAP, ATTRIBUTION_OPTIONS } from '../types/temporalTypes'
import type { FrequentTaskName, OverlapCheckData, SourceBatchItem, SourceKindSummary, SourceOverview } from '../types/temporalTypes'

const store = useTemporalStore()

const tasks = ref<any[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const selectedRows = ref<any[]>([])
const tableRef = ref<any>(null)

const filter = reactive<{
  dateRange: string[]; activity_type: string; attribution: string; keyword: string
  unclassified: boolean; source: string; batch: string
}>({
  dateRange: [], activity_type: '', attribution: '', keyword: '', unclassified: false,
  source: '', batch: '',
})

const bulkVisible = ref(false)
const saving = ref(false)
const bulkForm = reactive<{ activity_type: string; attribution: string | null }>({ activity_type: '', attribution: null })

const editVisible = ref(false)
const timerPanelVisible = ref(false)
const editingId = ref<number | null>(null)
// v3.58.6：不再有 duration_hours 输入 —— 时长由「开始时间 → 结束时间」自动算，后端落库时同步派生
const editForm = reactive({
  task_name: '', task_description: '', start_time: '', end_time: '', notes: '',
})

// ─── 最近常用任务（手工新增弹窗的快捷候选）────────────────────────────────
// 🔴 「选中的标签」与「手输的值」共用同一份 `editForm.task_name`：
//    选中 → 把标签名写进去 + 禁用输入框；取消 → 恢复选之前手输的内容。
//    这样「最终会提交哪个值」在界面上只有一处，提交时不需要再判「谁优先」，
//    也就不会出现「看着选了 A、实际提交了 B」这种静默错位。
const pickedName = ref('')
const frequentNames = ref<FrequentTaskName[]>([])
const frequentMonths = ref(3)
const frequentLoading = ref(false)
const frequentError = ref(false)
const nameError = ref('')
// 选中标签前手输的内容；A → B 换标签时不覆盖，取消后能回到最初手输的值
let stashedName = ''

function attrStyle(name: string) {
  return { background: (ATTRIBUTION_COLOR_MAP[name] || '#94A3B8') + '22', color: ATTRIBUTION_COLOR_MAP[name] || '#64748B', border: 'none' }
}
function typeStyle(name: string) {
  return { background: (ACTIVITY_TYPE_COLOR_MAP[name] || '#94A3B8') + '22', color: ACTIVITY_TYPE_COLOR_MAP[name] || '#64748B', border: 'none' }
}

// ─── 来源可见（v3.64.33）──────────────────────────────────────────────
// 🔴 中文词全部来自后端（`source_label` / `kinds[].label`），这里不写「CSV 导入」之类的映射：
//    否则改一个词要改两处，两处不一致时页面不会报错，只会说出两种来源名。
const sourceKinds = ref<SourceKindSummary[]>([])
const sourcesVisible = ref(false)
const sourcesLoading = ref(false)
const sourcesError = ref('')
const sources = ref<SourceOverview | null>(null)

/** 只决定颜色，不决定口径：灰 = 没来源，橙 = 有批次号但没认出来，其余用默认蓝 */
function sourceTagType(kind?: string): 'info' | 'warning' | '' {
  if (kind === 'unlabeled') return 'info'
  if (kind === 'other') return 'warning'
  return ''
}

function sourceHint(kind?: string): string {
  const k = sourceKinds.value.find((x) => x.kind === kind)
  return k?.hint || k?.label || ''
}

function sourceTip(row: any): string {
  const hint = sourceHint(row.source_kind) || row.source_label || '来源'
  return row.import_batch ? `${hint}｜批次 ${row.import_batch}` : hint
}

/** 筛选项要跟着库走（新增了来源就会多一项），所以不写死；失败就留空，不假装有选项 */
async function loadSourceKinds() {
  try {
    const res = await temporalApi.getTaskSources()
    sourceKinds.value = res.data.kinds
  } catch {
    sourceKinds.value = []
  }
}

async function openSources() {
  sourcesVisible.value = true
  sourcesLoading.value = true
  sourcesError.value = ''
  try {
    const res = await temporalApi.getTaskSources()
    sources.value = res.data
    // 顺手把筛选项刷新 —— 用户点开这个弹窗，多半就是想核「这些数怎么来的」
    sourceKinds.value = res.data.kinds
  } catch {
    // 不能静默留白：空白弹窗会被读成「我本来就没有来源数据」
    sourcesError.value = '来源数据没读出来（接口异常），请稍后再试'
    sources.value = null
  } finally {
    sourcesLoading.value = false
  }
}

function onSourceChange() {
  // 换来源就把「只看某一批」清掉：留着会变成「来源=CSV + 批次=worklog」的空交集，
  // 界面上只看到一片「暂无数据」，看不出是自己筛空了。
  filter.batch = ''
  applyFilter()
}

function clearBatch() {
  filter.batch = ''
  applyFilter()
}

/** 从汇总点进某个来源（关掉弹窗，落回清单） */
function applySource(kind: string) {
  filter.source = kind
  filter.batch = ''
  sourcesVisible.value = false
  applyFilter()
}

/** 从批次行钻到那几条：批次级精确筛选，时间范围要清掉，否则会「看着 0 条」 */
function drillBatch(row: SourceBatchItem) {
  filter.source = row.kind
  filter.batch = row.batch || ''
  filter.dateRange = []
  sourcesVisible.value = false
  applyFilter()
}

// ─── 时间列展示 ───────────────────────────────────────────────────────────
// 一行 = 一条 ATracker 原始记录（v3.58.5 起不再按「任务名 + 日期」合并）：
//   start_time / end_time / duration_hours 同属该条记录 → 「时长 == 结束 − 开始」。
// 若仍不一致（源数据里计时器暂停等），以「记录时长」为准，这里显式标出来避免误读。

// 🔴 任务说明（`task_description`）是**导入的工作日志**，自带换行与缩进。
//    表格里要压成**一行**才省略得掉 —— `white-space: nowrap` 遇到 `\n` 仍会换行，
//    所以先把所有连续空白（含换行）归一成一个空格。
function flatDesc(v: string): string {
  return String(v).replace(/\s+/g, ' ').trim()
}

function endTimeText(row: any): string {
  const e = String(row.end_time || '')
  if (!e) return ''
  const start = String(row.start_time || '')
  // 跨零点（全库仅 3 条）才补日期，其余只显示 HH:mm
  if (start && start.slice(0, 10) !== e.slice(0, 10)) return `${e.slice(5, 10)} ${e.slice(11, 16)}`
  return e.slice(11, 16)
}

function spanMinutes(row: any): number | null {
  if (!row.start_time || !row.end_time) return null
  const s = Date.parse(String(row.start_time).replace(' ', 'T'))
  const e = Date.parse(String(row.end_time).replace(' ', 'T'))
  if (Number.isNaN(s) || Number.isNaN(e)) return null
  return (e - s) / 60000
}

function fmtMinutes(min: number): string {
  const m = Math.max(0, Math.round(min))
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

// ─── 弹窗内的时长自动计算（v3.58.6）──────────────────────────────────────────
function fmtLocal(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:00`
}

/** DRF 返回 ISO（`2026-09-17T19:30:00+08:00`）→ 日期选择器 value-format 可吃的本地时刻串 */
function isoToInput(v: string | null): string {
  if (!v) return ''
  const s = String(v)
  return s.includes('T') ? s.slice(0, 19).replace('T', ' ') : s
}

/** 弹窗内「结束 − 开始」的分钟数；任一端缺失/非法 → null */
const formSpanMin = computed<number | null>(() => {
  const s = editForm.start_time ? Date.parse(editForm.start_time.replace(' ', 'T')) : NaN
  const e = editForm.end_time ? Date.parse(editForm.end_time.replace(' ', 'T')) : NaN
  if (Number.isNaN(s) || Number.isNaN(e)) return null
  return (e - s) / 60000
})
const formSpanOk = computed(() => formSpanMin.value !== null && formSpanMin.value > 0)
const formDurationText = computed(() => (formSpanOk.value ? (formSpanMin.value as number / 60).toFixed(2) : ''))
const formHhmmText = computed(() => (formSpanOk.value ? fmtMinutes(formSpanMin.value as number) : ''))

// 容差 2 分钟：吸收秒级存取与 duration_display 向下取整的误差
function spanMismatch(row: any): boolean {
  const span = spanMinutes(row)
  if (span === null || row.duration_hours == null) return false
  return Math.abs(span - Number(row.duration_hours) * 60) > 2
}

function durationTip(row: any): string {
  const span = spanMinutes(row) ?? 0
  return `起止跨度 ${fmtMinutes(span)}（${String(row.start_time).slice(11, 16)} → ${String(row.end_time).slice(11, 16)}），记录时长 ${fmtMinutes(Number(row.duration_hours) * 60)}；不一致时以「记录时长」为准`
}

async function loadTasks() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: 20 }
    if (filter.dateRange?.length === 2) { params.date_from = filter.dateRange[0]; params.date_to = filter.dateRange[1] }
    if (filter.activity_type) params.activity_type = filter.activity_type
    if (filter.attribution) params.attribution = filter.attribution
    if (filter.unclassified) params.unclassified = '1'
    if (filter.source) params.source = filter.source
    if (filter.batch) params.import_batch = filter.batch
    if (filter.keyword.trim()) params.search = filter.keyword.trim()
    const res = await temporalApi.getTaskList(params)
    const data = res.data
    tasks.value = (data.results || data) as any[]
    total.value = data.count ?? tasks.value.length
  } catch { tasks.value = [] } finally { loading.value = false }
}

function applyFilter() { page.value = 1; loadTasks() }

/** 计时结束后回第 1 页：新记录排在最前，停在旧页会「看起来没记上」 */
function onTimerChanged() { page.value = 1; loadTasks() }
function resetFilter() {
  filter.dateRange = []; filter.activity_type = ''; filter.attribution = ''; filter.keyword = ''
  filter.unclassified = false; filter.source = ''; filter.batch = ''
  applyFilter()
}
function onSelectionChange(rows: any[]) { selectedRows.value = rows }
function clearSelection() { selectedRows.value = []; tableRef.value?.clearSelection() }

async function applyBulk() {
  if (!selectedRows.value.length || !bulkForm.activity_type) return
  saving.value = true
  try {
    const res = await store.batchSetMeta({
      task_names: selectedRows.value.map((r) => r.task_name),
      activity_type: bulkForm.activity_type,
      attribution: bulkForm.attribution || null,
    })
    ElMessage.success(`已更新 ${res.updated} 个任务`)
    bulkVisible.value = false
    await loadTasks()
  } catch { ElMessage.error('批量失败') } finally { saving.value = false }
}

/** 拉「最近常用」候选。每次打开新增弹窗都重拉 —— 不同阶段关注点不同，不缓存。 */
function loadFrequentNames() {
  frequentLoading.value = true
  frequentError.value = false
  temporalApi.getFrequentTaskNames({ months: 3, limit: 10 })
    .then((res) => {
      const d = res.data
      frequentNames.value = d?.items ?? []
      frequentMonths.value = d?.months ?? 3
    })
    .catch(() => {
      // 拉不到不阻断新增，但必须让用户看见「没读出来」——
      // 否则一片空白会被读成「我本来就没有常用任务」。
      frequentNames.value = []
      frequentError.value = true
    })
    .finally(() => { frequentLoading.value = false })
}

function togglePick(name: string) {
  if (pickedName.value === name) {
    // 再点一次 = 取消：输入框恢复成选中前手输的内容
    pickedName.value = ''
    editForm.task_name = stashedName
  } else {
    // 只有从「未选」切到标签时才暂存；A → B 换标签不能覆盖，
    // 否则取消后会丢掉最初手输的内容
    if (!pickedName.value) stashedName = editForm.task_name
    pickedName.value = name
    editForm.task_name = name
  }
  nameError.value = ''
}

function openCreate() {
  editingId.value = null
  pickedName.value = ''
  stashedName = ''
  nameError.value = ''
  // 默认「刚刚过去的一小时」：手动补记时改动最小，且一打开就能看到时长
  const now = new Date()
  now.setSeconds(0, 0)
  editForm.task_name = ''
  editForm.task_description = ''
  editForm.start_time = fmtLocal(new Date(now.getTime() - 3600_000))
  editForm.end_time = fmtLocal(now)
  editForm.notes = ''
  editVisible.value = true
  // 每次打开都重拉：候选必须跟着「最近 3 个月的实际记录」走，不做缓存
  loadFrequentNames()
}

function openEdit(row: any) {
  editingId.value = row.id
  pickedName.value = ''
  stashedName = ''
  nameError.value = ''
  editForm.task_name = row.task_name
  editForm.task_description = row.task_description || ''
  editForm.start_time = isoToInput(row.start_time)
  editForm.end_time = isoToInput(row.end_time)
  editForm.notes = row.notes || ''
  editVisible.value = true
}

/**
 * 保存前的「时段重叠」确认 —— 只提示，不否决。
 *
 * 🔴 为什么不是硬拦：本库里重叠是**合法形态**（「牛马工作 08:00-18:00」之内再细分
 *    「代码编程」），硬拦会把「补记细分」这条路一起堵死，而且 CSV 导入 / 计时器入账
 *    写的是同一张表。所以这里只把「撞了哪些」摆给用户看，由他自己决定。
 *
 * 判据（交集 ≥60s、是否同名、排序）全在后端 `services.find_overlaps`，
 * 前端不复制阈值 —— 否则改一处漏一处还不报错。
 *
 * 返回 true = 继续保存；false = 用户选择返回修改。
 */
async function confirmOverlap(): Promise<boolean> {
  let data: OverlapCheckData
  try {
    const res = await temporalApi.checkTaskOverlap({
      start_time: editForm.start_time,
      end_time: editForm.end_time,
      exclude_id: editingId.value || undefined,
      task_name: editForm.task_name.trim(),
    })
    data = res.data
  } catch {
    // 查不成不阻断保存（出口不能自关），但必须说清楚 —— 不能装作查过了
    ElMessage.warning('没能完成时段重叠检查（接口异常），已跳过提示，保存继续')
    return true
  }
  if (!data.has_overlap) return true

  const lines = data.conflicts.map(c =>
    `${c.task_name}　${c.start_time} ~ ${c.end_time}（重叠 ${c.overlap_minutes} 分钟）`,
  )
  const head = data.same_name_count > 0
    // 纯文本渲染，别写 markdown 星号 —— 会原样显示出来
    ? `这段时间已有 ${data.same_name_count} 条同名记录，很可能是重复新增：`
    : '这段时间已有下列记录（任务名不同，可能是「大段 + 段内细分」的合法并存）：'
  try {
    await ElMessageBox.confirm(
      `${head}\n\n${lines.join('\n')}\n\n仍要保存吗？`,
      '时段重叠提醒',
      {
        customClass: 'overlap-confirm',
        confirmButtonText: '仍要保存',
        cancelButtonText: '返回修改',
        type: data.same_name_count > 0 ? 'warning' : 'info',
      },
    )
    return true
  } catch {
    return false
  }
}

async function saveEdit() {
  if (!editForm.task_name.trim()) {
    // 一处判空同时覆盖两种来源：选中的标签名与手输值都写在 editForm.task_name 上
    nameError.value = '任务名称必填：选一个常用任务，或手动输入'
    ElMessage.warning(nameError.value)
    return
  }
  nameError.value = ''
  if (!editForm.start_time) { ElMessage.warning('请选择开始时间'); return }
  if (!editForm.end_time) { ElMessage.warning('请选择结束时间（时长由起止时间自动计算）'); return }
  if (!formSpanOk.value) { ElMessage.error('结束时间需晚于开始时间；跨零点请把结束时间选到次日'); return }
  if (!(await confirmOverlap())) return
  saving.value = true
  try {
    // 不提交 duration_hours —— 时长由后端按「结束 − 开始」算，避免两处口径打架
    const payload = {
      task_name: editForm.task_name.trim(),
      task_description: editForm.task_description,
      start_time: editForm.start_time,
      end_time: editForm.end_time,
      notes: editForm.notes,
    }
    if (editingId.value) {
      await temporalApi.updateTask(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await temporalApi.createTask(payload)
      page.value = 1
      ElMessage.success(`已新增 ${(formSpanMin.value! / 60).toFixed(2)} 小时`)
    }
    editVisible.value = false
    loadTasks()
  } catch (e: any) {
    // 后端校验（结束 ≤ 开始）会把原因放在 end_time 字段上，透出来比「保存失败」有用
    const detail = e?.response?.data?.end_time
    ElMessage.error(Array.isArray(detail) ? detail[0] : (detail || '保存失败'))
  } finally { saving.value = false }
}

// 🔴 支持 `?date_from=&date_to=` 预置筛选（v3.64.12）：仪表盘「今天的三条线」
//    点进来时应直接落在那一天。不读 query 的话，跳过来会显示"全部记录"，
//    用户还得自己再选一次日期 —— 那个链接就成了假按钮。
const route = useRoute()

onMounted(async () => {
  const df = route.query.date_from
  const dt = route.query.date_to
  if (typeof df === 'string' && typeof dt === 'string' && df && dt) {
    filter.dateRange = [df, dt]
  }
  loadSourceKinds()
  await loadTasks()
})
</script>

<style scoped lang="scss">
.task-list-view { padding: 16px;
  .page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px;
    .page-title { margin: 0; font-size: 18px; font-weight: 600; }
    // 按钮组靠右：标题占左，出口集中在一处（这一页是主入口，不再有「返回」）
    .header-actions { margin-left: auto; display: flex; align-items: center; gap: 8px; } }
  .filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  // 任务列：两行（任务名 + 说明），都单行省略。
  // 🔴 列宽给**固定值**而不再用 min-width —— 无宽度的列会被 el-table 拉去吸收剩余宽度，
  //    这正是「任务名很短、那一列却空出一条」的原因。
  .task-cell { line-height: 1.4;
    .task-name { font-weight: 500; color: #1f2937; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .task-desc { font-size: 12px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: default; }
  }
  .bulk-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; font-size: 13px; color: #4b5563; }
  .muted { color: #b8bcc4; }
  .th-tip { border-bottom: 1px dashed #cbd5e1; cursor: help; }
  // 时长 ≠ 起止跨度（源数据本身如此），用琥珀色 + 星标提示，避免误读为「算错了」
  .dur-multi { color: #b45309; cursor: help;
    .dur-mark { font-style: normal; margin-left: 1px; }
  }
  // 弹窗内自动算出的时长（只读，不再手填）
  .dur-auto { display: flex; align-items: baseline; gap: 8px; font-size: 13px; color: #4b5563;
    .dur-value { font-size: 16px; font-weight: 600; color: #0f766e;
      small { margin-left: 2px; font-size: 11px; font-weight: 400; color: #64748b; } }
    .dur-hhmm { font-size: 12px; color: #94a3b8; }
    .dur-err { font-size: 12px; color: #dc2626; }
  }
  // 任务名称：最近常用标签组 + 输入框（两者共用一个值，选中时输入框禁用）
  .name-field { width: 100%; }
  .freq-block { margin-bottom: 6px; }
  .freq-row { display: flex; align-items: center; flex-wrap: wrap; }
  .freq-label { margin: 0 8px 6px 0; font-size: 12px; color: #94a3b8; white-space: nowrap; }
  .freq-tag { margin: 0 6px 6px 0; font-size: 12px; }
  .freq-hint { margin-top: 2px; font-size: 12px; line-height: 1.6; color: #94a3b8; }
  .freq-warn { color: #b45309; }
  // 手工新增弹窗：录入当时就说清「这条会被记成什么来源」（左缩进对齐 label 宽度）
  .src-hint { margin: -2px 0 0 80px; font-size: 12px; line-height: 1.6; color: #94a3b8; }

  // ─── 来源批次弹窗（v3.64.33）───
  .src-body { min-height: 80px; }
  .src-err { padding: 28px 0; text-align: center; font-size: 13px; color: #b45309; }
  .src-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 13px;
    .src-total { font-size: 15px; font-weight: 600; color: #0f172a; }
    .src-sub { color: #94a3b8; } }
  .src-kinds { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
  // 用 button 而不是 el-tag：它得能点（看着像按钮就得能点）
  .src-kind { display: inline-flex; align-items: baseline; gap: 6px; padding: 5px 10px;
    border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; cursor: pointer;
    font-size: 12px; color: #475569; font-family: inherit; line-height: 1.4;
    b { font-weight: 600; color: #1f2937; }
    span { color: #94a3b8; font-variant-numeric: tabular-nums; }
    &:hover { border-color: #94a3b8; background: #fff; } }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: #334155; }
  // 批次的时间跨度：首条 / 末条各一行，行高固定，tnum 让数字对齐
  .span-two { font-size: 12px; line-height: 1.45; color: #475569; white-space: nowrap;
    font-variant-numeric: tabular-nums;
    .span-to { color: #94a3b8; } }
  .src-note { margin-top: 10px; font-size: 12px; line-height: 1.7; color: #94a3b8; }
}

// 重叠提醒弹窗是挂在 body 上的，scoped 样式进不去 ⇒ 用 :global。
// 消息体里用 \n 分行（没有走 HTML 渲染，避免任务名被当标签解析），
// 必须显式 pre-line 才能让换行显示出来。
:global(.overlap-confirm .el-message-box__message) {
  white-space: pre-line;
  line-height: 1.7;
}
</style>
