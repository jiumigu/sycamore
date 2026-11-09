<template>
  <div class="weight-dashboard">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">⚖️ 体重管理</h1>
        <p class="page-subtitle">每月减{{ goal?.monthly_target_jin ?? 3 }}斤，持续跟进</p>
      </div>
      <div class="header-actions">
        <!-- v3.63.12：本页不再占菜单项，入口在健康管理页头 ⇒ 必须有回程。
             写死 `health`，不用 `router.back()`（刷新/直达/分享链接时没有上一页）。 -->
        <el-button size="default" @click="$router.push('/health/dashboard')">
          <el-icon><ArrowLeft /></el-icon> 健康管理
        </el-button>
        <el-button v-if="!goal" type="primary" @click="showGoalModal = true">
          🎯 设定目标
        </el-button>
        <template v-else>
          <el-tag v-if="goal.status === 'completed'" type="success" size="large" effect="dark" class="goal-status-tag">✅ 目标已完成</el-tag>
          <!-- 三块「不怎么变动」的内容已迁到独立子页面，入口紧挨「调整目标」 -->
          <el-button size="small" class="nav-btn" @click="goSub('health-weight-monthly')">📅 月度进度</el-button>
          <el-button size="small" class="nav-btn" @click="goSub('health-weight-bmi')">⚖️ BMI</el-button>
          <el-button size="small" class="nav-btn" @click="goSub('health-weight-adjustments')">📝 调整记录</el-button>
          <el-button @click="showGoalModal = true">🎯 调整目标</el-button>
        </template>
        <el-button type="success" @click="openAddRecord">
          <el-icon><Plus /></el-icon> 记录体重
        </el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="store.loading && store.records.length === 0" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>

    <template v-else>
      <!-- 统计卡片 -->
      <WeightStatsCards :stats="store.stats" />

      <!-- 趋势图 -->
      <WeightTrendChart :trend="store.trend" :stats="store.stats" :loading="store.loading" />

      <!-- 历史记录（后端分页，默认 20 条/页）
           ⚠️ 这里**不再有**「月度进度追踪 / BMI / 目标调整记录」——
              三块变动很少，已迁到 `/health/weight/{monthly,bmi,adjustments}` 三个子页面。 -->
      <el-row :gutter="16" class="section-row">
        <el-col :span="24">
          <WeightRecordList
            :records="store.records"
            :total="store.recordsTotal"
            :page="currentPage"
            :page-size="pageSize"
            :page-sizes="PAGE_SIZE_OPTIONS"
            :loading="store.loading"
            @page-change="handlePageChange"
            @size-change="handleSizeChange"
            @edit="handleEditRecord"
            @delete="handleDeleteRecord"
          />
        </el-col>
      </el-row>
    </template>

    <!-- 添加/编辑记录弹窗 -->
    <!-- 🔴 ref 不能省：编辑态的回填靠 formRef.loadRecord()，漏绑 ⇒ undefined?.() 静默不回填 -->
    <WeightForm
      ref="formRef"
      v-model="showForm"
      :record="editingRecord"
      :submitting="submitting"
      @submit="handleFormSubmit"
    />

    <!-- 设定目标弹窗 -->
    <GoalSettingModal
      v-model="showGoalModal"
      :submitting="submitting"
      @submit="handleGoalSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, ArrowLeft } from '@element-plus/icons-vue'
import { useWeightStore } from '../../stores/healthStore'
import type { WeightRecord } from '../../types/healthTypes'
import WeightStatsCards from '../../components/weight/WeightStatsCards.vue'
import WeightTrendChart from '../../components/weight/WeightTrendChart.vue'
import WeightRecordList from '../../components/weight/WeightRecordList.vue'
import WeightForm from '../../components/weight/WeightForm.vue'
import GoalSettingModal from '../../components/weight/GoalSettingModal.vue'

const store = useWeightStore()
const router = useRouter()
const goal = computed(() => store.goal)

const showForm = ref(false)
const showGoalModal = ref(false)
const editingRecord = ref<WeightRecord | null>(null)
const submitting = ref(false)
const formRef = ref<{ loadRecord: (r: WeightRecord | null) => void }>()

// ─── 历史记录分页（默认 20 条/页）───
const currentPage = ref(1)
const PAGE_SIZE_OPTIONS = [10, 20, 30, 50]
const pageSize = ref(20)

