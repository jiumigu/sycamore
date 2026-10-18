<template>
  <div class="sugar-card">
    <div class="card-main">
      <div class="card-body">
        <div class="card-top">
          <span class="card-time">{{ formatDate(record.time) }}</span>
          <!--
            档位词与分数一起放在**日期右侧的空白位**。
            颜色取后端下发的 `reward_color` —— 前端不按分数自己算（那是第二份档位边界）。
          -->
          <span v-if="scoreText" class="card-score" :style="{ color: scoreColor }">{{ scoreText }}</span>
          <span v-if="record.category_display" class="card-category">{{ record.category_display }}</span>
          <span class="card-reward">+¥{{ formatAmount(record.reward_amount) }}</span>
        </div>

        <h3 class="card-title">{{ record.title }}</h3>

        <!--
          备注**一直显示**，不再藏在「点一下卡片」后面。
          实测填充率只有 28%（18/64）—— 而「填了也看不见」正是它填不进去的原因。
          取不到就整段不渲染（自由文本的空只有一种含义，不留占位符）。
        -->
        <p v-if="record.notes" class="card-notes">{{ record.notes }}</p>

        <div v-if="record.joy_type || parsedTags.length" class="sugar-meta">
          <el-tag v-if="record.joy_type" size="small" class="joy-tag">{{ record.joy_type }}</el-tag>
          <el-tag
            v-for="tag in parsedTags"
            :key="tag"
            size="small"
            type="info"
          >
            {{ tag }}
          </el-tag>
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
import { computed } from 'vue'
import { Edit, Delete } from '@element-plus/icons-vue'
import type { SugarRecord } from '../types/sugarTypes'
import { formatAmount } from '@/shared/utils/format'

const props = defineProps<{ record: SugarRecord }>()
const emit = defineEmits<{ edit: [r: SugarRecord]; delete: [r: SugarRecord] }>()
void emit

// ⚠️ 这里**没有**档位边界数字，也**没有**表情：
// 卡片上曾经有两处一样的表情（左侧徽章 + 分数旁）与一条 `level/20` 的进度条。
// 进度条与分数是同一个数的两种画法，而分数本身信息量更全（还带档位词）——
// 实测 70% 的记录落在 4 个分数上、53% 的条长挤在 35%~40% 这 5% 区间里，
// 一眼扫过去过半的条一模一样长。所以整块去掉。
const scoreText = computed(() => {
  const level = props.record.level_of_happiness
  if (level === null || level === undefined || Number.isNaN(Number(level))) return ''
  const label = props.record.reward_label
  return label ? `${level} ${label}` : `${level}`
})

const scoreColor = computed(() => props.record.reward_color || '#6B7280')

const parsedTags = computed(() => {
  if (!props.record.tags) return []
  return props.record.tags.split(',').map(t => t.trim()).filter(Boolean)
})

function formatDate(d: string) {
  if (!d) return ''
  return d.slice(0, 10)
}
</script>

<style scoped lang="scss">
.sugar-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #E5E7EB;
  transition: all 0.2s;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    border-color: #d1d5db;
  }

  .card-main {
    display: flex;
    gap: 12px;
    padding: 16px 20px;
    align-items: flex-start;
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

      // 分数 + 档位词：紧跟日期，是这一行唯一带色的一段
      .card-score {
        font-size: 13px;
        font-weight: 600;
        white-space: nowrap;
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
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: #1F2937;
      line-height: 1.4;
    }

    // 备注：与标题留出间距，靠字号/颜色区分层次，不加分隔线（那是展开态才需要的）
    .card-notes {
      margin: 6px 0 0;
      font-size: 13px;
      color: #6B7280;
      line-height: 1.6;
      white-space: pre-wrap;
    }

    .sugar-meta {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px;
      margin-top: 8px;

      .joy-tag {
        border: none;
        background: #FEF3C7;
        color: #D97706;
        font-weight: 500;
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
