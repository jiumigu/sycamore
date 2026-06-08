<template>
  <div class="location-summary" v-if="summary">
    <div class="summary-card highlight">
      <div class="summary-icon">🏆</div>
      <div class="summary-body">
        <div class="summary-label">最佳认识地点</div>
        <div class="summary-value">{{ summary.best_location || '暂无' }}</div>
        <div class="summary-sub">滋养率 {{ summary.best_nourishing_rate }}%</div>
      </div>
    </div>
    <div class="summary-card">
      <div class="summary-icon">📍</div>
      <div class="summary-body">
        <div class="summary-label">覆盖地点</div>
        <div class="summary-value">{{ summary.total_locations }}</div>
        <div class="summary-sub">个不同城市/地点</div>
      </div>
    </div>
    <div class="summary-card">
      <div class="summary-icon">👥</div>
      <div class="summary-body">
        <div class="summary-label">覆盖总人数</div>
        <div class="summary-value">{{ summary.total_people }}</div>
        <div class="summary-sub">人有地点记录</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { LocationStatsSummary } from '../types/relationshipTypes'

defineProps<{
  summary: LocationStatsSummary | null
}>()
</script>

<style scoped lang="scss">
.location-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 18px;

  .summary-card {
    background: #fff;
    border: 1px solid #f0f0f0;
    border-radius: 10px;
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 14px;
    transition: all 0.2s;

    &.highlight {
      border-color: #c4b5fd;
      background: linear-gradient(135deg, #faf5ff 0%, #fff 100%);
    }

    .summary-icon { font-size: 28px; flex-shrink: 0; }

    .summary-body {
      .summary-label { font-size: 12px; color: #9CA3AF; margin-bottom: 2px; }
      .summary-value { font-size: 20px; font-weight: 700; color: #1F2937; }
      .summary-sub { font-size: 12px; color: #6B7280; margin-top: 2px; }
    }
  }
}
</style>
