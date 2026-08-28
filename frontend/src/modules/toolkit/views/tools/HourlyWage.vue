<template>
  <div class="hourly-wage">
    <h2>⏱️ 时薪计算器</h2>
    <p class="subtitle">月薪 ÷ 真实投入时间 = 时薪。看清自己的时间价值。</p>

    <el-card class="calc-form">
      <el-alert v-if="editingId" title="正在编辑已有记录" type="info" show-icon :closable="false" style="margin-bottom: 12px">
        <el-button size="small" text @click="cancelEdit">取消编辑</el-button>
      </el-alert>
      <el-form :model="form" label-width="130px" size="small">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="记录名称">
              <el-input v-model="form.name" placeholder="如：当前工作、Offer对比" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="月薪">
              <el-input-number v-model="form.monthly_salary" :min="0" :precision="2" style="width:100%" />
              <span class="suffix">元</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="计算模式">
          <el-radio-group v-model="form.calc_mode">
            <el-radio value="formal">🏢 正式职业</el-radio>
            <el-radio value="freelance">🧑‍💻 自由职业</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- ===== 正式职业模式 ===== -->
        <template v-if="form.calc_mode === 'formal'">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="休息类型">
                <el-select v-model="form.rest_type">
                  <el-option label="双休" value="双休" />
                  <el-option label="单休" value="单休" />
                  <el-option label="大小周" value="大小周" />
                  <el-option label="不休" value="不休" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="上班时间">
                <el-time-picker v-model="form.work_start" format="HH:mm" value-format="HH:mm" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="下班时间">
                <el-time-picker v-model="form.work_end" format="HH:mm" value-format="HH:mm" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="午休时长">
                <el-input-number v-model="form.lunch_break" :min="0" :max="180" />
                <span class="suffix">分钟</span>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="单程通勤">
                <el-input-number v-model="form.commute_minutes" :min="0" :max="180" />
                <span class="suffix">分钟</span>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="备注">
                <el-input v-model="form.notes" placeholder="选填" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <!-- ===== 自由职业模式 ===== -->
        <template v-if="form.calc_mode === 'freelance'">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="单程通勤">
                <el-input-number v-model="form.commute_minutes" :min="0" :max="180" style="width:100%" />
                <span class="suffix">分钟/天</span>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="备注">
                <el-input v-model="form.notes" placeholder="选填" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-divider />

          <el-form-item label="工时模式">
            <el-radio-group v-model="form.freelance_time_mode">
              <el-radio value="fixed">📆 固定时长</el-radio>
              <el-radio value="flexible">🕐 弹性工时</el-radio>
            </el-radio-group>
          </el-form-item>

          <!-- 固定时长 -->
          <template v-if="form.freelance_time_mode === 'fixed'">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="月工作天数">
                  <el-input-number v-model="form.freelance_days" :min="1" :max="31" style="width:100%" />
                  <span class="suffix">天</span>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="日均工作时长">
                  <el-input-number v-model="form.freelance_hours_per_day" :min="0.5" :max="16" :precision="1" style="width:100%" />
                  <span class="suffix">小时</span>
                </el-form-item>
              </el-col>
            </el-row>
          </template>

          <!-- 弹性工时 -->
          <template v-if="form.freelance_time_mode === 'flexible'">
            <el-form-item label="每周工作时长">
              <div class="flexible-hours">
                <div v-for="(day, i) in weekDays" :key="i" class="day-row">
                  <span class="day-label">{{ day }}</span>
                  <el-input-number v-model="form.weekly_hours[i]" :min="0" :max="16" :precision="0.5" size="small" style="width:120px" />
                  <span class="suffix">h</span>
                </div>
              </div>
              <div class="hint">填写一周中每天的工作时长，未填视为0</div>
            </el-form-item>
            <el-form-item label="每月周数">
              <el-input-number v-model="form.freelance_weeks" :min="1" :max="5" style="width:150px" />
              <span class="suffix">周（默认4周）</span>
            </el-form-item>
          </template>
        </template>

        <el-divider>💵 额外收入来源</el-divider>
        <div class="extra-incomes">
          <div v-for="(source, index) in form.extra_incomes" :key="index" class="source-row">
            <el-input v-model="source.name" size="small" placeholder="来源名" style="width: 120px" />
            <el-input-number v-model="source.amount" :min="0" :precision="2" size="small" style="width: 160px" />
            <el-select v-model="source.period" size="small" style="width: 90px">
              <el-option label="/天" value="daily" />
              <el-option label="/月" value="monthly" />
              <el-option label="/年" value="yearly" />
            </el-select>
            <el-button size="small" type="danger" @click="removeExtraIncome(index)" circle>✕</el-button>
          </div>
          <el-button size="small" @click="addExtraIncome">+ 添加收入来源</el-button>
          <div class="hint">如副业、稿费、投资收益等工资之外的收入，将并入总收入和时薪计算</div>
        </div>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleCalculate">计算时薪</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 计算结果 -->
    <el-card v-if="result" class="result-card">
      <div class="result-main">
        <div class="result-label">真实时薪</div>
        <div class="result-value">¥{{ result.hourly_wage }}<span class="unit">/小时</span></div>
      </div>
      <el-divider />
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stat-label">月工作天数</div>
          <div class="stat-value">{{ result.work_days_per_month }}天</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">日工作小时</div>
          <div class="stat-value">{{ result.work_hours_per_day }}h</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">日通勤时间</div>
          <div class="stat-value">{{ form.commute_minutes * 2 }}分钟</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">月总投入</div>
          <div class="stat-value">{{ result.total_hours_per_month }}h</div>
        </el-col>
      </el-row>

      <!-- 收入构成 -->
      <div class="income-breakdown">
        <el-divider />
        <div class="breakdown-item">
          <span>💼 工资收入</span>
          <span class="breakdown-value">¥{{ fmt(result.salary_monthly) }}/月</span>
        </div>
        <div v-for="source in form.extra_incomes.filter(s => s.amount > 0)" :key="source.name + source.period + source.amount" class="breakdown-item">
          <span>💰 {{ source.name || '未命名来源' }}</span>
          <span class="breakdown-sub">¥{{ fmt(source.amount) }}/{{ periodLabel(source.period) }} ≈ ¥{{ fmt(convertToMonthly(source)) }}/月</span>
        </div>
        <el-divider />
        <div class="breakdown-total">
          <span>📊 月总收入</span>
          <span class="breakdown-total-value">¥{{ fmt(result.total_monthly) }}</span>
        </div>
      </div>

      <!-- 收支对比（与固定开销联动） -->
      <div v-if="latestExpense" class="comparison">
        <el-divider />
        <div class="comparison-title">💰 收支对比</div>
        <el-row :gutter="16">
          <el-col :span="8">
            <div class="compare-item income">
              <div>日收入</div>
              <div class="compare-value">¥{{ fmt(result.total_daily) }}</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="compare-item expense">
              <div>日支出</div>
              <div class="compare-value">¥{{ fmt(latestExpense.total_daily) }}</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="compare-item" :class="dailyBalance >= 0 ? 'positive' : 'negative'">
              <div>日结余</div>
              <div class="compare-value">{{ dailyBalance >= 0 ? '+' : '' }}¥{{ fmt(dailyBalance) }}</div>
            </div>
          </el-col>
        </el-row>
        <el-progress :percentage="expenseRatio" :color="expenseRatio > 80 ? '#f56c6c' : '#67c23a'" :stroke-width="8" style="margin-top: 12px" />
        <div class="insight-text">{{ expenseRatio > 80 ? '⚠️ 开销占比偏高' : '✅ 收支健康' }}（{{ expenseRatio }}%）</div>
      </div>
    </el-card>

    <!-- 历史记录 -->
    <el-card class="history-card">
      <template #header>
        <div class="card-header">
          <span>📋 计算历史</span>
          <el-tag size="small">{{ history.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="history" v-loading="loading" stripe size="small" style="width:100%">
        <el-table-column prop="name" label="名称" min-width="80" show-overflow-tooltip />
        <el-table-column label="月薪" width="90">
          <template #default="{ row }">{{ maskAmount(parseFloat(row.monthly_salary), privacyStore.privacyMode) }}</template>
        </el-table-column>
        <el-table-column label="模式" width="72">
          <template #default="{ row }">
            <el-tag v-if="row.calc_mode === 'freelance'" size="small" type="warning">自由</el-tag>
            <el-tag v-else size="small">正式</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时薪" width="100">
          <template #default="{ row }">¥{{ row.hourly_wage }}/h</template>
        </el-table-column>
        <el-table-column label="月收入" width="100">
          <template #default="{ row }">¥{{ fmt(row.total_monthly || row.monthly_salary) }}</template>
        </el-table-column>
        <el-table-column label="日收入" width="100">
          <template #default="{ row }">¥{{ fmt(row.total_daily || (Number(row.monthly_salary) / 30)) }}</template>
        </el-table-column>
        <el-table-column label="月投入" width="72">
          <template #default="{ row }">{{ row.total_hours_per_month }}h</template>
        </el-table-column>
        <el-table-column label="通勤" width="64">
          <template #default="{ row }">{{ row.commute_minutes * 2 }}分</template>
        </el-table-column>
        <el-table-column label="日期" width="88">
          <template #default="{ row }">{{ row.created_at?.slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="editRecord(row)">编辑</el-button>
            <el-button size="small" link type="primary" @click="copyRecord(row)">复制</el-button>
            <el-button size="small" link type="primary" @click="viewDetail(row)">查看</el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && history.length === 0" description="暂无计算记录" />
    </el-card>

    <!-- 查看详情 -->
    <el-dialog v-model="showDetailDialog" title="时薪详情" width="600px" append-to-body>
      <template v-if="viewingRecord">
        <div class="detail-header">
          <span class="detail-name">{{ viewingRecord.name || '未命名记录' }}</span>
          <span class="detail-date">{{ viewingRecord.created_at?.slice(0, 10) }}</span>
        </div>

        <el-divider />

        <!-- 收入构成 -->
        <div class="detail-section">
          <div class="section-title">💵 收入构成</div>
          <div class="detail-row">
            <span>💼 工资收入</span>
            <span>¥{{ fmt(viewingRecord.monthly_salary || 0) }}/月</span>
          </div>
          <div v-for="source in (viewingRecord.extra_incomes || [])" :key="source.name + source.period + source.amount" class="detail-row">
            <span>💰 {{ source.name || '未命名来源' }}</span>
            <span>¥{{ fmt(source.amount) }}/{{ periodLabel(source.period) }}</span>
          </div>
          <el-divider />
          <div class="detail-row total">
            <span>📊 月总收入</span>
            <span>¥{{ fmt(viewingRecord.total_monthly || viewingRecord.monthly_salary || 0) }}</span>
          </div>
          <div class="detail-row">
            <span>日收入</span>
            <span>¥{{ fmt(detailIncomeDaily) }}</span>
          </div>
          <div class="detail-row">
            <span>时薪</span>
            <span>¥{{ viewingRecord.hourly_wage }}/h</span>
          </div>
        </div>

        <!-- 工作时间 -->
        <el-divider />
        <div class="detail-section">
          <div class="section-title">⏱️ 工作时间</div>
          <div class="detail-row">
            <span>月投入</span>
            <span>{{ viewingRecord.total_hours_per_month }}h</span>
          </div>
          <div class="detail-row">
            <span>模式</span>
            <span>{{ viewingRecord.calc_mode === 'freelance' ? '自由职业' : '正式职业' }}</span>
          </div>
        </div>

        <!-- 收支联动 -->
        <el-divider />
        <div class="detail-section comparison-section">
          <div class="section-title">💰 收支联动</div>
          <div v-if="latestExpense">
            <div class="detail-row">
              <span>日收入</span>
              <span class="text-success">¥{{ fmt(detailIncomeDaily) }}</span>
            </div>
            <div class="detail-row">
              <span>日固定开销</span>
              <span class="text-danger">¥{{ fmt(latestExpense.total_daily) }}</span>
            </div>
            <el-divider />
            <div class="detail-row total">
              <span>日结余</span>
              <span :class="detailBalance >= 0 ? 'text-success' : 'text-danger'">
                {{ detailBalance >= 0 ? '+' : '' }}¥{{ fmt(detailBalance) }}
              </span>
            </div>
            <div class="detail-row">
              <span>开销占比</span>
              <span>{{ detailRatio }}%</span>
            </div>
            <el-progress :percentage="detailRatio" :color="detailRatio > 80 ? '#f56c6c' : '#67c23a'" :stroke-width="6" style="margin-top: 8px" />
            <div class="linked-expense-name">关联的固定开销：{{ latestExpense.name }}</div>
          </div>
          <div v-else class="no-link">
            暂无固定开销记录，
            <el-button type="primary" size="small" text @click="$router.push('/toolkit/fixed-expense')">去添加</el-button>
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
        <el-button type="primary" @click="copyRecord(viewingRecord); showDetailDialog = false">复制并编辑</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { maskAmount } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { getHourlyWageList, createHourlyWage, updateHourlyWage, deleteHourlyWage, getFixedExpenseList } from '../../api/toolkitApi'
import type { HourlyWageRecord, FixedExpenseRecord } from '../../types/toolkitTypes'

const privacyStore = usePrivacyStore()
const weekDays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

function defaultForm() {
  return {
    name: '',
    monthly_salary: 0,
    calc_mode: 'formal',
    // 正式职业
    rest_type: '双休',
    work_start: '09:00' as string | Date,
    work_end: '18:00' as string | Date,
    lunch_break: 60,
    // 自由职业
    freelance_time_mode: 'fixed',
    freelance_days: 22,
    freelance_hours_per_day: 8,
    weekly_hours: [8, 8, 8, 8, 8, 0, 0] as number[],
    freelance_weeks: 4,
    // 通用
    commute_minutes: 0,
    notes: '',
    // 额外收入来源
    extra_incomes: [] as Array<{ name: string; amount: number; period: 'daily' | 'monthly' | 'yearly' }>,
  }
}

const form = reactive(defaultForm())

const result = ref<HourlyWageRecord | null>(null)
const saving = ref(false)
const loading = ref(false)
const history = ref<HourlyWageRecord[]>([])
const latestExpense = ref<FixedExpenseRecord | null>(null)

const editingId = ref<number | null>(null)
const showDetailDialog = ref(false)
const viewingRecord = ref<HourlyWageRecord | null>(null)

const dailyBalance = computed(() =>
  result.value && latestExpense.value
    ? Number(result.value.total_daily) - Number(latestExpense.value.total_daily)
    : 0,
)

const expenseRatio = computed(() => {
  if (!result.value || !latestExpense.value) return 0
  const daily = Number(result.value.total_daily)
  if (daily <= 0) return 0
  return Math.min(100, Math.round((Number(latestExpense.value.total_daily) / daily) * 100))
})

// 详情弹窗用：以查看记录为主体计算收支联动
const detailIncomeDaily = computed(() => {
  if (!viewingRecord.value) return 0
  return Number(viewingRecord.value.total_daily) || (Number(viewingRecord.value.monthly_salary) / 30) || 0
})

const detailBalance = computed(() =>
  detailIncomeDaily.value - (latestExpense.value ? Number(latestExpense.value.total_daily) : 0),
)

const detailRatio = computed(() => {
  const income = viewingRecord.value
    ? Number(viewingRecord.value.total_monthly) || Number(viewingRecord.value.monthly_salary) || 1
    : 1
  const expense = (latestExpense.value ? Number(latestExpense.value.total_daily) : 0) * 30
  return Math.min(100, Math.round((expense / income) * 100))
})

function fmt(val: number | string) {
  const n = typeof val === 'string' ? parseFloat(val) : val
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function periodLabel(period: string): string {
  return { daily: '日', monthly: '月', yearly: '年' }[period] || period
}

function convertToMonthly(source: { amount: number; period: string }): number {
  if (!source.amount) return 0
  if (source.period === 'daily') return Math.round(source.amount * 30 * 100) / 100
  if (source.period === 'yearly') return Math.round((source.amount / 12) * 100) / 100
  return source.amount
}

function addExtraIncome() {
  form.extra_incomes.push({ name: '', amount: 0, period: 'monthly' })
}

function removeExtraIncome(index: number) {
  form.extra_incomes.splice(index, 1)
}

function fillForm(record: HourlyWageRecord) {
  form.calc_mode = record.calc_mode || 'formal'
  form.monthly_salary = Number(record.monthly_salary) || 0
  form.rest_type = record.rest_type || '双休'
  form.work_start = record.work_start || '09:00'
  form.work_end = record.work_end || '18:00'
  form.lunch_break = record.lunch_break || 60
  form.commute_minutes = record.commute_minutes || 0
  form.freelance_time_mode = record.freelance_time_mode || 'fixed'
  form.freelance_days = record.freelance_days || 22
  form.freelance_hours_per_day = Number(record.freelance_hours_per_day) || 8
  form.weekly_hours = record.weekly_hours || [0, 0, 0, 0, 0, 0, 0]
  form.freelance_weeks = record.freelance_weeks || 4
  form.extra_incomes = (record.extra_incomes || []).map(item => ({
    name: item.name || '',
    amount: Number(item.amount) || 0,
    period: (item.period === 'daily' || item.period === 'yearly' ? item.period : 'monthly') as 'daily' | 'monthly' | 'yearly',
  }))
  form.notes = record.notes || ''
  result.value = null
}

function editRecord(record: HourlyWageRecord) {
  editingId.value = record.id
  fillForm(record)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function copyRecord(record: HourlyWageRecord | null) {
  if (!record) return
  editingId.value = null
  form.name = record.name ? `${record.name}（副本）` : ''
  fillForm(record)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function cancelEdit() {
  editingId.value = null
  resetForm()
}

function viewDetail(record: HourlyWageRecord) {
  viewingRecord.value = record
  showDetailDialog.value = true
  fetchLatestExpense()
}

async function fetchLatestExpense() {
  try {
    const res = await getFixedExpenseList()
    const results = (res.data?.results || []) as FixedExpenseRecord[]
    latestExpense.value = results[0] || null
  } catch {
    latestExpense.value = null
  }
}

async function fetchHistory() {
  loading.value = true
  try {
    const res = await getHourlyWageList()
    history.value = (res.data?.results || []) as HourlyWageRecord[]
  } catch {
    history.value = []
  } finally {
    loading.value = false
  }
}

function formatDate(d: Date) {
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
}

async function handleCalculate() {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      name: form.name || '',
      monthly_salary: form.monthly_salary,
      calc_mode: form.calc_mode,
      commute_minutes: form.commute_minutes,
      notes: form.notes || '',
      extra_incomes: form.extra_incomes,
    }

    if (form.calc_mode === 'formal') {
      payload.rest_type = form.rest_type
      payload.work_start = typeof form.work_start === 'object' ? formatDate(form.work_start) : form.work_start
      payload.work_end = typeof form.work_end === 'object' ? formatDate(form.work_end) : form.work_end
      payload.lunch_break = form.lunch_break
    } else {
      payload.freelance_time_mode = form.freelance_time_mode
      payload.freelance_weeks = form.freelance_weeks
      if (form.freelance_time_mode === 'fixed') {
        payload.freelance_days = form.freelance_days
        payload.freelance_hours_per_day = form.freelance_hours_per_day
      } else {
        payload.weekly_hours = form.weekly_hours
      }
    }

    const res = editingId.value
      ? await updateHourlyWage(editingId.value, payload)
      : await createHourlyWage(payload)
    const record = res.data as HourlyWageRecord
    result.value = record
    editingId.value = null
    ElMessage.success(`时薪 ¥${record.hourly_wage}/小时`)
    await fetchHistory()
    await fetchLatestExpense()
  } catch {
    ElMessage.error('计算失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这条记录？', '确认')
    await deleteHourlyWage(id)
    ElMessage.success('已删除')
    history.value = history.value.filter(r => r.id !== id)
    if (result.value?.id === id) result.value = null
    if (editingId.value === id) editingId.value = null
    if (viewingRecord.value?.id === id) {
      viewingRecord.value = null
      showDetailDialog.value = false
    }
  } catch {
    // cancelled
  }
}

function resetForm() {
  Object.assign(form, defaultForm())
  result.value = null
}

onMounted(() => {
  fetchHistory()
  fetchLatestExpense()
})
</script>

<style scoped>
.hourly-wage { padding: 20px; }
.back-bar { display: flex; align-items: center; gap: 4px; margin-bottom: 16px; flex-wrap: nowrap; }
h2 { margin: 0 0 4px; font-size: 22px; font-weight: 700; color: #1F2937; }
.subtitle { margin: 0 0 20px; font-size: 14px; color: #6B7280; }
.calc-form { margin-bottom: 16px; }
.suffix { margin-left: 8px; font-size: 12px; color: #9CA3AF; white-space: nowrap; }
.hint { font-size: 11px; color: var(--el-text-color-secondary); line-height: 1.4; margin-top: 2px; }
.result-card { margin-bottom: 16px; text-align: center; padding: 16px; }
.result-main { padding: 20px 0; }
.result-label { font-size: 14px; color: #6B7280; margin-bottom: 8px; }
.result-value { font-size: 48px; font-weight: 700; color: #10B981; }
.unit { font-size: 18px; font-weight: 400; color: #9CA3AF; margin-left: 8px; }
.stat-label { font-size: 12px; color: #6B7280; margin-bottom: 4px; }
.stat-value { font-size: 18px; font-weight: 600; color: #1F2937; }
.history-card :deep(.el-card__header) { padding: 12px 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.flexible-hours { display: flex; flex-direction: column; gap: 8px; }
.day-row { display: flex; align-items: center; gap: 12px; }
.day-label { width: 36px; font-size: 13px; color: #374151; font-weight: 500; }

.extra-incomes {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;

  .source-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.income-breakdown {
  text-align: left;
  margin-top: 8px;
  max-width: 420px;
  margin-left: auto;
  margin-right: auto;

  .breakdown-item {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    font-size: 13px;
    color: #374151;
    padding: 3px 0;

    .breakdown-value { font-weight: 600; color: #1F2937; flex-shrink: 0; }
    .breakdown-sub { font-size: 12px; color: #9CA3AF; text-align: right; }
  }

  .breakdown-total {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    font-size: 15px;
    font-weight: 600;
    color: #1F2937;

    .breakdown-total-value { font-size: 20px; color: #10B981; font-weight: 700; }
  }
}

.comparison {
  text-align: left;
  max-width: 420px;
  margin: 8px auto 0;

  .comparison-title { font-size: 14px; font-weight: 600; color: #1F2937; margin-bottom: 8px; }

  .compare-item {
    text-align: center;
    padding: 10px 0;
    border-radius: 8px;
    background: #F3F4F6;

    .compare-value { font-size: 20px; font-weight: 700; margin-top: 4px; }

    &.income .compare-value { color: #10B981; }
    &.expense .compare-value { color: #F59E0B; }
    &.positive .compare-value { color: #10B981; }
    &.negative .compare-value { color: #EF4444; }
  }

  .insight-text {
    margin-top: 8px;
    font-size: 13px;
    text-align: center;
    color: #6B7280;
  }
}

.detail-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;

  .detail-name { font-size: 16px; font-weight: 600; color: #1F2937; }
  .detail-date { font-size: 12px; color: #9CA3AF; }
}

.detail-section {
  .section-title { font-size: 14px; font-weight: 600; color: #1F2937; margin-bottom: 6px; }

  .detail-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    font-size: 13px;
    color: #374151;
    padding: 3px 0;

    &.total { font-size: 14px; font-weight: 600; color: #1F2937; }
  }

  .text-success { color: #10B981; font-weight: 600; }
  .text-danger { color: #EF4444; font-weight: 600; }

  .linked-expense-name {
    margin-top: 8px;
    font-size: 12px;
    color: #9CA3AF;
  }

  .no-link {
    font-size: 13px;
    color: #6B7280;
  }
}
</style>
