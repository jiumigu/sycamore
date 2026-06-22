<template>
  <div class="sugar-card" :class="{ expanded }">
    <div class="card-main" @click="expanded = !expanded">
      <div class="card-left">
        <div class="emoji-badge" :style="{ background: happinessColor + '20', color: happinessColor }">
          {{ happinessEmoji }}
        </div>
      </div>
      <div class="card-body">
        <div class="card-top">
          <span class="card-time">{{ formatDate(record.time) }}</span>
          <span v-if="record.category_display" class="card-category">{{ record.category_display }}</span>
          <span class="card-reward">+¥{{ formatMoney(record.reward_amount) }}</span>
        </div>
        <h3 class="card-title">{{ record.title }}</h3>
        <div class="card-happiness" v-if="record.level_of_happiness">
          <el-progress
            :percentage="(record.level_of_happiness / 10) * 100"
            :stroke-width="8"
            :color="happinessColor"
            :show-text="false"
          />
          <span class="happiness-text" :style="{ color: happinessColor }">
            {{ happinessEmoji }} {{ record.level_of_happiness }} {{ record.reward_label }}
          </span>
        </div>
        <div v-if="record.joy_type" class="card-joy-type">
          <span class="joy-type-tag">{{ record.joy_type }}</span>
        </div>
        <div v-if="record.tags" class="card-tags">
          <span v-for="tag in parsedTags" :key="tag" class="tag">{{ tag }}</span>
        </div>
        <div v-if="expanded && record.notes" class="card-notes">
          <p>{{ record.notes }}</p>
        </div>
      </div>
      <div class="card-actions">
        <el-button text size="small" @click.stop="$emit('edit', record)">
          <el-icon><Edit /></el-icon>
        </el-button>
        <el-button text size="small" type="danger" @click.stop="$emit('delete', record)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Edit, Delete } from '@element-plus/icons-vue'
import type { SugarRecord } from '../types/sugarTypes'
import { REWARD_LABELS } from '../types/sugarTypes'

const props = defineProps<{ record: SugarRecord }>()
const emit = defineEmits<{ edit: [r: SugarRecord]; delete: [r: SugarRecord] }>()

const expanded = ref(false)

const happinessColor = computed(() => {
  const v = props.record.level_of_happiness
  if (v <= 3) return '#9CA3AF'
  if (v <= 5) return '#60A5FA'
  if (v <= 7) return '#34D399'
  if (v <= 8.5) return '#FBBF24'
  return '#F97316'
})

const happinessEmoji = computed(() => {
  const v = props.record.level_of_happiness
  if (v <= 3) return '😊'
  if (v <= 5) return '🙂'
  if (v <= 7) return '😄'
  if (v <= 8.5) return '🥰'
  return '🤩'
})

const parsedTags = computed(() => {
  if (!props.record.tags) return []
  return props.record.tags.split(',').map(t => t.trim()).filter(Boolean)
})

function formatDate(d: string) {
  if (!d) return ''
  return d.slice(0, 10)
}

function formatMoney(v: number | string | null | undefined): string {
  if (v === null || v === undefined) return '0.00'
  const n = typeof v === 'string' ? parseFloat(v) : v
  return isNaN(n) ? '0.00' : n.toFixed(2)
}
</script>

<style scoped lang="scss">
.sugar-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #E5E7EB;
  transition: all 0.2s;
  overflow: hidden;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    border-color: #d1d5db;
  }

  &.expanded {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  }

  .card-main {
    display: flex;
    gap: 16px;
    padding: 20px;
    cursor: pointer;
    align-items: flex-start;
  }

  .card-left {
    flex-shrink: 0;

    .emoji-badge {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
    }
  }

  .card-body {
    flex: 1;
    min-width: 0;

    .card-top {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;

      .card-time {
        font-size: 12px;
        color: #9CA3AF;
      }

      .card-category {
        font-size: 11px;
        padding: 1px 8px;
        background: #F3F4F6;
        border-radius: 4px;
        color: #6B7280;
      }

      .card-reward {
        margin-left: auto;
        font-size: 13px;
        font-weight: 600;
        color: #10B981;
        white-space: nowrap;
      }
    }

    .card-title {
      margin: 0 0 8px;
      font-size: 15px;
      font-weight: 600;
      color: #1F2937;
      line-height: 1.4;
    }

    .card-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;

      .happiness-bar {
        flex: 1;
        height: 6px;
        background: #F3F4F6;
        border-radius: 3px;
        overflow: hidden;
        max-width: 120px;

        .bar-fill {
          height: 100%;
          border-radius: 3px;
          transition: width 0.3s;
        }
      }

      .happiness-text {
        font-size: 12px;
        font-weight: 600;
        white-space: nowrap;
      }
    }

    .card-joy-type {
      margin-bottom: 6px;
      .joy-type-tag {
        font-size: 11px;
        padding: 2px 8px;
        background: #FEF3C7;
        border-radius: 4px;
        color: #D97706;
        font-weight: 500;
      }
    }

    .card-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;

      .tag {
        font-size: 11px;
        padding: 2px 8px;
        background: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 4px;
        color: #6B7280;
      }
    }

    .card-notes {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px dashed #E5E7EB;

      p {
        margin: 0;
        font-size: 13px;
        color: #6B7280;
        line-height: 1.6;
        white-space: pre-wrap;
      }
    }
  }

  .card-actions {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.2s;
  }

  &:hover .card-actions {
    opacity: 1;
  }
}
</style>
