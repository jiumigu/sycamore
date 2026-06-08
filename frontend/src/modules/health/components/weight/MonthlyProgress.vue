<template>
  <div class="progress-section">
    <div class="section-title">📅 月度进度追踪</div>

    <div class="progress-overview" v-if="stats">
      <div class="overview-item">
        <span class="overview-label">整体进度</span>
        <span class="overview-value">{{ stats.overall_progress }}%</span>
      </div>
      <div class="overview-item">
        <span class="overview-label">本月目标</span>
        <span class="overview-value">{{ monthlyTargetJin }} 斤</span>
      </div>
      <div class="overview-item">
        <span class="overview-label">本月已减</span>
        <span class="overview-value" :class="monthlyClass">{{ monthlyLostJin }} 斤</span>
      </div>
      <div class="overview-item">
        <span class="overview-label">剩余天数</span>
        <span class="overview-value">{{ stats.remaining_days }} 天</span>
      </div>
    </div>

    <!-- 环形进度 + 月度进度条 -->
    <div class="progress-body" v-if="milestones && milestones.length > 0">
      <div class="ring-wrapper">
        <svg viewBox="0 0 120 120" class="progress-ring">
          <circle cx="60" cy="60" r="52" fill="none" stroke="#F3F4F6" stroke-width="8" />
          <circle
            cx="60" cy="60" r="52" fill="none" stroke="#10B981" stroke-width="8"
            :stroke-dasharray="circumference"
            :stroke-dashoffset="ringOffset"
            stroke-linecap="round"
            transform="rotate(-90, 60, 60)"
          />
          <text x="60" y="52" text-anchor="middle" class="ring-label">整体</text>
          <text x="60" y="72" text-anchor="middle" class="ring-value">{{ stats?.overall_progress ?? 0 }}%</text>
        </svg>
      </div>

      <div class="milestones-list">
        <div
          v-for="m in milestones" :key="m.month_number"
          class="milestone-row"
          :class="{ achieved: m.is_achieved, active: !m.is_achieved && m.month_number === currentMonth }"
        >
          <div class="milestone-month">
            <span class="month-badge" :class="badgeClass(m)">第{{ m.month_number }}月</span>
          </div>
          <div class="milestone-info">
            <span>{{ displayWeight(m.start_weight_kg) }}斤 → {{ displayWeight(m.target_weight_kg) }}斤</span>
            <span class="milestone-target">目标-{{ formatDiff(m.start_weight_kg, m.target_weight_kg) }}斤</span>
          </div>
          <div class="milestone-status">
            <span v-if="m.is_achieved" class="tag-done">✅ 已完成</span>
            <span v-else-if="m.month_number === currentMonth" class="tag-doing">🔄 进行中</span>
            <span v-else class="tag-pending">⏳ 未开始</span>
          </div>
        </div>
      </div>
    </div>
    <el-empty v-else-if="!loading" description="还没有设定减重目标" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WeightMilestone, WeightStats } from '../../types/healthTypes'

const props = defineProps<{
  stats: WeightStats | null
  milestones: WeightMilestone[]
  currentMonth: number
  loading?: boolean
}>()

const circumference = 2 * Math.PI * 52
const ringOffset = computed(() => {
  const pct = (props.stats?.overall_progress ?? 0) / 100
  return circumference * (1 - pct)
})

const monthlyTargetJin = computed(() => {
  const v = props.stats?.monthly_target_jin
  return v != null ? v.toFixed(1) : '--'
})

const monthlyLostJin = computed(() => {
  const v = props.stats?.monthly_lost_jin
  if (v == null) return '--'
  return v.toFixed(1)
})

const monthlyClass = computed(() => {
  const lost = props.stats?.monthly_lost_jin
  if (lost == null) return ''
  return lost > 0 ? 'text-green' : 'text-orange'
})

const badgeClass = (m: WeightMilestone) => {
  if (m.is_achieved) return 'badge-done'
  if (m.month_number === props.currentMonth) return 'badge-active'
  return 'badge-pending'
}

const displayWeight = (val: string | null) => {
  if (!val) return '--'
  return (parseFloat(val) * 2).toFixed(1)
}

const formatDiff = (start: string | null, end: string | null) => {
  if (!start || !end) return '--'
  return ((parseFloat(start) - parseFloat(end)) * 2).toFixed(1)
}
</script>

<style scoped>
.progress-section { background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 20px; }
.section-title { font-size: 16px; font-weight: 600; color: #1F2937; margin-bottom: 16px; }
.progress-overview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.overview-item { text-align: center; padding: 8px; }
.overview-label { display: block; font-size: 12px; color: #6B7280; margin-bottom: 4px; }
.overview-value { font-size: 20px; font-weight: 700; color: #1F2937; }
.progress-body { display: flex; gap: 24px; align-items: flex-start; }
.ring-wrapper { flex-shrink: 0; width: 120px; }
.progress-ring { width: 120px; height: 120px; }
.ring-label { font-size: 10px; fill: #6B7280; }
.ring-value { font-size: 16px; font-weight: 700; fill: #1F2937; }
.milestones-list { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.milestone-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 8px; background: #F9FAFB; }
.milestone-row.active { background: #F0FDF4; border: 1px solid #BBF7D0; }
.milestone-row.achieved { opacity: 0.7; }
.milestone-month { flex-shrink: 0; }
.month-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge-done { background: #D1FAE5; color: #059669; }
.badge-active { background: #DBEAFE; color: #2563EB; }
.badge-pending { background: #F3F4F6; color: #9CA3AF; }
.milestone-info { flex: 1; font-size: 13px; color: #374151; }
.milestone-target { display: block; font-size: 11px; color: #6B7280; }
.milestone-status { flex-shrink: 0; font-size: 12px; }
.tag-done { color: #059669; }
.tag-doing { color: #2563EB; }
.tag-pending { color: #9CA3AF; }
.text-green { color: #10B981; }
.text-orange { color: #F59E0B; }
</style>
