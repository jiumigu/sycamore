<template>
  <div class="health-check">
    <h2 class="page-title">🩺 身体健康自查</h2>
    <p class="subtitle">8 大系统 · 31 项指标，定期追踪身体信号。</p>

    <el-card class="check-form">
      <el-form :model="form" label-position="top">
        <el-collapse v-model="activePanels">
          <el-collapse-item v-for="(fields, systemName) in SYSTEM_GROUPS" :key="systemName" :title="systemIcon(systemName) + ' ' + systemName" :name="systemName">
            <template v-for="field in fields" :key="field">
              <div v-if="NUMERIC_FIELDS.includes(field)" class="field-group">
                <div class="field-label">{{ NUMERIC_LABELS[field]?.label || field }}</div>
                <div class="numeric-row">
                  <el-input-number v-model="form[field]" :min="0" :max="NUMERIC_LABELS[field]?.max ?? 999" style="width:100%" />
                  <span class="numeric-unit">{{ NUMERIC_LABELS[field]?.unit || '' }}</span>
                </div>
              </div>
              <div v-else class="field-group">
                <div class="field-label">{{ FIELD_DEFS[field]?.label || field }}</div>
                <el-radio-group v-model="form[field]" class="field-radios">
                  <el-radio v-for="opt in FIELD_DEFS[field]?.options" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </el-radio>
                </el-radio-group>
              </div>
            </template>
            <!-- spots_location: 仅在 spots=有时显示 -->
            <el-form-item v-if="systemName === '皮肤' && form.spots === '有'" label="痣/斑部位">
              <el-input v-model="form.spots_location" placeholder="记录部位、大小、颜色变化等" />
            </el-form-item>
          </el-collapse-item>
        </el-collapse>

        <el-divider />
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="补充身体感受或记录" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="检查日期">
              <el-date-picker v-model="form.check_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" size="large" :loading="saving" @click="handleCheck">
            {{ saving ? '提交中...' : '提交检查' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 结果卡片 -->
    <el-card v-if="result" class="check-result" :class="resultClass">
      <div class="result-score">{{ result.health_score }} <span class="result-unit">分</span></div>
      <div v-if="result.score_change !== null" class="result-change" :class="result.score_change > 0 ? 'up' : result.score_change < 0 ? 'down' : ''">
        {{ result.score_change > 0 ? '↑' : result.score_change < 0 ? '↓' : '—' }} 较上次 {{ Math.abs(result.score_change) }} 分
      </div>
      <div class="result-bar">
        <div class="bar-label">评分分布</div>
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: Math.min(100, result.health_score) + '%' }" />
        </div>
        <div class="bar-labels">
          <span>0</span>
          <span>50</span>
          <span>100+</span>
        </div>
      </div>
      <div v-if="result.alert_items" class="result-alerts">
        <div class="alerts-title">⚠️ 需关注</div>
        <div class="alerts-text">{{ result.alert_items }}</div>
      </div>
      <div v-else class="result-ok">✅ 所有指标正常</div>
    </el-card>

    <!-- 历史记录 -->
    <el-card class="check-history">
      <template #header>
        <div class="history-header">
          <span>📋 检查历史</span>
          <el-button v-if="history.length > 0" text type="danger" size="small" @click="clearAll">清空</el-button>
        </div>
      </template>

      <!-- 趋势图 -->
      <div v-if="history.length >= 2" class="trend-chart">
        <div ref="chartRef" style="height: 200px" />
      </div>

      <el-table v-if="history.length > 0" :data="history" style="width:100%;font-size:13px">
        <el-table-column prop="check_date" label="日期" width="110">
          <template #default="{ row }">
            <span style="white-space:nowrap">{{ row.check_date }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="health_score" label="健康分" width="70" />
        <el-table-column label="变化" width="70">
          <template #default="{ row }">
            <span v-if="row.score_change !== null" :class="row.score_change > 0 ? 'change-up' : row.score_change < 0 ? 'change-down' : 'change-flat'">
              {{ row.score_change > 0 ? '+' : '' }}{{ row.score_change }}
            </span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="异常项" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.alert_items" class="alert-preview">{{ row.alert_items }}</span>
            <span v-else class="all-good">✅ 正常</span>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <span class="action-btns">
              <el-button size="small" @click="viewDetail(row)">查看</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
            </span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无检查记录" />
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="showDetail" title="检查详情" width="500px">
      <template v-if="detailRecord">
        <div class="detail-grid">
          <div v-for="(val, key) in detailRecord" :key="key" class="detail-field" v-show="!['id', 'check_date', 'health_score', 'last_score', 'score_change', 'alert_items', 'notes', 'created_at'].includes(key)">
            <span class="detail-label">{{ FIELD_LABELS[key as string] || key }}</span>
            <span class="detail-value">{{ val ?? '—' }}</span>
          </div>
        </div>
        <div v-if="detailRecord.notes" class="detail-notes">
          <div class="detail-label">备注</div>
          <div class="detail-value">{{ detailRecord.notes }}</div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { SYSTEM_GROUPS, FIELD_DEFS, NUMERIC_FIELDS } from '../../types/healthCheckTypes'
import * as healthCheckApi from '../../api/healthCheckApi'
import type { HealthSelfCheck } from '../../types/healthCheckTypes'

const NUMERIC_LABELS: Record<string, { label: string; unit: string; max: number }> = {
  stool_count: { label: '大便次数', unit: '次/周', max: 50 },
  sleep_latency: { label: '入睡时间', unit: '分钟', max: 120 },
  awakenings: { label: '夜间醒来次数', unit: '次', max: 20 },
}

const FIELD_LABELS: Record<string, string> = {
  headache: '头痛', dizzy: '头晕', hairloss: '脱发', memory: '记忆力',
  vision: '视力', ear: '耳鸣', ulcer: '口腔溃疡', gum: '牙龈出血',
  allergy: '鼻塞/过敏', spots: '新发痣/斑', spots_location: '痣/斑部位',
  rash: '皮疹', wound_healing: '伤口愈合', joint: '关节疼痛',
  numbness: '手脚发麻', muscle: '肌肉酸痛', finger_flex: '手指灵活性',
  appetite: '食欲', bloating: '腹胀', abdominal_pain: '腹痛',
  reflux: '胃酸反流', stool_count: '大便次数', stool_type: '大便性状',
  urination_pain: '尿频/尿急/尿痛', nocturia: '夜尿次数',
  sleep_latency: '入睡时间', awakenings: '夜醒次数', morning_energy: '晨起精力',
  snoring: '打鼾', fatigue: '疲劳感', mood: '情绪低落',
  afternoon_fatigue: '午后犯困', interest_change: '兴趣变化',
}

const activePanels = ref(Object.keys(SYSTEM_GROUPS))
const saving = ref(false)
const result = ref<HealthSelfCheck | null>(null)
const history = ref<HealthSelfCheck[]>([])
const chartRef = ref<HTMLDivElement>()
const detailRecord = ref<HealthSelfCheck | null>(null)
const showDetail = ref(false)

function systemIcon(name: string): string {
  const icons: Record<string, string> = {
    '头部': '🧠', '五官': '👁️', '皮肤': '🧴', '四肢/肌肉': '💪',
    '消化系统': '🫃', '泌尿系统': '🚻', '睡眠': '😴', '精力/情绪': '⚡',
  }
  return icons[name] || '📋'
}

function defaultForm(): Record<string, any> {
  const f: Record<string, any> = {
    check_date: new Date().toISOString().slice(0, 10),
    notes: '',
    spots_location: '',
  }
  for (const fields of Object.values(SYSTEM_GROUPS)) {
    for (const field of fields) {
      if (NUMERIC_FIELDS.includes(field)) {
        f[field] = null
      } else {
        const def = FIELD_DEFS[field]
        f[field] = def?.options?.[0]?.value || ''
      }
    }
  }
  return f
}

const form = reactive<Record<string, any>>(defaultForm())

async function handleCheck() {
  if (!form.check_date) {
    ElMessage.warning('请选择检查日期')
    return
  }

  saving.value = true
  try {
    const data = { ...form }
    for (const k of NUMERIC_FIELDS) {
      if (data[k] === '' || data[k] === undefined) data[k] = null
    }
    const resp = await healthCheckApi.createHealthCheck(data)
    result.value = resp.data as HealthSelfCheck
    ElMessage.success('检查完成')
    await fetchHistory()
    Object.assign(form, defaultForm())
  } catch {
    ElMessage.error('提交失败')
  } finally {
    saving.value = false
  }
}

async function fetchHistory() {
  try {
    const resp = await healthCheckApi.getHealthCheckList({ page_size: 50 })
    const data = resp.data ?? resp
    history.value = Array.isArray(data) ? data as HealthSelfCheck[] : (data.results ?? []) as HealthSelfCheck[]
    await nextTick()
    renderChart()
  } catch {
    history.value = []
  }
}

async function handleDelete(id: number) {
  try {
    await healthCheckApi.deleteHealthCheck(id)
    ElMessage.success('已删除')
    await fetchHistory()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空所有检查记录？', '确认', {
      confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning',
    })
    for (const r of history.value) {
      await healthCheckApi.deleteHealthCheck(r.id)
    }
    history.value = []
    ElMessage.success('已清空')
  } catch { /* cancelled */ }
}

