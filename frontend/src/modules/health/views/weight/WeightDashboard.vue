<template>
  <div class="weight-dashboard">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">⚖️ 体重管理</h1>
        <p class="page-subtitle">每月减{{ goal?.monthly_target_jin ?? 3 }}斤，持续跟进</p>
      </div>
      <div class="header-actions">
        <el-button v-if="!goal" type="primary" @click="showGoalModal = true">
          🎯 设定目标
        </el-button>
        <template v-else>
          <el-tag v-if="goal.status === 'completed'" type="success" size="large" effect="dark" class="goal-status-tag">✅ 目标已完成</el-tag>
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

      <!-- 进度 + BMI -->
      <el-row :gutter="16" class="section-row">
        <el-col :span="store.stats?.bmi ? 16 : 24">
          <MonthlyProgress
            :stats="store.stats"
            :milestones="store.milestones"
            :current-month="store.goal?.current_month ?? 1"
            :loading="store.loading"
          />
        </el-col>
        <el-col :span="8" v-if="store.stats?.bmi">
          <BMIStatus :stats="store.stats" />
        </el-col>
      </el-row>

      <!-- 趋势图 -->
      <WeightTrendChart :trend="store.trend" :stats="store.stats" :loading="store.loading" />

      <!-- 今日记录 + 历史记录 -->
      <el-row :gutter="16" class="section-row">
        <el-col :span="24">
          <WeightRecordList
            :records="store.records"
            :show-all="showAllRecords"
            @toggle-show="showAllRecords = !showAllRecords"
            @edit="handleEditRecord"
            @delete="handleDeleteRecord"
          />
        </el-col>
      </el-row>
    </template>

    <!-- 添加/编辑记录弹窗 -->
    <WeightForm
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
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useWeightStore } from '../../stores/healthStore'
import type { WeightRecord } from '../../types/healthTypes'
import WeightStatsCards from '../../components/weight/WeightStatsCards.vue'
import BMIStatus from '../../components/weight/BMIStatus.vue'
import MonthlyProgress from '../../components/weight/MonthlyProgress.vue'
import WeightTrendChart from '../../components/weight/WeightTrendChart.vue'
import WeightRecordList from '../../components/weight/WeightRecordList.vue'
import WeightForm from '../../components/weight/WeightForm.vue'
import GoalSettingModal from '../../components/weight/GoalSettingModal.vue'

const store = useWeightStore()
const goal = computed(() => store.goal)

const showForm = ref(false)
const showGoalModal = ref(false)
const showAllRecords = ref(false)
const editingRecord = ref<WeightRecord | null>(null)
const submitting = ref(false)
const formRef = ref<{ loadRecord: (r: WeightRecord | null) => void }>()

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
    store.fetchStats()
    store.fetchTrend()
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
    store.fetchStats()
    store.fetchTrend()
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
    await store.loadAll()
  } catch {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  store.loadAll()
})
</script>

<style scoped>
.weight-dashboard { max-width: 1000px; margin: 0 auto; padding: 24px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.header-left { }
.page-title { margin: 0; font-size: 24px; font-weight: 700; color: #1F2937; }
.page-subtitle { margin: 4px 0 0; font-size: 14px; color: #6B7280; }
.header-actions { display: flex; gap: 8px; }
.loading-state { padding: 40px; }
.section-row { margin-top: 16px !important; }
</style>
