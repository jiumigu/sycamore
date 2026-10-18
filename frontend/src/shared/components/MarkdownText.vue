<!--
  标记文本块 —— 一段文字该按 Markdown 排版、还是原样显示，只在这里判一次。

  为什么需要它：`shared/utils/markdown.ts` 早就声明了「唯一实现」，但收敛的只是
  **函数**（`renderMarkdown`），**样式**却各写各的 —— `QuoteDetailDialog` /
  `LogseqViewer` / `AskAnswerNode` 各有一套近似的 `:deep()` 排版块。再加一处
  「好东西档案馆的摘录要渲染 Markdown」就会变成第 4 份。所以这里把
  「渲染 + 排版」一起收成一个组件：调用方只管给文字，不管怎么排版。

  🔴 分流判据（`mode="auto"`）不在组件里现编，走 `containsMarkdown()`
     —— 原因见那个函数：自由文本框里既有拷来的 .md，也有随手写的手记，
     无条件过 marked 会把「3 * 5 = 15」读成斜体。

  ⚠️ 样式是 **em 相对单位**，不写死 px：同一个组件要同时服务
     金句详情的 15px 正文与档案馆详情的 14px 正文，字号由调用方的容器决定，
     组件只负责「标题比正文大多少、段落间距多少」这类比例。

  ⚠️ 正文由 `v-html` 注入，scoped 样式打不进运行时产生的节点 ⇒ 内部一律 `:deep()`。
-->
<template>
  <div class="md-text" :class="isMarkdown ? 'md-text--prose' : 'md-text--plain'">
    <div v-if="isMarkdown" class="md-text__body" v-html="html" />
    <template v-else>{{ text }}</template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { containsMarkdown, renderMarkdown } from '@/shared/utils/markdown'

defineOptions({ name: 'MarkdownText' })

const props = withDefaults(defineProps<{
  text?: string | null
  /**
   * - `auto`（默认）：交给 `containsMarkdown()` 判 —— 含 Markdown 标记才渲染，
   *   否则原样 + 保留换行。**自由文本框（摘录 / 理由 / 后果）用这个**，
   *   这样存量手记的观感一条都不会变。
   * - `markdown`：强制渲染。数据源**已知**是 Markdown 时用
   *   （如金句里后端标了 `is_paragraph` 的段落型）。
   * - `plain`：强制纯文本。**短字段用这个**（📍场景 / 在哪能找到），
   *   免得一句「3 * 5 = 15」被当成斜体 —— 与 `QuoteDetailDialog` 的取舍同源。
   */
  mode?: 'auto' | 'markdown' | 'plain'
}>(), {
  text: '',
  mode: 'auto',
})

const isMarkdown = computed(() => {
  if (props.mode === 'markdown') return true
  if (props.mode === 'plain') return false
  return containsMarkdown(props.text)
})

const html = computed(() => (isMarkdown.value ? renderMarkdown(props.text) : ''))
</script>

<style scoped>
.md-text {
  word-break: break-word;
}

/* 纯文本：要的是「原样 + 保留换行」，不是排版 */
.md-text--plain {
  white-space: pre-wrap;
}

/* 首尾边距清零：内容自带 margin，盒子有自己的 padding，
   不清零的话带 padding 的盒子（.detail-text）首行会多出一段空隙。 */
.md-text__body :deep(> :first-child) {
  margin-top: 0;
}
.md-text__body :deep(> :last-child) {
  margin-bottom: 0;
}

.md-text__body :deep(p) {
  margin: 8px 0;
}
.md-text__body :deep(h1),
.md-text__body :deep(h2),
.md-text__body :deep(h3),
.md-text__body :deep(h4),
.md-text__body :deep(h5),
.md-text__body :deep(h6) {
  margin: 16px 0 8px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--el-text-color-primary);
}
.md-text__body :deep(h1) { font-size: 1.35em; }
.md-text__body :deep(h2) { font-size: 1.2em; }
.md-text__body :deep(h3) { font-size: 1.1em; }
.md-text__body :deep(h4),
.md-text__body :deep(h5),
.md-text__body :deep(h6) { font-size: 1em; }

.md-text__body :deep(ul),
.md-text__body :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}
.md-text__body :deep(li) {
  margin: 4px 0;
}

/*
 * 🔴 代码块 / 引用块用 `--el-fill-color-darker`（#e6e8eb）而不是 `--el-fill-color-light`
 *    （#f5f7fa）：后者**恰好等于**带底色的承载盒子（`.detail-text` 就是 f5f7fa），
 *    于是渲染出来的块与盒子同色、看不出边界 —— 实测 `pre` 只有一行字浮在灰底上。
 *    判据：**渲染出来的块必须与承载它的盒子区分得开**，不能假定外层是白底。
 *    代码块再补一道 1px 边框：它没有引用块那样的左侧色条，只靠底色差太弱。
 */
.md-text__body :deep(blockquote) {
  margin: 10px 0;
  padding: 6px 14px;
  border-left: 3px solid var(--el-color-primary-light-5);
  border-radius: 0 4px 4px 0;
  background: var(--el-fill-color-darker);
  color: var(--el-text-color-regular);
}
.md-text__body :deep(hr) {
  margin: 18px 0;
  border: none;
  border-top: 1px solid var(--el-border-color-lighter);
}

.md-text__body :deep(code) {
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--el-fill-color-dark);
  font-family: Menlo, Consolas, monospace;
  font-size: 0.87em;
  color: var(--el-color-primary-dark-2);
}
.md-text__body :deep(pre) {
  margin: 10px 0;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-fill-color-darker);
  overflow-x: auto;
}
.md-text__body :deep(pre code) {
  padding: 0;
  background: none;
  color: inherit;
}

.md-text__body :deep(a) {
  color: var(--el-color-primary);
  text-decoration: none;
}
.md-text__body :deep(a:hover) {
  text-decoration: underline;
}

.md-text__body :deep(table) {
  width: 100%;
  margin: 10px 0;
  border-collapse: collapse;
  font-size: 0.93em;
}
.md-text__body :deep(th),
.md-text__body :deep(td) {
  padding: 6px 10px;
  border: 1px solid var(--el-border-color-lighter);
  text-align: left;
}
.md-text__body :deep(th) {
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.md-text__body :deep(strong) {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
/* 图片一律不超出容器：摘录里贴张图不该把弹窗撑破 */
.md-text__body :deep(img) {
  max-width: 100%;
}
</style>
