<template>
  <div class="allocation-board">
    <!-- 月份选择 + 操作按钮 -->
    <div class="board-header">
      <el-date-picker
        v-model="selectedMonth"
        type="month"
        placeholder="选择月份"
        format="YYYY年MM月"
        value-format="YYYY-MM"
        @change="loadData"
      />
      <el-button type="primary" @click="showCommitmentDialog = true">
        <el-icon><Plus /></el-icon> 添加承诺
      </el-button>
      <el-button @click="openDecisionDialog">
        <el-icon><Edit /></el-icon> 记录决策
      </el-button>
    </div>

    <!-- 四张核心卡片 -->
    <el-row :gutter="16" class="summary-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="card-label">💳 手头现金</div>
            <el-input-number
              v-model="totalCash"
              :min="0"
              :step="1000"
              :precision="2"
              :controls="false"
              class="card-value-input"
            />
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card" style="border-left: 4px solid #f56c6c">
          <div class="card-content">
            <div class="card-label">📅 硬性承诺</div>
            <div class="card-value" style="color: #f56c6c">-{{ formatAmount(summary.commitments_total) }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card" style="border-left: 4px solid #e6a23c">
          <div class="card-content">
            <div class="card-label">📦 预留分配</div>
            <div class="card-value" style="color: #e6a23c">-{{ formatAmount(summary.allocated_total) }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card" style="border-left: 4px solid #67c23a">
          <div class="card-content">
            <div class="card-label">🎯 自由支配</div>
            <div class="card-value" :style="{ color: summary.free_cash < 0 ? '#f56c6c' : '#67c23a' }">
              {{ formatAmount(summary.free_cash) }}
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 分配计划 + 承诺/决策 -->
    <el-row :gutter="16">
      <el-col :span="16">
        <el-card class="allocation-section" shadow="hover">
          <template #header>
            <div class="section-header">
              <span>📋 预留分配计划</span>
              <span class="section-hint">预留金额 = 打算留作某用途的钱，还未实际花费</span>
            </div>
          </template>

          <div
            v-for="item in allocationItems"
            :key="item.category_id"
            class="allocation-row"
          >
            <div class="allocation-info">
              <span class="category-icon">{{ item.category_icon }}</span>
              <span class="category-name">{{ item.category_name }}</span>
            </div>

            <div class="allocation-amounts">
              <el-input-number
                v-model="item.planned_amount"
                :min="0"
                :step="500"
                :precision="2"
                size="small"
                style="width: 140px"
              />
              <span class="amount-detail">
                已花: <span style="color: #f56c6c">{{ formatAmount(item.spent_amount) }}</span>
                │ 剩余: <span :style="{ color: (item.remaining_amount || 0) < 0 ? '#f56c6c' : '#67c23a' }">
                  {{ formatAmount(item.remaining_amount) }}
                </span>
              </span>
            </div>
          </div>

          <div class="allocation-summary">
            <span>预留合计: <strong>{{ formatAmount(totalAllocated) }}</strong></span>
            <span class="remaining">
              剩余可分配: <strong :style="{ color: remainingToAllocate < 0 ? '#f56c6c' : '#67c23a' }">
                {{ formatAmount(remainingToAllocate) }}
              </strong>
            </span>
            <el-button type="primary" size="small" :loading="saving" @click="savePlan">
              保存计划
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <!-- 硬性承诺列表 -->
        <el-card class="commitment-section" shadow="hover">
          <template #header>
            <div class="section-header">
              <span>⏰ 硬性承诺</span>
              <span class="section-hint">未来必须花的钱</span>
            </div>
          </template>

          <div v-if="commitments.length === 0" class="empty-state">暂无硬性承诺</div>
          <div v-for="c in commitments" :key="c.id" class="commitment-item">
            <div class="commitment-info">
              <span class="commitment-name">{{ c.name }}</span>
              <el-tag :type="c.status === 'urgent' ? 'danger' : 'info'" size="small">
                {{ c.status === 'urgent' ? '紧急' : '待付' }}
              </el-tag>
            </div>
            <div class="commitment-meta">
              <span class="commitment-amount">¥{{ formatAmount(c.amount) }}</span>
              <span class="commitment-date">📅 {{ formatDate(c.due_date) }}</span>
              <el-button text size="small" type="danger" @click="removeCommitment(c)">删除</el-button>
            </div>
          </div>
        </el-card>

        <!-- 自由决策 -->
        <el-card class="decision-section" shadow="hover" style="margin-top: 16px">
          <template #header>
            <span>🧠 自由决策记录</span>
          </template>

          <div v-if="decisions.length === 0" class="empty-state">暂无决策记录</div>
          <div v-for="d in decisions" :key="d.id" class="decision-item">
            <div class="decision-left">
              <span class="decision-text">{{ d.content }}</span>
              <span class="decision-category">{{ decisionCategoryLabel(d.category) }}</span>
            </div>
            <span class="decision-date">{{ formatDate(d.created_at) }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 添加承诺对话框 -->
    <el-dialog title="添加硬性承诺" v-model="showCommitmentDialog" width="400px">
      <el-form :model="commitmentForm" label-width="80px">
        <el-form-item label="项目名称">
          <el-input v-model="commitmentForm.name" placeholder="如：保险费" />
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="commitmentForm.amount" :min="0" :step="100" :precision="2" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="commitmentForm.due_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCommitmentDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCommitment">确认添加</el-button>
      </template>
    </el-dialog>

    <!-- 记录决策对话框 -->
    <el-dialog title="记录自由决策" v-model="showDecisionDialog" width="400px">
      <el-form>
        <el-form-item label="决策内容">
          <el-input
            v-model="decisionForm.content"
            type="textarea"
            :rows="3"
            placeholder="如：决定留 ¥8,000 给9月旅行计划"
          />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="decisionForm.category" placeholder="选择类别">
            <el-option v-for="opt in decisionOptions" :key="opt.value" :label="opt.icon + ' ' + opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDecisionDialog = false">取消</el-button>
        <el-button type="primary" @click="saveDecision">确认记录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit } from '@element-plus/icons-vue'
import { formatAmount } from '@/shared/utils/format'
import { getAllocationDetail, createAllocationPlan, saveDecision as apiSaveDecision } from '../api/allocation'

interface PlanItem {
  id: number | null
  category_id: number
  category_name: string
  category_icon: string
  category_color: string
  planned_amount: number
  spent_amount: number
  remaining_amount: number
  note: string
}

interface PlanCommitment {
  id: number | null
  name: string
  amount: number
  due_date: string
  status: string
  source: string
}

interface PlanDecision {
  id: number
  content: string
  category: string
  created_at: string
}

const loading = ref(false)
const saving = ref(false)
const selectedMonth = ref(new Date().toISOString().slice(0, 7))
const showCommitmentDialog = ref(false)
const showDecisionDialog = ref(false)

const planData = ref<any>({
  id: null,
  total_cash: 0,
  commitments_total: 0,
  allocated_total: 0,
  free_cash: 0,
  items: [],
  commitments: [],
  decisions: [],
  available_categories: [],
})

const totalCash = ref(0)

const commitmentForm = reactive({ name: '', amount: 0, due_date: '' })
const decisionForm = reactive({ content: '', category: '' })

const decisionOptions = [
  { value: 'save', label: '存起来', icon: '📈' },
  { value: 'learn', label: '学习/技能', icon: '📚' },
  { value: 'travel', label: '旅行/体验', icon: '✈️' },
  { value: 'home', label: '改善生活', icon: '🏠' },
  { value: 'venture', label: '创业/探索', icon: '🚀' },
]

const allocationItems = computed<PlanItem[]>(() => planData.value.items || [])
const commitments = computed<PlanCommitment[]>(() => planData.value.commitments || [])
const decisions = computed<PlanDecision[]>(() => planData.value.decisions || [])

const totalAllocated = computed(() =>
  allocationItems.value.reduce((sum, item) => sum + (Number(item.planned_amount) || 0), 0),
)

const summary = computed(() => {
  const total = Number(totalCash.value) || 0
  const commit = commitments.value.reduce((sum, c) => sum + (Number(c.amount) || 0), 0)
  const alloc = totalAllocated.value
  return {
    total_cash: total,
    commitments_total: commit,
    allocated_total: alloc,
    free_cash: total - commit - alloc,
  }
})

const remainingToAllocate = computed(() => {
  return summary.value.free_cash - totalAllocated.value
})

async function loadData() {
  loading.value = true
  try {
    const res = await getAllocationDetail({ year_month: selectedMonth.value })
    planData.value = res.data
    totalCash.value = Number(planData.value.total_cash) || 0
  } catch {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

async function savePlan() {
  if (summary.value.free_cash < 0) {
    ElMessage.warning('自由支配为负，请调整手头现金或预留金额')
    return
  }
  saving.value = true
  try {
    const allocations = allocationItems.value.map((item) => ({
      category_id: item.category_id,
      amount: Number(item.planned_amount) || 0,
    }))
    const commitmentList = commitments.value.map((c) => ({
      name: c.name,
      amount: Number(c.amount) || 0,
      due_date: c.due_date,
      source: c.source || 'manual',
    }))

    await createAllocationPlan({
      year_month: selectedMonth.value,
      total_cash: Number(totalCash.value) || 0,
      allocations,
      commitments: commitmentList,
    })
    ElMessage.success('计划已保存')
    await loadData()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function saveCommitment() {
  if (!commitmentForm.name.trim() || commitmentForm.amount <= 0 || !commitmentForm.due_date) {
    ElMessage.warning('请填写完整信息')
    return
  }
  commitments.value.push({
    id: null,
    name: commitmentForm.name.trim(),
    amount: commitmentForm.amount,
    due_date: commitmentForm.due_date,
    status: 'pending',
    source: 'manual',
  })
  showCommitmentDialog.value = false
  commitmentForm.name = ''
  commitmentForm.amount = 0
  commitmentForm.due_date = ''
  ElMessage.success('已添加硬性承诺，保存计划后生效')
}

function removeCommitment(row: PlanCommitment) {
  ElMessageBox.confirm(`确定删除 "${row.name}" 吗？`, '确认删除', { type: 'warning' })
    .then(() => {
      commitments.value = commitments.value.filter((c) => c.id !== row.id)
      ElMessage.success('已删除，保存计划后生效')
    })
    .catch(() => {})
}

function openDecisionDialog() {
  decisionForm.content = ''
  decisionForm.category = ''
  showDecisionDialog.value = true
}

async function saveDecision() {
  if (!decisionForm.content.trim()) {
    ElMessage.warning('请输入决策内容')
    return
  }
  try {
    await apiSaveDecision({
      plan_id: planData.value.id,
      content: decisionForm.content.trim(),
      category: decisionForm.category,
    })
    showDecisionDialog.value = false
    ElMessage.success('决策已记录')
    await loadData()
  } catch {
    ElMessage.error('记录失败')
  }
}

function decisionCategoryLabel(value: string) {
  return decisionOptions.find((o) => o.value === value)?.label || ''
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  return `${d.getMonth() + 1}/${d.getDate()}`
}

onMounted(loadData)
</script>

<style scoped lang="scss">
.allocation-board {
  padding: 16px 0;
}

.board-header {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: center;
}

.summary-cards {
  margin-bottom: 20px;

  .summary-card {
    .card-content {
      .card-label {
        font-size: 14px;
        color: var(--el-text-color-secondary);
        margin-bottom: 6px;
      }

      .card-value {
        font-size: 24px;
        font-weight: 700;
      }

      .card-value-input {
        width: 100%;
      }
    }
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .section-hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

.allocation-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--el-border-color-light);

  .allocation-info {
    display: flex;
    align-items: center;
    gap: 8px;

    .category-icon {
      font-size: 20px;
    }

    .category-name {
      font-weight: 500;
      width: 140px;
    }
  }

  .allocation-amounts {
    display: flex;
    align-items: center;
    gap: 16px;

    .amount-detail {
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }
  }
}

.allocation-summary {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 24px;
  padding: 12px 0;
  border-top: 2px solid var(--el-border-color-light);
  margin-top: 8px;

  .remaining {
    font-size: 14px;
  }
}

.commitment-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--el-border-color-light);

  .commitment-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;

    .commitment-name {
      font-size: 14px;
      font-weight: 500;
    }
  }

  .commitment-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13px;
    color: var(--el-text-color-secondary);

    .commitment-amount {
      font-weight: 600;
      color: #f56c6c;
    }
  }
}

.decision-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-light);

  .decision-left {
    display: flex;
    flex-direction: column;
    gap: 2px;

    .decision-text {
      font-size: 14px;
    }

    .decision-category {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }

  .decision-date {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    white-space: nowrap;
  }
}

.empty-state {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 20px 0;
}
</style>
