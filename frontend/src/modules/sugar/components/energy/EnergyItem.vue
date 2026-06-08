<template>
  <div
    class="energy-item"
    :class="{ completed: isCompleted }"
    @click="handleToggle"
  >
    <div class="item-checkbox">
      <span v-if="isCompleted" class="checked">☑️</span>
      <span v-else class="unchecked">⬜</span>
    </div>
    <div class="item-icon">{{ template.icon }}</div>
    <div class="item-content">{{ template.content }}</div>
    <div class="item-energy">+{{ template.default_energy }}</div>
    <div class="item-time">{{ formatTime(template.estimated_seconds) }}</div>
    <div v-if="isCompleted" class="item-done">✓</div>
  </div>
</template>

<script setup lang="ts">
import type { EnergyTemplate } from '../../types/sugarTypes'

const props = defineProps<{
  template: EnergyTemplate
  completedIds: number[]
}>()

const emit = defineEmits<{
  (e: 'complete', template: EnergyTemplate): void
}>()

const isCompleted = computed(() => props.completedIds.includes(props.template.id))

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`
  return `${(seconds / 3600).toFixed(1)}小时`
}

function handleToggle() {
  if (!isCompleted.value) {
    emit('complete', props.template)
  }
}

import { computed } from 'vue'
</script>

<style scoped lang="scss">
.energy-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;

  &:hover:not(.completed) {
    background: #FAF5FF;
    border-color: #E9D5FF;
  }

  &.completed {
    opacity: 0.55;
    background: #F9FAFB;
    cursor: default;

    .item-content { text-decoration: line-through; color: #9CA3AF; }
  }

  .item-checkbox {
    font-size: 18px;
    flex-shrink: 0;
    line-height: 1;
  }

  .item-icon { font-size: 18px; flex-shrink: 0; }

  .item-content {
    flex: 1;
    font-size: 14px;
    color: #1F2937;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-energy {
    font-size: 13px;
    font-weight: 600;
    color: #10B981;
    white-space: nowrap;
  }

  .item-time {
    font-size: 12px;
    color: #9CA3AF;
    white-space: nowrap;
    min-width: 40px;
    text-align: right;
  }

  .item-done {
    color: #10B981;
    font-weight: 700;
    font-size: 14px;
  }
}
</style>
