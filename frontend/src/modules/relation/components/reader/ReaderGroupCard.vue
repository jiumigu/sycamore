<template>
  <div class="group-card" :class="{ active: isActive }" @click="$emit('select', group.id)">
    <div class="card-avatar">{{ group.name.charAt(0) }}</div>
    <div class="card-body">
      <div class="card-name">{{ group.name }}</div>
      <div class="card-stats">
        <span class="stat">能量 <b>{{ group.total_energy }}</b></span>
        <span class="stat-divider" />
        <span class="stat">互动 <b>{{ group.interaction_count }}</b></span>
      </div>
    </div>
    <el-button
      size="small"
      link
      type="danger"
      class="delete-btn"
      @click.stop="$emit('delete', group.id)"
    >
      删除
    </el-button>
  </div>
</template>

<script setup lang="ts">
import type { ReaderGroup } from '../../types/readerTypes'

defineProps<{
  group: ReaderGroup
  isActive?: boolean
}>()

defineEmits<{
  select: [id: number]
  delete: [id: number]
}>()
</script>

<style scoped>
.group-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid #E5E7EB;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}
.group-card:hover {
  border-color: #3B82F6;
  box-shadow: 0 2px 8px rgba(59,130,246,0.1);
}
.group-card.active {
  border-color: #3B82F6;
  background: #EFF6FF;
}
.card-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3B82F6, #8B5CF6);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  flex-shrink: 0;
}
.card-body {
  flex: 1;
  min-width: 0;
}
.card-name {
  font-size: 14px;
  font-weight: 600;
  color: #1F2937;
  margin-bottom: 4px;
}
.card-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6B7280;
}
.stat-divider {
  width: 1px;
  height: 12px;
  background: #E5E7EB;
}
.delete-btn {
  flex-shrink: 0;
}
</style>
