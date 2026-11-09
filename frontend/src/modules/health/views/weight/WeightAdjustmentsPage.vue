<template>
  <div class="weight-sub-page">
    <WeightSubHeader title="📝 目标调整记录" :subtitle="subtitle">
      <el-button size="small" :loading="loading" @click="reload">刷新</el-button>
    </WeightSubHeader>

    <div v-if="loading && !loaded" class="loading-state">
      <el-skeleton :rows="5" animated />
    </div>
    <template v-else>
      <!-- 当前目标：先给个「现在站在哪」，再看历史怎么一步步走到这儿的 -->
      <div class="goal-card" v-if="store.goal">
        <div class="goal-row">
          <div class="goal-item">
            <span class="goal-label">起始</span>
            <span class="goal-value">{{ store.goal.start_weight_jin }} 斤</span>
          </div>
          <span class="goal-arrow">→</span>
          <div class="goal-item">
            <span class="goal-label">目标</span>
            <span class="goal-value">{{ store.goal.target_weight_jin }} 斤</span>
          </div>
          <div class="goal-item goal-right">
            <span class="goal-label">每月</span>
            <span class="goal-value">-{{ store.goal.monthly_target_jin }} 斤</span>
          </div>
        </div>
        <div class="goal-meta">开始于 {{ store.goal.start_date }} · 当前第 {{ store.goal.current_month }} 个月</div>
      </div>

      <div class="adjust-card">
        <el-empty
          v-if="store.adjustments.length === 0"
          description="还没有调整过目标"
          :image-size="80"
        />
        <el-timeline v-else>
          <el-timeline-item
            v-for="adj in store.adjustments"
            :key="adj.id"
            :timestamp="adj.adjusted_at"
            placement="top"
            :color="Number(adj.change_amount) > 0 ? '#f56c6c' : '#67c23a'"
          >
            <div class="adj-line">
              <span>{{ adj.before_value }}斤 → {{ adj.after_value }}斤</span>
              <el-tag :type="Number(adj.change_amount) > 0 ? 'danger' : 'success'" size="small">
                {{ Number(adj.change_amount) > 0 ? '+' : '' }}{{ adj.change_amount }}斤
              </el-tag>
            </div>
            <div v-if="adj.reason" class="adj-reason">{{ adj.reason }}</div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useWeightStore } from '../../stores/healthStore'
import WeightSubHeader from '../../components/weight/WeightSubHeader.vue'

const store = useWeightStore()
const loading = ref(false)
const loaded = ref(false)

const subtitle = computed(() => {
  const n = store.adjustments.length
  return n === 0 ? '当前目标还没有被调整过' : `当前目标累计调整 ${n} 次`
})

async function reload() {
  loading.value = true
  try {
    await Promise.all([
      store.fetchGoal(),
      store.fetchAdjustments(),
    ])
    loaded.value = true
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.weight-sub-page { max-width: 1000px; margin: 0 auto; padding: 24px; }
.loading-state { padding: 24px; background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; }
.goal-card {
  background: #fff; border: 1px solid #E5E7EB; border-radius: 12px;
  padding: 18px 20px; margin-bottom: 16px;
}
.goal-row { display: flex; align-items: center; gap: 16px; }
.goal-item { display: flex; flex-direction: column; gap: 4px; }
.goal-right { margin-left: auto; }
.goal-label { font-size: 12px; color: #6B7280; }
.goal-value { font-size: 18px; font-weight: 700; color: #1F2937; }
.goal-arrow { color: #9CA3AF; font-size: 16px; }
.goal-meta { margin-top: 12px; font-size: 12px; color: #9CA3AF; }
.adjust-card {
  background: #fff; border: 1px solid #E5E7EB; border-radius: 12px;
  padding: 20px;
}
.adjust-card :deep(.el-timeline) { padding-left: 0; margin-bottom: 0; }
.adj-line { display: flex; align-items: center; gap: 8px; font-size: 14px; color: #1F2937; }
.adj-reason { font-size: 12px; color: #9CA3AF; margin-top: 6px; }
</style>
