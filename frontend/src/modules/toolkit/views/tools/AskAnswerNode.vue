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
        <div class="answer-body markdown-body" :class="{ collapsed: !expanded }" v-html="rendered" />
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
import { computed, ref } from 'vue'
import { marked } from 'marked'
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

/** 回答正文 markdown 渲染（breaks: 单换行成段，AI 回答排版习惯） */
const rendered = computed(() => {
  if (!props.answer.answer) return ''
  return marked.parse(props.answer.answer, { breaks: true, gfm: true })
})

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
      word-break: break-word;
      overflow-wrap: break-word;
      color: var(--el-text-color-regular);

      &.collapsed {
        max-height: 200px;
        overflow: hidden;
        position: relative;
        &::after {
          content: '';
          position: absolute;
          left: 0; right: 0; bottom: 0; height: 40px;
          background: linear-gradient(transparent, var(--el-bg-color));
        }
      }

      // markdown 渲染样式（内容为 marked 输出，须 :deep）
      :deep(p) { margin: 6px 0; }
      :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5) {
        font-weight: 600;
        color: var(--el-text-color-primary);
        margin: 10px 0 6px;
        line-height: 1.5;
      }
      :deep(h1) { font-size: 16px; }
      :deep(h2) { font-size: 15px; }
      :deep(h3) { font-size: 14px; }
      :deep(h4), :deep(h5) { font-size: 13px; }
      :deep(ul), :deep(ol) { padding-left: 22px; margin: 6px 0; }
      :deep(li) { margin: 3px 0; }
      :deep(blockquote) {
        border-left: 3px solid var(--el-color-primary-light-5);
        padding: 6px 12px;
        margin: 8px 0;
        background: var(--el-fill-color-light);
        color: var(--el-text-color-secondary);
        border-radius: 0 4px 4px 0;
      }
      :deep(code) {
        background: var(--el-fill-color);
        padding: 1px 5px;
        border-radius: 3px;
        font-size: 12px;
        font-family: Menlo, Consolas, monospace;
        color: var(--el-color-primary-dark-2);
      }
      :deep(pre) {
        background: var(--el-fill-color-light);
        padding: 10px 12px;
        border-radius: 6px;
        overflow-x: auto;
        margin: 8px 0;
        code {
          background: none;
          padding: 0;
          color: inherit;
        }
      }
      :deep(a) { color: var(--el-color-primary); text-decoration: none; &:hover { text-decoration: underline; } }
      :deep(table) {
        border-collapse: collapse;
        width: 100%;
        margin: 8px 0;
        display: block;
        overflow-x: auto;
        th, td {
          border: 1px solid var(--el-border-color);
          padding: 5px 9px;
          text-align: left;
          font-size: 12px;
        }
        th { background: var(--el-fill-color-light); font-weight: 600; }
      }
      :deep(hr) { border: none; border-top: 1px solid var(--el-border-color-light); margin: 10px 0; }
      :deep(img) { max-width: 100%; }
      :deep(strong) { color: var(--el-text-color-primary); }
    }

    .expand-btn { margin-top: 2px; }
  }
}
</style>
