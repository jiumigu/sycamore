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
      <!-- 段落型金句本身就是一篇 Markdown 文章（`###` 小标题 / `**` 加粗 / 列表 / `---`），
           必须渲染后再展示 —— 否则这些标记会以裸符号的样子糊在正文里 -->
      <div v-if="quote.is_paragraph" class="quote-detail__content" v-html="rendered"></div>
      <!-- 短句型不渲染 Markdown：一句「3 * 5 = 15」不该被当成斜体。
           这里要的是「原样 + 保留换行」，不是排版 -->
      <div v-else class="quote-detail__content quote-detail__content--plain">
        {{ quote.content }}
      </div>

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
import { renderMarkdown } from '@/shared/utils/markdown'
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
const rendered = computed(() => renderMarkdown(props.quote?.content))
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
.quote-detail__content--plain {
  white-space: pre-wrap;
}

/* markdown 渲染样式（内容由 v-html 注入，scoped 打不进去，必须 :deep） */
.quote-detail__content :deep(p) {
  margin: 8px 0;
}
.quote-detail__content :deep(h1),
.quote-detail__content :deep(h2),
.quote-detail__content :deep(h3),
.quote-detail__content :deep(h4),
.quote-detail__content :deep(h5),
.quote-detail__content :deep(h6) {
  margin: 16px 0 8px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--el-text-color-primary);
}
.quote-detail__content :deep(h1) {
  font-size: 19px;
}
.quote-detail__content :deep(h2) {
  font-size: 17px;
}
.quote-detail__content :deep(h3) {
  font-size: 16px;
}
.quote-detail__content :deep(h4),
.quote-detail__content :deep(h5),
.quote-detail__content :deep(h6) {
  font-size: 15px;
}
.quote-detail__content :deep(ul),
.quote-detail__content :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}
.quote-detail__content :deep(li) {
  margin: 4px 0;
}
.quote-detail__content :deep(blockquote) {
  margin: 10px 0;
  padding: 6px 14px;
  border-left: 3px solid var(--el-color-primary-light-5);
  border-radius: 0 4px 4px 0;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
}
.quote-detail__content :deep(hr) {
  margin: 18px 0;
  border: none;
  border-top: 1px solid var(--el-border-color-lighter);
}
.quote-detail__content :deep(code) {
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--el-fill-color);
  font-family: Menlo, Consolas, monospace;
  font-size: 13px;
  color: var(--el-color-primary-dark-2);
}
.quote-detail__content :deep(pre) {
  margin: 10px 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  overflow-x: auto;
}
.quote-detail__content :deep(pre code) {
  padding: 0;
  background: none;
  color: inherit;
}
.quote-detail__content :deep(a) {
  color: var(--el-color-primary);
  text-decoration: none;
}
.quote-detail__content :deep(a:hover) {
  text-decoration: underline;
}
.quote-detail__content :deep(table) {
  width: 100%;
  margin: 10px 0;
  border-collapse: collapse;
  font-size: 14px;
}
.quote-detail__content :deep(th),
.quote-detail__content :deep(td) {
  padding: 6px 10px;
  border: 1px solid var(--el-border-color-lighter);
  text-align: left;
}
.quote-detail__content :deep(th) {
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.quote-detail__content :deep(strong) {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

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
