<template>
  <div class="inbox-stats">
    <div class="stat-card pending">
      <div class="stat-value">{{ store.stats?.pending ?? 0 }}</div>
      <div class="stat-label">📋 待处理</div>
    </div>
    <div class="stat-card done">
      <div class="stat-value">{{ store.stats?.done_this_week ?? 0 }}</div>
      <div class="stat-label">✅ 本周完成</div>
    </div>
    <div class="stat-card overdue">
      <div class="stat-value">{{ store.stats?.overdue ?? 0 }}</div>
      <div class="stat-label">⏰ 逾期</div>
    </div>
    <div class="stat-card total">
      <div class="stat-value">{{ store.stats?.total ?? 0 }}</div>
      <div class="stat-label">📊 总条数</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useInboxStore } from '../stores/inboxStore'

const store = useInboxStore()
</script>

<style scoped>
.inbox-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: #6B7280;
  margin-top: 4px;
}
.pending .stat-value { color: #3B82F6; }
.done .stat-value { color: #10B981; }
.overdue .stat-value { color: #EF4444; }
.total .stat-value { color: #6B7280; }
</style>
