<template>
  <div class="quarterly-cards" v-loading="loading">
    <div class="cards-header">
      <h3>📊 季度决策工作台</h3>
      <el-tag type="info" size="small">从数据到决策</el-tag>
      <div class="quarter-selector">
        <el-select v-model="year" size="small" style="width:100px" @change="fetchData">
          <el-option v-for="y in store.availableYears" :key="y" :label="`${y}年`" :value="y" />
        </el-select>
        <el-radio-group v-model="quarter" size="small" @change="fetchData">
          <el-radio-button :value="1">Q1</el-radio-button>
          <el-radio-button :value="2">Q2</el-radio-button>
          <el-radio-button :value="3">Q3</el-radio-button>
          <el-radio-button :value="4">Q4</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="never" class="insight-card" :class="unmetClass">
          <div class="card-title">{{ unmetTitle }}</div>
          <div class="card-content">{{ unmetText }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="insight-card" :class="declineClass">
          <div class="card-title">{{ declineTitle }}</div>
          <div class="card-content">{{ declineText }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="insight-card" :class="focusClass">
          <div class="card-title">{{ focusTitle }}</div>
          <div class="card-content">{{ focusText }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSummaryStore } from '../stores/summaryStore'

const store = useSummaryStore()

const year = ref(new Date().getFullYear())
const quarter = ref(Math.ceil((new Date().getMonth() + 1) / 3))
const loading = ref(false)

async function fetchData() {
  loading.value = true
  try {
    await store.fetchQuarterlyReport(year.value, quarter.value)
  } finally {
    loading.value = false
  }
}

// 从 insights 中按 type 提取对应卡片
const unmetInsight = computed(() => store.quarterlyInsights.find(i => i.type === 'danger'))
const declineInsight = computed(() => store.quarterlyInsights.find(i => i.type === 'warning'))
const focusInsight = computed(() => store.quarterlyInsights.find(i => i.type === 'info'))

const unmetTitle = computed(() => unmetInsight.value ? `⚠️ ${unmetInsight.value.icon} 未达标` : '✅ 全部达标')
const unmetText = computed(() => unmetInsight.value?.message || '本季度所有目标均按计划推进')
const unmetClass = computed(() => unmetInsight.value ? 'card-danger' : 'card-ok')

const declineTitle = computed(() => declineInsight.value ? '📉 环比下降' : '📈 环比稳定')
const declineText = computed(() => declineInsight.value?.message || '各指标与上季度持平或有提升')
const declineClass = computed(() => declineInsight.value ? 'card-warning' : 'card-ok')

const focusTitle = computed(() => focusInsight.value ? '🎯 最需关注' : '👍 无需特别关注')
const focusText = computed(() => focusInsight.value?.message || '本季度没有特别突出的问题领域')
const focusClass = computed(() => focusInsight.value ? 'card-info' : 'card-ok')

onMounted(fetchData)
</script>

<style scoped>
.quarterly-cards {
  margin-bottom: 18px;
}
.cards-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  h3 { margin: 0; font-size: 16px; font-weight: 600; }
}
.quarter-selector {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.insight-card {
  border: none;
  border-radius: 10px;
  &.card-danger { border-left: 4px solid #EF4444; background: #FEF2F2; }
  &.card-warning { border-left: 4px solid #F59E0B; background: #FFFBEB; }
  &.card-info { border-left: 4px solid #6366F1; background: #EEF2FF; }
  &.card-ok { border-left: 4px solid #10B981; background: #ECFDF5; }
  :deep(.el-card__body) { padding: 14px; }
  .card-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
  .card-content { font-size: 12px; line-height: 1.5; color: #6B7280; }
}
</style>
