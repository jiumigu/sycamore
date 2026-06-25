<template>
  <div class="hourly-wage">
    <div class="back-bar">
      <el-button text @click="$router.push('/toolkit')">
        <el-icon><ArrowLeft /></el-icon> 返回工具集
      </el-button>
    </div>

    <h2>⏱️ 时薪计算器</h2>
    <p class="subtitle">月薪 ÷ 真实投入时间 = 时薪。看清自己的时间价值。</p>

    <el-card class="calc-form">
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
        <el-table-column label="月投入" width="72">
          <template #default="{ row }">{{ row.total_hours_per_month }}h</template>
        </el-table-column>
        <el-table-column label="通勤" width="64">
          <template #default="{ row }">{{ row.commute_minutes * 2 }}分</template>
        </el-table-column>
        <el-table-column label="日期" width="88">
          <template #default="{ row }">{{ row.created_at?.slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="60" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && history.length === 0" description="暂无计算记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { maskAmount } from '@/shared/utils/privacy'
import { usePrivacyStore } from '@/core/privacy/stores/privacyStore'
import { getHourlyWageList, createHourlyWage, deleteHourlyWage } from '../../api/toolkitApi'
import type { HourlyWageRecord } from '../../types/toolkitTypes'

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
  }
}

const form = reactive(defaultForm())

const result = ref<HourlyWageRecord | null>(null)
const saving = ref(false)
const loading = ref(false)
const history = ref<HourlyWageRecord[]>([])

function fmt(val: number | string) {
  const n = typeof val === 'string' ? parseFloat(val) : val
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
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

    const res = await createHourlyWage(payload)
    const record = res.data as HourlyWageRecord
    result.value = record
    ElMessage.success(`时薪 ¥${record.hourly_wage}/小时`)
    await fetchHistory()
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
  } catch {
    // cancelled
  }
}

function resetForm() {
  Object.assign(form, defaultForm())
  result.value = null
}

onMounted(fetchHistory)
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
</style>