function viewDetail(record: HealthSelfCheck) {
  detailRecord.value = record
  showDetail.value = true
}

function renderChart() {
  if (history.value.length < 2 || !chartRef.value) return
  const chart = echarts.init(chartRef.value)
  const sorted = [...history.value].reverse()
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: {
      type: 'category',
      data: sorted.map(r => r.check_date.slice(5)),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', min: 0, axisLabel: { fontSize: 11 } },
    series: [{
      type: 'line',
      data: sorted.map(r => r.health_score),
      smooth: true,
      lineStyle: { color: '#10B981', width: 2 },
      areaStyle: { color: 'rgba(16, 185, 129, 0.1)' },
      itemStyle: { color: '#10B981' },
    }],
  })
}

const resultClass = computed(() => {
  if (!result.value) return ''
  const s = result.value.health_score
  if (s <= 10) return 'verdict-good'
  if (s <= 20) return 'verdict-ok'
  if (s <= 35) return 'verdict-warn'
  return 'verdict-danger'
})

onMounted(fetchHistory)
</script>

<style scoped>
.health-check {
  width: 100%;
}
.page-title { font-size: 22px; font-weight: 700; margin: 0 0 4px; }
.subtitle { font-size: 13px; color: #9CA3AF; margin: 0 0 20px; }

.check-form { margin-bottom: 18px; }
.check-form :deep(.el-collapse-item__header) { font-weight: 600; font-size: 15px; }

.field-group { margin-bottom: 16px; }
.field-label { font-size: 14px; font-weight: 500; color: #374151; margin-bottom: 8px; }
.numeric-row { display: flex; align-items: center; gap: 8px; }
.numeric-row :deep(.el-input-number) { flex: 1; }
.numeric-unit { font-size: 13px; color: #6B7280; white-space: nowrap; }
.field-radios { display: flex; flex-wrap: wrap; gap: 6px; }
.field-radios :deep(.el-radio) { margin-right: 0; min-width: 90px; }

/* 表格 */
:deep(.el-table) {
  font-size: 13px;
}
:deep(.el-table .el-table__cell) {
  padding: 8px 6px;
  white-space: nowrap;
}
.action-btns {
  display: flex;
  gap: 4px;
  white-space: nowrap;
}

/* 结果卡片 */
.check-result {
  margin-bottom: 18px; text-align: center; padding: 24px 20px;
  border-radius: 10px; border: none;
}
.result-score { font-size: 48px; font-weight: 700; line-height: 1; }
.result-unit { font-size: 18px; font-weight: 400; color: #9CA3AF; }
.result-change { font-size: 14px; margin: 4px 0 12px; font-weight: 500; }
.result-change.up { color: #10B981; }
.result-change.down { color: #EF4444; }
.result-change.fl { color: #6B7280; }

.result-bar { margin: 12px auto; max-width: 300px; }
.bar-label { font-size: 11px; color: #9CA3AF; margin-bottom: 4px; }
.bar-track { height: 8px; background: #E5E7EB; border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, #10B981, #F59E0B, #EF4444); border-radius: 4px; transition: width 0.5s; }
.bar-labels { display: flex; justify-content: space-between; font-size: 10px; color: #9CA3AF; margin-top: 2px; }

.result-alerts { margin-top: 12px; text-align: left; }
.alerts-title { font-size: 13px; font-weight: 600; color: #DC2626; margin-bottom: 4px; }
.alerts-text { font-size: 13px; color: #6B7280; line-height: 1.6; white-space: pre-wrap; }
.result-ok { margin-top: 12px; font-size: 14px; }

.verdict-good { background: #ecfdf5; }
.verdict-ok { background: #fffbeb; }
.verdict-warn { background: #fff7ed; }
.verdict-danger { background: #fef2f2; }

/* 历史 */
.check-history :deep(.el-card__body) { padding: 16px; }
.history-header { display: flex; justify-content: space-between; align-items: center; }
.trend-chart { margin-bottom: 16px; }
.change-up { color: #10B981; font-weight: 500; }
.change-down { color: #EF4444; font-weight: 500; }
.change-flat { color: #6B7280; }
.alert-preview { font-size: 12px; color: #6B7280; }
.all-good { font-size: 12px; color: #10B981; }

/* 详情弹窗 */
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
}
.detail-field {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px solid #f3f4f6;
}
.detail-field .detail-label {
  font-size: 12px;
  color: #9CA3AF;
}
.detail-field .detail-value {
  font-size: 13px;
  color: #1F2937;
  font-weight: 500;
}
.detail-notes {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #E5E7EB;
}
.detail-notes .detail-label {
  font-size: 12px;
  color: #9CA3AF;
  margin-bottom: 4px;
}
.detail-notes .detail-value {
  font-size: 13px;
  color: #1F2937;
  white-space: pre-wrap;
}
</style>
