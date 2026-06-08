<template>
  <div class="energy-list">
    <!-- 统计横幅 -->
    <div class="energy-banner" v-if="stats">
      <div class="banner-left">
        <span class="banner-icon">⚡</span>
        <span class="banner-text">
          能量清单 · 低门槛快乐小事 · 今日已完成 {{ stats.today.completed_count }}/{{ totalTemplates }}
        </span>
      </div>
      <div class="banner-right">
        <span class="banner-reward">
          💰 今日能量 +{{ stats.today.total_energy }} → 奖励池 +{{ stats.today.total_energy * 2 }}
        </span>
      </div>
    </div>

    <!-- 分类列表 -->
    <div class="category-sections">
      <div v-for="group in categorizedTemplates" :key="group.category" class="category-section">
        <div class="category-header">
          <span class="category-label">{{ group.icon }} {{ group.label }}</span>
          <span class="category-count">
            今日已完成 {{ group.completedCount }}/{{ group.items.length }}
          </span>
        </div>
        <div class="category-items">
          <EnergyItem
            v-for="tpl in group.items"
            :key="tpl.id"
            :template="tpl"
            :completed-ids="completedIds"
            @complete="handleComplete"
          />
        </div>
      </div>
    </div>

    <!-- 自定义按钮 -->
    <div class="custom-action">
      <el-button text @click="emit('custom')">
        <el-icon><Plus /></el-icon> 自定义能量小事
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ENERGY_CATEGORY_CONFIG } from '../../types/sugarTypes'
import type { EnergyStats, EnergyTemplate } from '../../types/sugarTypes'
import EnergyItem from './EnergyItem.vue'

const props = defineProps<{
  templates: EnergyTemplate[]
  completedIds: number[]
  stats: EnergyStats | null
}>()

const emit = defineEmits<{
  (e: 'complete', template: EnergyTemplate): void
  (e: 'custom'): void
}>()

const totalTemplates = computed(() => props.templates.length)

const categorizedTemplates = computed(() => {
  const groups: Record<string, { category: string; label: string; icon: string; items: EnergyTemplate[]; completedCount: number }> = {}

  for (const tpl of props.templates) {
    const cfg = ENERGY_CATEGORY_CONFIG[tpl.category] || { label: tpl.category, icon: '📁' }
    if (!groups[tpl.category]) {
      groups[tpl.category] = { category: tpl.category, label: cfg.label, icon: cfg.icon, items: [], completedCount: 0 }
    }
    groups[tpl.category].items.push(tpl)
    if (props.completedIds.includes(tpl.id)) {
      groups[tpl.category].completedCount++
    }
  }

  return Object.values(groups)
})

function handleComplete(template: EnergyTemplate) {
  emit('complete', template)
}
</script>

<style scoped lang="scss">
.energy-list {
  background: #fff;
  border: 1px solid #E5E7EB;
  border-radius: 16px;
  padding: 20px;
}

.energy-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid #F3F4F6;

  .banner-left {
    display: flex;
    align-items: center;
    gap: 8px;

    .banner-icon { font-size: 20px; }
    .banner-text { font-size: 14px; font-weight: 600; color: #1F2937; }
  }

  .banner-right {
    .banner-reward {
      font-size: 13px;
      color: #059669;
      background: #D1FAE5;
      padding: 4px 12px;
      border-radius: 6px;
      font-weight: 500;
    }
  }
}

.category-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.category-section {
  .category-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    padding: 0 4px;

    .category-label {
      font-size: 14px;
      font-weight: 600;
      color: #374151;
    }

    .category-count {
      font-size: 12px;
      color: #9CA3AF;
    }
  }

  .category-items {
    background: #F9FAFB;
    border-radius: 10px;
    overflow: hidden;
  }
}

.custom-action {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #F3F4F6;
  text-align: center;
}
</style>
