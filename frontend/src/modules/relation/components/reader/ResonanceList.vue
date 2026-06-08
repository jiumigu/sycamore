<template>
  <div class="resonance-list">
    <div v-for="item in items" :key="item.id" class="resonance-item">
      <div class="resonance-header">
        <span class="resonance-score" :style="{ background: scoreBg(item.energy_score) }">
          +{{ item.energy_score }}
        </span>
        <span class="resonance-reader">{{ item.reader_name }}</span>
        <span class="resonance-type">{{ item.interaction_type_display }}</span>
      </div>
      <div class="resonance-content" v-if="item.content">{{ item.content }}</div>
      <div class="resonance-article" v-if="item.article_title">
        📄 {{ item.article_title }}
      </div>
      <div class="resonance-tags" v-if="item.tags">
        🏷 <span v-for="tag in tags(item.tags)" :key="tag" class="tag">{{ tag }}</span>
      </div>
    </div>
    <div v-if="items.length === 0" class="resonance-empty">暂无高能量互动</div>
  </div>
</template>

<script setup lang="ts">
import type { ReaderInteraction } from '../../types/readerTypes'

defineProps<{
  items: ReaderInteraction[]
}>()

const scoreBg = (score: number) => {
  if (score >= 5) return '#10B981'
  if (score >= 3) return '#34D399'
  return '#6B7280'
}

const tags = (val: string) => val.split(/[,，、]/).map(s => s.trim()).filter(Boolean)
</script>

<style scoped>
.resonance-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.resonance-item {
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  padding: 12px;
  background: #F9FAFB;
}
.resonance-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.resonance-score {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}
.resonance-reader {
  font-weight: 600;
  font-size: 13px;
  color: #1F2937;
}
.resonance-type {
  font-size: 12px;
  color: #6B7280;
}
.resonance-content {
  font-size: 13px;
  color: #374151;
  margin-bottom: 4px;
  line-height: 1.5;
}
.resonance-article {
  font-size: 12px;
  color: #6B7280;
  margin-bottom: 4px;
}
.resonance-tags {
  font-size: 12px;
  color: #6B7280;
}
.tag {
  display: inline-block;
  padding: 0 6px;
  margin: 0 2px;
  background: #E5E7EB;
  border-radius: 4px;
  color: #374151;
  font-size: 11px;
}
.resonance-empty {
  text-align: center;
  padding: 24px;
  color: #9CA3AF;
  font-size: 13px;
}
</style>
