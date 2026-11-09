<template>
  <div class="weight-sub-page">
    <WeightSubHeader title="📅 月度进度追踪" :subtitle="subtitle">
      <el-button size="small" :loading="loading" @click="reload">刷新</el-button>
    </WeightSubHeader>

    <div v-if="loading && !store.stats" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>
    <MonthlyProgress
      v-else
      page-mode
      :stats="store.stats"
      :milestones="store.milestones"
      :current-month="store.goal?.current_month ?? 1"
      :loading="loading"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useWeightStore } from '../../stores/healthStore'
import MonthlyProgress from '../../components/weight/MonthlyProgress.vue'
import WeightSubHeader from '../../components/weight/WeightSubHeader.vue'

const store = useWeightStore()
const loading = ref(false)

const subtitle = computed(() => {
  const monthly = store.goal?.monthly_target_jin
  const phases = store.milestones.length
  if (monthly == null && phases === 0) return '还没有设定减重目标'
  const parts: string[] = []
  if (monthly != null) parts.push(`每月减 ${monthly} 斤`)
  if (phases > 0) parts.push(`共 ${phases} 个阶段`)
  return parts.join(' · ')
})

/**
 * 子页面可以被人**直接打开**（收藏 / 刷新 / 从侧边栏切回）——
 * 那时 store 还是空的，不能指望首页已经把它取好。
 */
async function reload() {
  loading.value = true
  try {
    await Promise.all([
      store.fetchStats(),
      store.fetchGoal(),
      store.fetchMilestones(),
    ])
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.weight-sub-page { max-width: 1000px; margin: 0 auto; padding: 24px; }
.loading-state { padding: 24px; background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; }
</style>
