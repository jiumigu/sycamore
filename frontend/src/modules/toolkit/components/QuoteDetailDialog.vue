<template>
  <el-dialog
    v-model="visible"
    :title="title"
    class="quote-detail"
    width="min(880px, 92vw)"
    top="6vh"
    append-to-body
  >
    <template v-if="quote">
      <!--
        段落型金句本身就是一篇 Markdown 文章（`###` 小标题 / `**` 加粗 / 列表 / `---`），
        必须渲染后再展示 —— 否则这些标记会以裸符号的样子糊在正文里。
        短句型不渲染 Markdown：一句「3 * 5 = 15」不该被当成斜体。这里要的是
        「原样 + 保留换行」，不是排版。

        ⚠️ 分流靠**后端 `is_paragraph`** 显式标记（不是内容自证），所以显式传 mode，
           **不要**改成默认的 `auto` —— 那会把口径从「后端说了算」换成「前端猜」。
        渲染与排版全在 `MarkdownText` 里，本组件不再持有一份 `:deep()` 样式。
      -->
      <MarkdownText
        class="quote-detail__content"
        :mode="quote.is_paragraph ? 'markdown' : 'plain'"
        :text="quote.content"
      />

      <div class="quote-detail__meta">
        <span v-if="quote.author" class="quote-detail__author">— {{ quote.author }}</span>
        <el-tag v-if="quote.language" size="small" effect="plain">{{ quote.language }}</el-tag>
        <span v-if="quote.category" class="quote-detail__category">{{ quote.category }}</span>
      </div>
      <div v-if="quote.source" class="quote-detail__source">📎 {{ quote.source }}</div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownText from '@/shared/components/MarkdownText.vue'
import type { Quote } from '../types/quoteTypes'

/**
 * 金句详情弹窗（汇总总览 / 仪表盘共用）。
 *
 * 从两处各写一份的 `<el-dialog>` 合并而来 —— 原先 500px / 600px 且都是纯文本渲染，
 * 长文挤成窄窄一栏、Markdown 标记全裸。宽度与渲染只此一处。
 *
 * 宽度取 `min(880px, 92vw)`：
 * - 880px 让中文正文落到约 50 字/行的舒适区（原先 500px 约 25 字/行，读长了很累）；
 * - `92vw` 保证窄屏不溢出。
 *
 * 正文限高 68vh 独立滚动，标题与落款固定 —— 长文不会把弹窗撑出屏幕。
 */
defineOptions({ name: 'QuoteDetailDialog' })

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  quote: Quote | null
}>()

const title = computed(() => props.quote?.short_title || '金句详情')
</script>

<style scoped>
.quote-detail__content {
  max-height: 68vh;
  overflow-y: auto;
  padding-right: 6px;
  font-size: 15px;
  line-height: 1.9;
  color: var(--el-text-color-primary);
  word-break: break-word;
}
/*
 * 正文的 markdown 排版（`.md-text__body :deep(...)` 那一套）已整体搬进
 * `@/shared/components/MarkdownText.vue` —— 原先 QuoteDetailDialog / LogseqViewer /
 * AskAnswerNode 各持一份近似的排版块，改一处必然漏两处。
 * 本组件今后只负责这个**盒子**（限高 / 滚动 / 基准字号）；
 * 「渲染还是纯文本」也由 MarkdownText 按传入的 mode 决定。
 */

.quote-detail__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.quote-detail__author {
  font-size: 14px;
  font-style: italic;
  color: var(--el-text-color-secondary);
}
.quote-detail__category {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.quote-detail__source {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}
</style>