/**
 * 🔴 `page` 与 `page_size` **必须显式发给后端**：
 * 接口走 DRF 全局 `StandardPagination`（默认 `page_size = 10`），只取默认值的话
 * 「总数 57、页面上只有 10 条」，而分页条按 57 渲染 —— 点第 2 页就错位。
 */
function recordParams(): Record<string, unknown> {
  return { page: currentPage.value, page_size: pageSize.value }
}

async function loadRecords() {
  await store.fetchRecords(recordParams())
}

/** 删掉一条后若本页已空，退到新的最后一页（留在原页 = 空表，页码却还在） */
function clampPage(total: number) {
  const lastPage = Math.max(1, Math.ceil(Math.max(0, total) / pageSize.value))
  if (currentPage.value > lastPage) currentPage.value = lastPage
}

function goSub(name: string) {
  router.push({ name })
}

function openAddRecord() {
  editingRecord.value = null
  showForm.value = true
  // Reset form on next tick
  setTimeout(() => formRef.value?.loadRecord(null), 0)
}

function handleEditRecord(record: WeightRecord) {
  editingRecord.value = record
  showForm.value = true
  setTimeout(() => formRef.value?.loadRecord(record), 0)
}

async function handleDeleteRecord(id: number) {
  try {
    await store.deleteRecord(id)
    ElMessage.success('已删除')
    // 删除前 `recordsTotal` 还是旧数：减 1 才是删完的总数
    clampPage(store.recordsTotal - 1)
    await Promise.all([loadRecords(), store.fetchStats(), store.fetchTrend()])
  } catch {
    ElMessage.error('删除失败')
  }
}

async function handleFormSubmit(data: Record<string, unknown>) {
  submitting.value = true
  try {
    if (editingRecord.value) {
      await store.updateRecord(editingRecord.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await store.createRecord(data)
      ElMessage.success('记录成功')
    }
    showForm.value = false
    // 增改都**不回第 1 页**（§93）：改动只影响当前页内容，不改变「我在看第几页」。
    // 新增的记录按 `-record_date` 排在第 1 页顶部 —— 人在第 1 页时会立刻看到，
    // 人在后页时由 toast + 统计卡变化告知，不把人拽走。
    await Promise.all([loadRecords(), store.fetchStats(), store.fetchTrend()])
  } catch {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleGoalSubmit(data: Record<string, unknown>) {
  submitting.value = true
  try {
    // Create goal first, then save body info
    await store.createGoal({
      start_weight_kg: data.start_weight_kg,
      target_weight_kg: data.target_weight_kg,
      monthly_target_kg: data.monthly_target_kg,
    })
    // Save body info if provided
    if (data.height_cm) {
      await store.updateBodyInfo({
        height_cm: data.height_cm,
        gender: data.gender || undefined,
        age: data.age || undefined,
      })
    }
    showGoalModal.value = false
    ElMessage.success('目标设定成功！加油！💪')
    await store.loadAll(recordParams())
  } catch {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

async function handlePageChange(page: number) {
  // 改页码必须**重新取数**：分页时前端只有当前页那 20 条，光改数字 = 表里还是旧内容
  const lastPage = Math.max(1, Math.ceil(store.recordsTotal / pageSize.value))
  currentPage.value = Math.min(page, lastPage)
  await loadRecords()
}

async function handleSizeChange() {
  // 每页条数变了 ⇒「第几页」不再指向同一批数据 ⇒ 回第 1 页重取
  currentPage.value = 1
  await loadRecords()
}

onMounted(() => {
  store.loadAll(recordParams())
})
</script>

<style scoped>
.weight-dashboard { max-width: 1000px; margin: 0 auto; padding: 24px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.header-left { }
.page-title { margin: 0; font-size: 24px; font-weight: 700; color: #1F2937; }
.page-subtitle { margin: 4px 0 0; font-size: 14px; color: #6B7280; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.nav-btn { color: #4B5563; }
.loading-state { padding: 40px; }
.section-row { margin: 16px 0 !important; display: flex; overflow: visible; }
.section-row :deep(.el-col) { display: flex; overflow: visible; }
.section-row .el-col > * { width: 100%; overflow: visible; }
</style>
