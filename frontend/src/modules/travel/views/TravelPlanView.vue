<template>
  <div class="travel-plan">
    <!-- 归档提示 -->
    <el-alert title="此模块已归档，随时可重新启用" type="info" show-icon :closable="false" class="archive-banner" />
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1><span class="header-icon">🧳</span> 旅行计划</h1>
        <p class="header-desc">出发前做好预算，旅行中逐项打卡</p>
      </div>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon> 新建计划
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value">{{ stats?.total_plans ?? 0 }}</div>
          <div class="stat-label">计划总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value text-warning">{{ fmt(stats?.total_estimate) }}</div>
          <div class="stat-label">总预估费用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value text-success">{{ stats?.completed_plans ?? 0 }}</div>
          <div class="stat-label">已完成</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value">{{ plans.length - (stats?.completed_plans ?? 0) }}</div>
          <div class="stat-label">计划中</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 计划列表 -->
    <el-card class="plans-card" shadow="never">
      <template #header>📋 旅行计划列表</template>
      <div v-if="loading" v-loading="true" class="list-loading" />
      <div v-else-if="plans.length === 0" class="empty">
        <el-empty description="还没有旅行计划，点击右上角新建" />
      </div>
      <div v-for="plan in plans" :key="plan.id" class="plan-card">
        <div class="plan-header">
          <div class="plan-info" @click="togglePlan(plan.id)">
            <span class="plan-name">{{ plan.name }}</span>
            <span class="plan-destination">📍 {{ plan.destination }}</span>
            <el-tag :type="getStatusType(plan.status)" size="small">{{ plan.status }}</el-tag>
            <span class="plan-cost">¥{{ fmt(plan.total_estimate) }}</span>
            <span class="plan-date">{{ plan.start_date || '未定日期' }}</span>
            <el-icon class="expand-icon" :class="{ expanded: expandedPlanId === plan.id }"><ArrowDown /></el-icon>
          </div>
          <div class="plan-actions" @click.stop>
            <el-button size="small" @click="viewRoute(plan)">🚂 路线</el-button>
            <el-button size="small" @click="editPlan(plan)">✏️ 编辑</el-button>
            <el-button size="small" @click="copyPlan(plan)">📋 复制</el-button>
            <el-button size="small" type="danger" @click="deletePlan(plan.id)">🗑️ 删除</el-button>
          </div>
        </div>

        <!-- 展开的明细 -->
        <div v-if="expandedPlanId === plan.id" class="plan-items">
          <div v-for="item in plan.items" :key="item.id" class="item-row" :class="{ completed: item.is_completed }">
            <el-checkbox :model-value="item.is_completed" @change="toggleItem(plan, item)" />
            <span class="item-icon">{{ getItemIcon(item.item_type) }}</span>
            <span class="item-name" :class="{ 'text-done': item.is_completed }">{{ item.name }}</span>
            <span class="item-cost">¥{{ fmt(item.estimate_cost) }}</span>
          </div>
          <div v-if="plan.items.length === 0" class="no-items">暂无明细项</div>
        </div>
      </div>
    </el-card>

    <!-- 计划内打卡录入弹窗 -->
    <el-dialog v-model="visitDialogVisible" title="打卡记录" width="460px" :close-on-click-modal="false">
      <div v-if="visitItem" class="visit-item-name">
        {{ getItemIcon(visitItem.item_type) }} {{ visitItem.name }}
        <span v-if="visitPlan" class="visit-plan-name">{{ visitPlan.name }}</span>
      </div>
      <p class="visit-tip">记录后会自动写入「旅行足迹 → 行程日志」，也可跳过只打卡。</p>
      <el-form label-width="90px">
        <el-form-item label="打卡日期">
          <el-date-picker
            v-model="visitForm.visited_at"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="默认今天"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="评分">
          <el-rate v-model="visitForm.visit_rating" :texts="RATE_TEXTS" show-text clearable />
        </el-form-item>
        <el-form-item label="打卡评价">
          <el-input
            v-model="visitForm.visit_notes"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="味道 / 体验 / 值不值得排队的真实感受…"
          />
        </el-form-item>
        <el-form-item label="值得反复">
          <el-switch v-model="visitForm.worth_revisit" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visitDialogVisible = false">取消</el-button>
        <el-button :loading="visitSaving" @click="confirmVisit(false)">只打卡</el-button>
        <el-button type="primary" :loading="visitSaving" @click="confirmVisit(true)">打卡并记录</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="showCreateDialog" :title="editingPlanId ? '编辑旅行计划' : '新建旅行计划'" width="680px" append-to-body>
      <el-form :model="createForm" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="计划名称" required>
              <el-input v-model="createForm.name" placeholder="如：泉州2日游" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目的地" required>
              <el-input v-model="createForm.destination" placeholder="如：泉州" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="出发日期">
          <el-date-picker v-model="createForm.start_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
        </el-form-item>

        <!-- 添加明细项 -->
        <el-divider>计划明细</el-divider>
        <div v-for="(item, index) in createForm.items" :key="index" class="item-edit-row">
          <el-select v-model="item.item_type" size="small" class="item-type-select">
            <el-option v-for="t in TRAVEL_PLAN_ITEM_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <el-input v-model="item.name" size="small" placeholder="名称" class="item-edit-name" />
          <el-input-number v-model="item.estimate_cost" :min="0" :precision="2" size="small" class="item-cost-input" controls-position="right" />
          <span class="cost-suffix">元</span>
          <el-button size="small" type="danger" circle @click="createForm.items.splice(index, 1)">✕</el-button>
        </div>
        <el-button size="small" class="add-item-btn" @click="addItem">
          <el-icon><Plus /></el-icon> 添加明细
        </el-button>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePlan">{{ editingPlanId ? '保存' : '创建计划' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, ArrowDown } from '@element-plus/icons-vue'
