<template>
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">当前体重</div>
      <div class="stat-value">{{ stats?.current_weight_jin ?? '--' }} <small>斤</small></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">最终目标</div>
      <div class="stat-value">{{ stats?.target_weight_jin ?? '--' }} <small>斤</small></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">已减总量</div>
      <div class="stat-value" :class="lostClass">{{ stats?.total_lost_jin ?? '--' }} <small>斤</small></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">还需减重</div>
      <div class="stat-value" :class="remainingClass">{{ stats?.remaining_jin ?? '--' }} <small>斤</small></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WeightStats } from '../../types/healthTypes'

const props = defineProps<{ stats: WeightStats | null }>()

const lostClass = computed(() => {
  if (!props.stats?.total_lost_jin || props.stats.total_lost_jin <= 0) return 'text-muted'
  return 'text-green'
})

const remainingClass = computed(() => {
  if (!props.stats?.remaining_jin || props.stats.remaining_jin <= 0) return 'text-green'
  return 'text-orange'
})
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.stat-card {
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}
.stat-label { font-size: 13px; color: #6B7280; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 700; color: #1F2937; }
.stat-value small { font-size: 14px; font-weight: 400; color: #6B7280; }
.text-green { color: #10B981; }
.text-orange { color: #F59E0B; }
.text-muted { color: #6B7280; }
</style>
