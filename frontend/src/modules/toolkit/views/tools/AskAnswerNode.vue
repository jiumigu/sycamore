<!-- AskAnswerNode.vue — AI 问答库·回答节点（支持多轮追问链递归展示/录入） -->
<template>
  <div class="answer-node">
    <!-- 非首轮：追问行 -->
    <div v-if="depth > 0" class="followup-question">
      <span class="followup-mark">↳ 追问</span>
      <span class="followup-text">{{ answer.question || '（未记录追问文本）' }}</span>
    </div>

    <div class="answer-card-wrap">
      <el-card shadow="never" class="answer-card" :class="{ 'is-followup': depth > 0 }">
        <div class="answer-head">
          <span class="ai-badge">{{ answer.ai }}</span>
          <el-tag v-if="answer.session" size="small" type="info" class="session-tag">{{ answer.session }}</el-tag>
          <span class="asked-time">{{ formatDateTime(answer.asked_at) }}</span>
          <el-select
            :model-value="answer.verdict || ''"
            placeholder="采纳?"
            size="small"
            class="verdict-select"
            @change="(v: string) => onVerdictChange(answer, v)"
          >
            <el-option label="未标记" value="" />
            <el-option label="✅ 采纳" value="采纳" />
            <el-option label="📎 备用" value="备用" />
            <el-option label="✖ 不采用" value="不采用" />
          </el-select>
          <span class="head-spacer" />
          <el-button size="small" link type="primary" @click="onFollowUp(answer)">
            <el-icon><ChatLineRound /></el-icon> 追问
          </el-button>
          <el-button size="small" link @click="onEdit(answer)">编辑</el-button>
          <el-button size="small" link type="danger" @click="onDelete(answer)">删除</el-button>
        </div>
        <p v-if="answer.note" class="answer-note">{{ answer.note }}</p>
        <div class="answer-body" :class="{ collapsed: !expanded }">
          {{ answer.answer }}
        </div>
        <div v-if="answer.answer.length > 220" class="expand-btn">
          <el-button size="small" link type="primary" @click="expanded = !expanded">
            {{ expanded ? '收起' : '展开全文' }}
          </el-button>
        </div>
      </el-card>

      <!-- 追问子树（递归，同一批回调直达顶层） -->
      <AskAnswerNode
        v-for="child in children"
        :key="child.id"
        :answer="child"
        :children="childrenOf(child.id)"
        :children-of="childrenOf"
        :depth="depth + 1"
        :on-verdict-change="onVerdictChange"
        :on-follow-up="onFollowUp"
        :on-edit="onEdit"
        :on-delete="onDelete"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ChatLineRound } from '@element-plus/icons-vue'
import type { AskAnswerItem } from '../../api/askLibraryApi'

defineOptions({ name: 'AskAnswerNode' })

const props = defineProps<{
  answer: AskAnswerItem
  /** 当前节点的直接子追问（按时间升序） */
  children: AskAnswerItem[]
  /** 查找某节点的直接子追问 */
  childrenOf: (parentId: number) => AskAnswerItem[]
  depth: number
  onVerdictChange: (ans: AskAnswerItem, verdict: string) => void
  onFollowUp: (ans: AskAnswerItem) => void
  onEdit: (ans: AskAnswerItem) => void
  onDelete: (ans: AskAnswerItem) => void
}>()

const expanded = ref(false)

function formatDateTime(iso?: string | null): string {
  if (!iso) return ''
  return iso.slice(0, 16).replace('T', ' ')
}
</script>

<style scoped lang="scss">
.answer-node {
  border-left: 2px solid var(--el-border-color-lighter);

  .followup-question {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin: 10px 0 6px;
    padding-left: 12px;

    .followup-mark {
      flex-shrink: 0;
      font-size: 11px;
      font-weight: 600;
      color: var(--el-color-primary);
      background: var(--el-color-primary-light-9);
      padding: 1px 6px;
      border-radius: 4px;
      margin-top: 2px;
    }

    .followup-text {
      font-size: 13px;
      color: var(--el-text-color-regular);
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }
  }

  .answer-card-wrap { padding-left: 12px; padding-bottom: 2px; }

  .answer-card {
    &.is-followup { border-color: var(--el-color-primary-light-7); }

    .answer-head {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
      flex-wrap: wrap;

      .ai-badge { font-size: 13px; font-weight: 600; color: var(--el-color-primary); }
      .session-tag { max-width: 220px; }
      .asked-time { font-size: 12px; color: var(--el-text-color-placeholder); }
      .verdict-select { width: 110px; }
      .head-spacer { flex: 1; }
    }

    .answer-note {
      font-size: 12px;
      color: var(--el-color-warning);
      background: var(--el-color-warning-light-9);
      padding: 4px 8px;
      border-radius: 4px;
      margin: 0 0 6px;
    }

    .answer-body {
      font-size: 13px;
      line-height: 1.8;
      white-space: pre-wrap;
      word-break: break-word;
      color: var(--el-text-color-regular);

      &.collapsed {
        max-height: 180px;
        overflow: hidden;
        position: relative;
        &::after {
          content: '';
          position: absolute;
          left: 0; right: 0; bottom: 0; height: 40px;
          background: linear-gradient(transparent, var(--el-bg-color));
        }
      }
    }

    .expand-btn { margin-top: 2px; }
  }
}
</style>