import * as api from '../api/travelApi'
import {
  TRAVEL_PLAN_ITEM_TYPES,
  type TravelPlan,
  type TravelPlanItem,
  type TravelPlanItemInput,
  type TravelPlanStats,
} from '../types/travelTypes'

const router = useRouter()
const plans = ref<TravelPlan[]>([])
const stats = ref<TravelPlanStats | null>(null)
const loading = ref(false)
const expandedPlanId = ref<number | null>(null)

const showCreateDialog = ref(false)
const saving = ref(false)
const editingPlanId = ref<number | null>(null)
const createForm = reactive<{
  name: string
  destination: string
  start_date: string | null
  items: TravelPlanItemInput[]
}>({
  name: '',
  destination: '',
  start_date: null,
  items: [],
})

function fmt(n: unknown): string {
  return Number(n ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function getStatusType(status: string): string {
  if (status === '进行中') return 'warning'
  if (status === '已完成') return 'success'
  if (status === '已取消') return 'info'
  return ''
}

function getItemIcon(type: string): string {
  const t = TRAVEL_PLAN_ITEM_TYPES.find((x) => x.value === type)
  return t ? t.label.split(' ')[0] : '📌'
}

function addItem() {
  createForm.items.push({ item_type: 'food', name: '', estimate_cost: 0 })
}

function resetCreateForm() {
  createForm.name = ''
  createForm.destination = ''
  createForm.start_date = null
  createForm.items = []
}

function openCreateDialog() {
  resetCreateForm()
  editingPlanId.value = null
  addItem()
  showCreateDialog.value = true
}

function fillItemInputs(items: TravelPlanItemInput[]) {
  createForm.items = (items || []).map((item) => ({
    item_type: item.item_type,
    name: item.name,
    estimate_cost: item.estimate_cost,
  }))
  if (createForm.items.length === 0) addItem()
}

function editPlan(plan: TravelPlan) {
  editingPlanId.value = plan.id
  createForm.name = plan.name
  createForm.destination = plan.destination
  createForm.start_date = plan.start_date
  fillItemInputs(plan.items)
  showCreateDialog.value = true
}

function copyPlan(plan: TravelPlan) {
  editingPlanId.value = null
  createForm.name = `${plan.name}（副本）`
  createForm.destination = plan.destination
  createForm.start_date = plan.start_date
  fillItemInputs(plan.items)
  showCreateDialog.value = true
}

async function fetchAll() {
  loading.value = true
  try {
    const [planRes, statsRes] = await Promise.all([api.getTravelPlans(), api.getTravelPlanStats()])
    plans.value = planRes.data?.results ?? planRes.data ?? []
    stats.value = statsRes.data
  } catch {
    ElMessage.error('加载旅行计划失败')
  } finally {
    loading.value = false
  }
}

function togglePlan(id: number) {
  expandedPlanId.value = expandedPlanId.value === id ? null : id
}

/** 打开路线推演：优先复用计划生成时记录的完整站点序列 */
function viewRoute(plan: TravelPlan) {
  const matched = /^由路线推演生成：(.+)$/.exec(plan.notes || '')
  let origin = ''
  let dests: string[] = []
  if (matched) {
    const seq = matched[1].split('→').map(s => s.trim()).filter(Boolean)
    origin = seq[0] || ''
    dests = seq.slice(1)
  }
  if (!dests.length) dests = [plan.destination].filter(Boolean)
  if (!dests.length) {
    ElMessage.warning('该计划还没有目的地')
    return
  }
  router.push({ path: '/travel/route', query: { origin, destinations: dests.join(',') } })
}

async function savePlan() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请填写计划名称')
    return
  }
  if (!createForm.destination.trim()) {
    ElMessage.warning('请填写目的地')
    return
  }
  const data = {
    name: createForm.name.trim(),
    destination: createForm.destination.trim(),
    start_date: createForm.start_date,
    items: createForm.items.filter((i) => i.name.trim()),
  }
  saving.value = true
  try {
    if (editingPlanId.value) {
      await api.updateTravelPlan(editingPlanId.value, data)
      ElMessage.success('已更新')
    } else {
      await api.createTravelPlan(data)
      ElMessage.success('已创建')
    }
    showCreateDialog.value = false
    editingPlanId.value = null
    resetCreateForm()
    await fetchAll()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function deletePlan(id: number) {
  try {
    await ElMessageBox.confirm('确定删除这个旅行计划吗？', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await api.deleteTravelPlan(id)
    ElMessage.success('已删除')
    await fetchAll()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function toggleItem(plan: TravelPlan, item: TravelPlanItem) {
  // 未完成 → 完成：有关联心愿时先录入打卡详情（可跳过），保证行程日志字段完整
  if (!item.is_completed && item.wish) {
    openVisitDialog(plan, item)
    return
  }
  await doToggleItem(plan, item)
}

async function doToggleItem(plan: TravelPlan, item: TravelPlanItem) {
  try {
    const res = await api.toggleTravelPlanItem(plan.id, item.id)
    const updated = res.data as TravelPlanItem
    const target = plan.items.find((i) => i.id === updated.id)
    if (target) {
      target.is_completed = updated.is_completed
      target.completed_at = updated.completed_at
    }
  } catch {
    ElMessage.error('操作失败')
  }
}

// ===== 计划内打卡录入 =====
const RATE_TEXTS = ['踩雷', '一般', '还行', '不错', '值得专程去']
const visitDialogVisible = ref(false)
const visitSaving = ref(false)
const visitPlan = ref<TravelPlan | null>(null)
const visitItem = ref<TravelPlanItem | null>(null)
const visitForm = ref({
  visited_at: '',
  visit_rating: 0,
  visit_notes: '',
  worth_revisit: false,
})

function todayStr() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function openVisitDialog(plan: TravelPlan, item: TravelPlanItem) {
  visitPlan.value = plan
  visitItem.value = item
  visitForm.value = {
    visited_at: todayStr(),
    visit_rating: 0,
    visit_notes: '',
    worth_revisit: false,
  }
  visitDialogVisible.value = true
}

async function confirmVisit(withRecord: boolean) {
  const plan = visitPlan.value
  const item = visitItem.value
  if (!plan || !item) return
  visitSaving.value = true
  try {
    if (withRecord && item.wish) {
      await api.recordWishVisit(item.wish, {
        visited_at: visitForm.value.visited_at || todayStr(),
        visit_rating: visitForm.value.visit_rating || null,
        visit_notes: visitForm.value.visit_notes,
        worth_revisit: visitForm.value.worth_revisit,
      })
    }
    await doToggleItem(plan, item)
    visitDialogVisible.value = false
    ElMessage.success(withRecord ? '已打卡并记录' : '已打卡')
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { error?: string } } })?.response?.data?.error
    ElMessage.error(msg || '打卡失败')
  } finally {
    visitSaving.value = false
  }
}

onMounted(fetchAll)
</script>

<style scoped lang="scss">
.travel-plan {
  padding: 24px;
  background: #F5F7FA;
  min-height: 100vh;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;

    .header-left {
      h1 {
        font-size: 22px;
        font-weight: 700;
        color: #1F2937;
        margin: 0 0 6px 0;

        .header-icon { margin-right: 8px; }
      }
      .header-desc {
        font-size: 13px;
        color: #9CA3AF;
        margin: 0;
      }
    }
  }

  .stats-row {
    margin-bottom: 20px;

    .stat-card {
      border: none;
      border-radius: 10px;

      .stat-value {
        font-size: 24px;
        font-weight: 700;
        color: #1F2937;
        text-align: center;
        padding-top: 6px;
      }
      .stat-label {
        font-size: 13px;
        color: #6B7280;
        margin-top: 4px;
        text-align: center;
        padding-bottom: 6px;
      }
      .text-warning { color: #E6A23C; }
      .text-success { color: #67C23A; }
    }
  }

  .plans-card {
    border: none;
    border-radius: 10px;

    .list-loading {
      min-height: 120px;
    }
    .empty {
      padding: 12px 0;
    }

    .plan-card {
      border: 1px solid #f0f0f0;
      border-radius: 8px;
      margin-bottom: 12px;
      overflow: hidden;

      .plan-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        transition: background 0.2s;

        &:hover { background: #f9fafb; }

        .plan-info {
          display: flex;
          align-items: center;
          gap: 12px;
          min-width: 0;
          cursor: pointer;
          flex: 1;

          .plan-name { font-size: 15px; font-weight: 600; color: #1F2937; }
          .plan-destination { font-size: 13px; color: #6B7280; }
          .plan-cost { font-size: 16px; font-weight: 700; color: #E6A23C; }
          .plan-date { font-size: 12px; color: #9CA3AF; }

          .expand-icon {
            color: #9CA3AF;
            transition: transform 0.2s;

            &.expanded { transform: rotate(180deg); }
          }
        }

        .plan-actions {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
        }
      }

      .plan-items {
        border-top: 1px solid #f0f0f0;
        background: #fafbfc;
        padding: 8px 0;

        .item-row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 16px;

          &.completed .item-name { color: #9CA3AF; }
          &.completed .item-cost { color: #C0C4CC; }

          .item-icon { font-size: 15px; }
          .item-name {
            flex: 1;
            font-size: 14px;
            color: #1F2937;

            &.text-done { text-decoration: line-through; }
          }
          .item-cost { font-size: 13px; font-weight: 600; color: #606266; }
        }

        .no-items {
          padding: 16px;
          text-align: center;
          font-size: 13px;
          color: #9CA3AF;
        }
      }
    }
  }
}

/* 明细行在 append-to-body 弹窗内（teleport 到 body），不能依赖 .travel-plan 祖先，需顶层作用域 */
.item-edit-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: nowrap;

  .item-type-select {
    width: 90px;
    flex-shrink: 0;
  }

  .item-edit-name {
    flex: 1;
    min-width: 150px;
  }

  .item-cost-input {
    width: 120px;
    flex-shrink: 0;
  }

  .cost-suffix {
    font-size: 13px;
    color: #666;
    white-space: nowrap;
  }
}

.add-item-btn {
  margin-top: 4px;
}

/* ===== 计划内打卡录入 ===== */
.visit-item-name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 500;
  color: #1F2937;

  .visit-plan-name {
    font-size: 12px;
    font-weight: 400;
    color: #6B7280;
    background: #F3F4F6;
    padding: 2px 8px;
    border-radius: 10px;
  }
}

.visit-tip {
  margin: 6px 0 16px;
  font-size: 12px;
  color: #9CA3AF;
}
</style>
